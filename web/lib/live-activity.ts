/** Parse the actual subprocess log, never generate fictional agent steps. */
export type LiveActivity = { key: string; turn: number | null; tool: string; title: string; detail: string; kind: 'tool' | 'problem' | 'provider' | 'result' };

export function summarizeTool(tool: string, argumentText: string): string {
  let result: Record<string, unknown> | null = null;
  try {
    const parsed: unknown = JSON.parse(argumentText);
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) result = parsed as Record<string, unknown>;
  } catch { /* subprocess log truncates observations; don't guess missing values */ }
  if (!result) {
    // The durable logfile intentionally truncates observation JSON. Only use
    // literal fields present in the recorded text; never infer from the oracle.
    const field = (name: string) => new RegExp(`\"${name}\"\\s*:\\s*(\\d+)`).exec(argumentText)?.[1];
    if (tool === 'simulate_repair' || tool === 'apply_repair') {
      const action = /"action_id"\s*:\s*"([^"]+)"/.exec(argumentText)?.[1] || 'Repair';
      const restored = field('restored_count'), newOutages = field('newly_unavailable_count');
      if (restored && newOutages) return `${action}: ${restored} restored · ${newOutages} new outage${newOutages === '1' ? '' : 's'}`;
    }
    if (tool === 'read_alert') return 'Incident alert received';
    if (tool === 'scan_service_health') return 'External service probes recorded';
    if (tool === 'inspect_config') return /"configured_local_check"\s*:\s*false/.test(argumentText)
      ? 'No local failure check configured' : 'Configuration inspected';
    if (tool === 'inspect_dependencies') return 'Dependencies inspected';
    if (tool === 'list_repairs') return 'Candidate repairs reviewed';
    if (tool === 'prepare_repair') return 'Repair plan handed off';
    return 'Tool observation recorded';
  }
  if (tool === 'scan_service_health') {
    const statuses = result.statuses;
    if (statuses && typeof statuses === 'object') {
      const values = Object.values(statuses as Record<string, string>);
      return `${values.filter(v => v === 'unavailable').length} unavailable / ${values.length} checked (synthetic initial snapshot)`;
    }
  }
  if (tool === 'simulate_repair' || tool === 'apply_repair') {
    const restored = result.restored_count;
    const remaining = result.unavailable_after_count;
    const newFailures = result.newly_unavailable_count;
    if (typeof restored === 'number' && typeof remaining === 'number' && typeof newFailures === 'number') {
      return `${restored} restored · ${remaining} remain · ${newFailures} newly unavailable`;
    }
  }
  if (tool === 'list_repairs') {
    const available = result.candidate_repairs;
    if (Array.isArray(available)) return `${available.length} candidate repairs listed; effects not revealed`;
  }
  if (tool === 'inspect_metrics') {
    const status = result.health_probe;
    if (typeof status === 'string') return `Health probe: ${status}`;
  }
  if (result.rejected) return `Rejected: ${String(result.reason || 'invalid request')}`;
  return 'Tool observation recorded';
}

export function parseLiveActivity(log: string): LiveActivity[] {
  const result: LiveActivity[] = [];
  let turn: number | null = null;
  for (const [index, raw] of (log || '').split(/\r?\n/).entries()) {
    const line = raw.trim();
    const request = line.match(/^turn=(\d+)\/\d+\s*·\s*(?:provider|Anthropic|Gemini) request/);
    if (request) { turn = Number(request[1]); continue; }
    const observation = line.match(/^(EV\d+)\s+([a-z_]+)\s*→\s*(.*)$/);
    if (observation) {
      const [, id, tool, data] = observation;
      const serviceMatch = data.match(/"(?:service|action_id)"\s*:\s*"([^"]+)"/);
      const label = tool.replaceAll('_', ' ');
      result.push({ key: `${index}-${id}`, turn, tool,
        title: `Turn ${turn ?? '?'} · ${label}${serviceMatch ? ` (${serviceMatch[1]})` : ''}`,
        detail: summarizeTool(tool, data), kind: 'tool' });
      continue;
    }
    if (/protocol error:|(?:provider|Anthropic|Gemini) failed|error:|budget exhausted|Input-token budget reached|Provider omitted input-token usage/i.test(line)) {
      result.push({ key: `problem-${index}`, turn, tool: 'warning', title: `Turn ${turn ?? '?'} · Issue recorded`, detail: line.slice(0, 350), kind: 'problem' });
    } else if (/score=|Run saved:/.test(line)) {
      result.push({ key: `result-${index}`, turn, tool: 'result', title: 'Episode result saved', detail: line.slice(0, 250), kind: 'result' });
    }
  }
  return result;
}

