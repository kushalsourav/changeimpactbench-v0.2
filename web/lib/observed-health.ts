/** Health shown during a run comes from recorded tool observations, never the oracle. */
export type ObservedHealth = Record<string, 'healthy' | 'unavailable'>;
const svc = (value: unknown) => typeof value === 'string' && /^svc-\d+$/.test(value) ? value : '';
const health = (value: unknown): 'healthy' | 'unavailable' | null =>
  value === 'healthy' || value === 'unavailable' ? value : null;

function acceptObservation(statuses: ObservedHealth, tool: string, result: Record<string, unknown>) {
  if (tool === 'scan_service_health' && result.statuses && typeof result.statuses === 'object') {
    for (const [name, state] of Object.entries(result.statuses as Record<string, unknown>)) {
      const id = svc(name), value = health(state);
      if (id && value) statuses[id] = value;
    }
  }
  if (tool === 'inspect_metrics') {
    const id = svc(result.service), value = health(result.health_probe);
    if (id && value) statuses[id] = value;
  }
}

export function healthFromTrajectory(events: unknown): ObservedHealth {
  const statuses: ObservedHealth = {};
  if (!Array.isArray(events)) return statuses;
  for (const event of events) {
    if (!event || typeof event !== 'object') continue;
    const item = event as { tool?: unknown; observation?: { result?: unknown } };
    if (typeof item.tool === 'string' && item.observation?.result &&
        typeof item.observation.result === 'object' && !Array.isArray(item.observation.result))
      acceptObservation(statuses, item.tool, item.observation.result as Record<string, unknown>);
  }
  return statuses;
}

/** Runner logs may truncate an observation JSON mid-field. Recognize only explicit values. */
export function healthFromLog(log: string): ObservedHealth {
  const statuses: ObservedHealth = {};
  for (const line of (log || '').split(/\r?\n/)) {
    const match = line.trim().match(/^EV\d+\s+(scan_service_health|inspect_metrics)\s*→\s*(.*)$/);
    if (!match) continue;
    const [, tool, value] = match;
    try {
      const obj: unknown = JSON.parse(value);
      if (obj && typeof obj === 'object' && !Array.isArray(obj)) {
        acceptObservation(statuses, tool, obj as Record<string, unknown>);
        continue;
      }
    } catch { /* partial JSON: parse explicit field pairs below */ }
    if (tool === 'inspect_metrics') {
      const target = value.match(/"service"\s*:\s*"(svc-\d+)"/);
      const probe = value.match(/"health_probe"\s*:\s*"(healthy|unavailable)"/);
      if (target && probe) statuses[target[1]] = probe[1] as 'healthy' | 'unavailable';
    } else {
      // Only status pairs actually present in the observed, possibly truncated text.
      for (const p of value.matchAll(/"(svc-\d+)"\s*:\s*"(healthy|unavailable)"/g))
        statuses[p[1]] = p[2] as 'healthy' | 'unavailable';
    }
  }
  return statuses;
}
