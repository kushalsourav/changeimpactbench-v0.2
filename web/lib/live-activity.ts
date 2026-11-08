/** Parse the actual subprocess log, never generate fictional agent steps. */
export type LiveActivity = {
  key: string;
  id: string;
  turn: number | null;
  tool: string;
  target: string;
  title: string;
  detail: string;
  kind: 'tool' | 'problem' | 'provider' | 'result';
};

const PROVIDER = '(?:provider|Anthropic|Gemini)';
const requestPattern = new RegExp(`^turn=(\\d+)\\/\\d+\\s*·\\s*${PROVIDER} request`, 'i');

/** The API log is unprefixed, while copied FastAPI terminal output has this prefix. */
function observableLine(raw: string): string {
  return raw
    .trim()
    .replace(/^\[ChangeImpactBench agent pid=\d+\]\s*/, '')
    .trim();
}

export function summarizeTool(tool: string, argumentText: string): string {
  let result: Record<string, unknown> | null = null;
  try {
    const parsed: unknown = JSON.parse(argumentText);
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed))
      result = parsed as Record<string, unknown>;
  } catch {
    /* subprocess log truncates observations; don't guess missing values */
  }
  if (!result) {
    // Older live logs truncated observation JSON. Use only literal visible fields.
    const field = (name: string) =>
      new RegExp(`\"${name}\"\\s*:\\s*(\\d+)`).exec(argumentText)?.[1];
    if (tool === 'simulate_repair' || tool === 'apply_repair') {
      const action = /"action_id"\s*:\s*"([^"]+)"/.exec(argumentText)?.[1] || 'Repair';
      const cost = field('cost'),
        restored = field('restored_count');
      const remaining = field('unavailable_after_count'),
        newOutages = field('newly_unavailable_count');
      const facts = [
        cost != null ? `cost ${cost}` : '',
        restored != null ? `${restored} restored` : '',
        remaining != null ? `${remaining} remain` : '',
        newOutages != null ? `${newOutages} new outage${newOutages === '1' ? '' : 's'}` : '',
      ].filter(Boolean);
      if (facts.length) return `${action}: ${facts.join(' · ')}`;
    }
    if (tool === 'read_alert') return 'Incident alert received';
    if (tool === 'scan_service_health') {
      const statuses = [...argumentText.matchAll(/"svc-\d+"\s*:\s*"(healthy|unavailable)"/g)].map(
        (match) => match[1],
      );
      if (statuses.length)
        return `${statuses.filter((value) => value === 'healthy').length} healthy · ${statuses.filter((value) => value === 'unavailable').length} unavailable (visible probes)`;
      return 'External service probes recorded';
    }
    if (tool === 'inspect_metrics') {
      const status = /"health_probe"\s*:\s*"(healthy|unavailable)"/.exec(argumentText)?.[1];
      if (status) return `Health probe: ${status}`;
    }
    if (tool === 'inspect_config')
      return 'Raw configuration snapshot inspected';
    if (tool === 'inspect_dependencies') return 'Dependencies inspected';
    if (tool === 'list_repairs') return 'Candidate repairs reviewed';
    if (tool === 'prepare_repair') return 'Repair plan handed off';
    return 'Tool observation recorded';
  }
  if (tool === 'scan_service_health') {
    const statuses = result.statuses;
    if (statuses && typeof statuses === 'object') {
      const values = Object.values(statuses as Record<string, string>);
      return `${values.filter((v) => v === 'unavailable').length} unavailable / ${values.length} checked (synthetic initial snapshot)`;
    }
  }
  if (tool === 'simulate_repair' || tool === 'apply_repair') {
    const action = typeof result.action_id === 'string' ? result.action_id : 'Repair';
    const values = [
      typeof result.cost === 'number' ? `cost ${result.cost}` : '',
      typeof result.restored_count === 'number' ? `${result.restored_count} restored` : '',
      typeof result.unavailable_after_count === 'number'
        ? `${result.unavailable_after_count} remain`
        : '',
      typeof result.newly_unavailable_count === 'number'
        ? `${result.newly_unavailable_count} new outage${result.newly_unavailable_count === 1 ? '' : 's'}`
        : '',
    ].filter(Boolean);
    if (values.length) return `${action}: ${values.join(' · ')}`;
  }
  if (tool === 'list_repairs') {
    const available = result.candidate_repairs;
    if (Array.isArray(available))
      return `${available.length} candidate repairs listed; effects not revealed`;
  }
  if (tool === 'inspect_metrics') {
    const status = result.health_probe;
    if (typeof status === 'string') return `Health probe: ${status}`;
  }
  if (tool === 'inspect_config') {
    const values = result.configuration_snapshot;
    if (values && typeof values === 'object' && !Array.isArray(values)) {
      const entries = Object.entries(values as Record<string, unknown>);
      if (entries.length)
        return entries
          .map(([path, value]) => `${path.split('.').at(-1)} = ${String(value)}`)
          .join(' · ');
    }
    return 'Raw configuration snapshot inspected';
  }
  if (tool === 'inspect_dependencies') {
    const upstream =
      result.upstream && typeof result.upstream === 'object'
        ? Object.values(result.upstream as Record<string, unknown>).reduce<number>(
            (sum, value) => sum + (Array.isArray(value) ? value.length : 0),
            0,
          )
        : 0;
    const consumers = Array.isArray(result.direct_consumers) ? result.direct_consumers.length : 0;
    return `${upstream} upstream · ${consumers} direct consumer${consumers === 1 ? '' : 's'}`;
  }
  if (tool === 'prepare_repair') {
    const simulations = result.available_simulations;
    return result.handoff_accepted === true
      ? `Repair handoff accepted${typeof simulations === 'number' ? ` · ${simulations} simulations available` : ''}`
      : 'Repair plan recorded';
  }
  if (tool === 'submit_diagnosis') {
    return result.received === true && typeof result.final_status === 'string'
      ? result.final_status.replaceAll('_', ' ')
      : 'Diagnosis submission recorded';
  }
  if (result.rejected) return `Rejected: ${String(result.reason || 'invalid request')}`;
  return 'Tool observation recorded';
}

