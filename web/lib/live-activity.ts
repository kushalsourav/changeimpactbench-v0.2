/** Parse the actual subprocess log, never generate fictional agent steps. */
export type LiveActivity = { key: string; turn: number | null; tool: string; title: string; detail: string; kind: 'tool' | 'problem' | 'provider' | 'result' };

export function summarizeTool(tool: string, argumentText: string): string {
  let result: Record<string, unknown> | null = null;
  try {
    const parsed: unknown = JSON.parse(argumentText);
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) result = parsed as Record<string, unknown>;
  } catch { /* subprocess log truncates observations; don't guess missing values */ }
  if (!result) return 'Observation recorded; full values available in Episode evidence.';
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
  return 'Observation recorded; full details available in Episode evidence.';
}

export function parseLiveActivity(log: string): LiveActivity[] {
  const result: LiveActivity[] = [];
  let turn: number | null = null;
  for (const [index, raw] of (log || '').split(/\r?\n/).entries()) {
    const line = raw.trim();
    const request = line.match(/^turn=(\d+)\/\d+\s*·\s*(?:provider|Gemini) request/);
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
    if (/protocol error:|(?:provider|Gemini) failed|error:|budget exhausted/i.test(line)) {
      result.push({ key: `problem-${index}`, turn, tool: 'warning', title: `Turn ${turn ?? '?'} · Issue recorded`, detail: line.slice(0, 350), kind: 'problem' });
    } else if (/score=|Run saved:/.test(line)) {
      result.push({ key: `result-${index}`, turn, tool: 'result', title: 'Episode result saved', detail: line.slice(0, 250), kind: 'result' });
    }
  }
  return result;
}