/** Derive workflow progress only from real log lines; never infer a diagnosis or repair. */
export const WORKFLOW_STAGES = [
  { key: 'received', label: 'Start investigation', tools: [] },
  { key: 'investigate', label: 'Inspect the incident', tools: ['read_alert', 'scan_service_health', 'inspect_metrics', 'inspect_logs', 'inspect_config', 'inspect_dependencies', 'list_repairs'] },
  { key: 'plan', label: 'Prepare a repair', tools: ['prepare_repair'] },
  { key: 'simulate', label: 'Test a repair', tools: ['simulate_repair'] },
  { key: 'apply', label: 'Apply a repair', tools: ['apply_repair'] },
  { key: 'diagnose', label: 'Submit diagnosis', tools: ['submit_diagnosis'] },
  { key: 'grade', label: 'Verify and grade', tools: [] },
] as const;

export type WorkflowStep = {
  key: string;
  label: string;
  state: 'done' | 'current' | 'pending' | 'not-reached';
};
export type WorkflowState = { steps: WorkflowStep[]; episode: string; activity: LiveActivity[] };
export function currentEpisodeLog(fullLog: string): string {
  const lines = (fullLog || '').split(/\r?\n/);
  // The last score is a reliable episode boundary for each provider adapter.
  // A new episode cannot inherit a previous one's completed stages.
  const lastScore = lines.findLastIndex(line => /^\s+score=/.test(line));
  const precedingScore = lastScore >= 0
    ? lines.slice(0, lastScore).findLastIndex(line => /^\s+score=/.test(line)) : -1;
  const afterScore = lines.slice(lastScore + 1).join('\n');
  // A new trial starts when another provider request is actually logged.
  // Until then, keep showing the preceding episode instead of resetting it.
  const nextTrialHasStarted = /turn=\d+\/\d+\s*·\s*(?:provider|Anthropic|Gemini) request/.test(afterScore);
  const segment = lastScore < 0 ? fullLog
    : nextTrialHasStarted ? afterScore : lines.slice(precedingScore + 1).join('\n');
  return segment;
}

export function parseLiveWorkflow(fullLog: string, running: boolean): WorkflowState {
  const segment = currentEpisodeLog(fullLog);
  const activity = parseLiveActivity(segment);
  const tools = new Set(activity.filter(a => a.kind === 'tool').map(a => a.tool));
  const requestSeen = /turn=\d+\/\d+\s*·\s*(?:provider|Anthropic|Gemini) request/.test(segment);
  const terminal = /^\s+score=(\S+)\s+pass=(\S+)\s+status=(\S+)/m.exec(segment);
  const graded = Boolean(terminal && terminal[1] !== 'None' && terminal[3] === 'completed');
  const ended = Boolean(terminal);
  const completedKeys = new Set<string>();
  if (requestSeen || tools.size || graded) completedKeys.add('received');
  for (const stage of WORKFLOW_STAGES) {
    if (stage.tools.some(tool => tools.has(tool))) completedKeys.add(stage.key);
  }
  if (graded) completedKeys.add('grade');
  const reached = Math.max(-1, ...WORKFLOW_STAGES.map((stage, i) => completedKeys.has(stage.key) ? i : -1));
  // If only a provider request exists, we are waiting for the first inspection.
  const current = running ? Math.min(reached + 1, WORKFLOW_STAGES.length - 1) : -1;
  return {
    steps: WORKFLOW_STAGES.map((stage, i) => ({
      key: stage.key, label: stage.label,
      state: completedKeys.has(stage.key) ? 'done' : i === current ? 'current' : ended && !running ? 'not-reached' : 'pending',
    })),
    episode: /\[(\d+\/\d+)\].*trial=\d+/.exec(segment)?.[1] || '',
    activity,
  };
}