export function parseLiveActivity(log: string): LiveActivity[] {
  const result: LiveActivity[] = [];
  let turn: number | null = null;
  for (const [index, raw] of (log || '').split(/\r?\n/).entries()) {
    const line = observableLine(raw);
    const request = line.match(requestPattern);
    if (request) {
      turn = Number(request[1]);
      continue;
    }
    const observation = line.match(/^(EV\d+)\s+([a-z_]+)\s*(?:→|->)\s*(.*)$/i);
    if (observation) {
      const [, id, tool, data] = observation;
      const targetField =
        tool === 'simulate_repair' || tool === 'apply_repair' ? 'action_id' : 'service';
      const targetMatch = data.match(new RegExp(`"${targetField}"\\s*:\\s*"([^"]+)"`));
      const label = tool.replaceAll('_', ' ');
      const target = targetMatch?.[1] || '';
      result.push({
        key: `${index}-${id}`,
        id,
        turn,
        tool,
        target,
        title: `${label}${target ? ` · ${target}` : ''}`,
        detail: summarizeTool(tool, data),
        kind: 'tool',
      });
      continue;
    }
    if (
      /protocol error:|(?:provider|Anthropic|Gemini) failed|error:|budget exhausted|Input-token budget reached|Provider omitted input-token usage/i.test(
        line,
      )
    ) {
      result.push({
        key: `problem-${index}`,
        id: 'issue',
        turn,
        tool: 'warning',
        target: '',
        title: 'Issue recorded',
        detail: line.slice(0, 350),
        kind: 'problem',
      });
    } else if (/score=|Run saved:/.test(line)) {
      result.push({
        key: `result-${index}`,
        id: 'result',
        turn,
        tool: 'result',
        target: '',
        title: 'Episode result saved',
        detail: line.slice(0, 250),
        kind: 'result',
      });
    }
  }
  return result;
}

/** Derive workflow progress only from real log lines; never infer a diagnosis or repair. */
export const WORKFLOW_STAGES = [
  { key: 'received', label: 'Start investigation', tools: ['read_alert', 'scan_service_health'] },
  {
    key: 'investigate',
    label: 'Inspect the incident',
    tools: [
      'inspect_metrics',
      'inspect_logs',
      'inspect_config',
      'inspect_dependencies',
      'list_repairs',
    ],
  },
  { key: 'plan', label: 'Prepare a repair', tools: ['prepare_repair'] },
  { key: 'simulate', label: 'Test a repair', tools: ['simulate_repair'] },
  { key: 'apply', label: 'Apply a repair', tools: ['apply_repair'] },
  { key: 'diagnose', label: 'Submit diagnosis', tools: ['submit_diagnosis'] },
  { key: 'grade', label: 'Verify and grade', tools: [] },
] as const;

export type WorkflowStep = {
  key: string;
  label: string;
  detail: string;
  state: 'done' | 'current' | 'pending' | 'not-reached' | 'warning';
};
export type WorkflowState = { steps: WorkflowStep[]; episode: string; activity: LiveActivity[] };
export function currentEpisodeLog(fullLog: string): string {
  const lines = (fullLog || '').split(/\r?\n/);
  // The last score is a reliable episode boundary for each provider adapter.
  // A new episode cannot inherit a previous one's completed stages.
  const lastScore = lines.findLastIndex((line) => /^\s+score=/.test(line));
  const precedingScore =
    lastScore >= 0
      ? lines.slice(0, lastScore).findLastIndex((line) => /^\s+score=/.test(line))
      : -1;
  const afterScore = lines.slice(lastScore + 1).join('\n');
  // A new trial starts when another provider request is actually logged.
  // Until then, keep showing the preceding episode instead of resetting it.
  const nextTrialHasStarted = /turn=\d+\/\d+\s*·\s*(?:provider|Anthropic|Gemini) request/.test(
    afterScore,
  );
  const segment =
    lastScore < 0
      ? fullLog
      : nextTrialHasStarted
        ? afterScore
        : lines.slice(precedingScore + 1).join('\n');
  return segment;
}

export function parseLiveWorkflow(fullLog: string, running: boolean): WorkflowState {
  const segment = currentEpisodeLog(fullLog);
  const activity = parseLiveActivity(segment);
  const tools = new Set(activity.filter((a) => a.kind === 'tool').map((a) => a.tool));
  const requestSeen = segment
    .split(/\r?\n/)
    .some((line) => requestPattern.test(observableLine(line)));
  const terminal = /^\s+score=(\S+)\s+pass=(\S+)\s+status=(\S+)/m.exec(segment);
  const graded = Boolean(terminal && terminal[1] !== 'None' && terminal[3] === 'completed');
  const ended = !running && Boolean(segment.trim());
  const observedStages = WORKFLOW_STAGES.map((stage) =>
    stage.tools.some((tool) => tools.has(tool)),
  );
  if (requestSeen) observedStages[0] = true;
  if (graded) observedStages[WORKFLOW_STAGES.length - 1] = true;
  const reached = Math.max(0, ...observedStages.map((seen, index) => (seen ? index : -1)));
  const inspected = new Set(
    activity
      .filter((item) => item.tool.startsWith('inspect_') && item.target)
      .map((item) => item.target),
  ).size;
  const simulations = activity.filter((item) => item.tool === 'simulate_repair');
  const details = [
    tools.has('scan_service_health')
      ? 'Alert read, probes scanned'
      : tools.has('read_alert')
        ? 'Alert read'
        : requestSeen
          ? 'Waiting for first tool event'
          : 'Waiting to start',
    inspected ? `${inspected} service${inspected === 1 ? '' : 's'} inspected` : '',
    tools.has('prepare_repair') ? 'Handoff accepted' : '',
    simulations.length
      ? `${simulations.length} simulation${simulations.length === 1 ? '' : 's'} recorded`
      : '',
    tools.has('apply_repair') ? 'Repair applied' : '',
    tools.has('submit_diagnosis') ? 'Diagnosis submitted' : '',
    graded ? 'Grade recorded' : ended ? 'Unverified, no completed grade' : '',
  ];
  return {
    steps: WORKFLOW_STAGES.map((stage, i) => ({
      key: stage.key,
      label: stage.label,
      detail: details[i],
      state: graded
        ? 'done'
        : ended
          ? i <= reached && i < WORKFLOW_STAGES.length - 1
            ? 'done'
            : i === WORKFLOW_STAGES.length - 1
              ? 'warning'
              : 'not-reached'
          : i < reached
            ? 'done'
            : i === reached
              ? 'current'
              : 'pending',
    })),
    episode: /\[(\d+\/\d+)\].*trial=\d+/.exec(segment)?.[1] || '',
    activity,
  };
}
