/** Structured facts copied from visible live tool observations only. */
export type LiveNodeObservation = {
  config?: string;
  dependencies?: string;
  eventIds: string[];
};

export type LiveRepairObservation = {
  eventId: string;
  action: string;
  kind: 'simulation' | 'applied';
  cost: number | null;
  restored: number | null;
  remaining: number | null;
  newOutages: number | null;
  simulationsRemaining: number | null;
  committed: boolean | null;
};

export type LiveObservations = {
  nodes: Record<string, LiveNodeObservation>;
  repairs: LiveRepairObservation[];
};

const serviceId = (value: unknown): string =>
  typeof value === 'string' && /^svc-\d+$/.test(value) ? value : '';
const numeric = (value: unknown): number | null =>
  typeof value === 'number' && Number.isFinite(value) ? value : null;

function fieldNumber(text: string, name: string): number | null {
  const match = new RegExp(`"${name}"\\s*:\\s*(-?\\d+(?:\\.\\d+)?)`).exec(text);
  return match ? Number(match[1]) : null;
}

function fieldBoolean(text: string, name: string): boolean | null {
  const match = new RegExp(`"${name}"\\s*:\\s*(true|false)`).exec(text);
  return match ? match[1] === 'true' : null;
}

function visibleObject(text: string): Record<string, unknown> | null {
  try {
    const value: unknown = JSON.parse(text);
    return value && typeof value === 'object' && !Array.isArray(value)
      ? (value as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}

function displayValue(value: unknown): string {
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return 'recorded';
}

function configSummary(result: Record<string, unknown>, raw: string): string {
  const values = result.configuration_snapshot;
  if (values && typeof values === 'object' && !Array.isArray(values)) {
    const entries = Object.entries(values as Record<string, unknown>);
    if (entries.length) {
      const [path, value] = entries[0];
      const key = path.split('.').at(-1) || path;
      return `Config: ${key} = ${displayValue(value)}${entries.length > 1 ? ` +${entries.length - 1}` : ''}`;
    }
  }
  return 'Raw configuration inspected';
}

function dependencySummary(result: Record<string, unknown>): string {
  const upstream = result.upstream;
  let upstreamCount = 0;
  if (upstream && typeof upstream === 'object' && !Array.isArray(upstream)) {
    for (const value of Object.values(upstream as Record<string, unknown>)) {
      if (Array.isArray(value)) upstreamCount += value.length;
    }
  }
  const consumers = Array.isArray(result.direct_consumers) ? result.direct_consumers.length : 0;
  if (upstreamCount || consumers)
    return `Dependencies: ${upstreamCount} upstream · ${consumers} consumer${consumers === 1 ? '' : 's'}`;
  return 'Dependencies inspected';
}

/** Supports both new compact observations and already-saved, truncated logs. */
export function observationsFromLog(log: string): LiveObservations {
  const nodes: Record<string, LiveNodeObservation> = {};
  const repairs: LiveRepairObservation[] = [];
  for (const rawLine of (log || '').split(/\r?\n/)) {
    const line = rawLine
      .trim()
      .replace(/^\[ChangeImpactBench agent pid=\d+\]\s*/, '')
      .trim();
    const match = line.match(/^(EV\d+)\s+([a-z_]+)\s*(?:→|->)\s*(.*)$/i);
    if (!match) continue;
    const [, eventId, tool, raw] = match;
    const result = visibleObject(raw) || {};
    const target = serviceId(result.service) || raw.match(/"service"\s*:\s*"(svc-\d+)"/)?.[1] || '';
    if (target && (tool === 'inspect_config' || tool === 'inspect_dependencies')) {
      const node = (nodes[target] ??= { eventIds: [] });
      if (!node.eventIds.includes(eventId)) node.eventIds.push(eventId);
      if (tool === 'inspect_config') node.config = configSummary(result, raw);
      else node.dependencies = dependencySummary(result);
    }
    if (tool !== 'simulate_repair' && tool !== 'apply_repair') continue;
    const action =
      (typeof result.action_id === 'string' ? result.action_id : '') ||
      raw.match(/"action_id"\s*:\s*"([^"]+)"/)?.[1] ||
      'Repair';
    const value = (name: string): number | null => numeric(result[name]) ?? fieldNumber(raw, name);
    repairs.push({
      eventId,
      action,
      kind: tool === 'apply_repair' ? 'applied' : 'simulation',
      cost: value('cost'),
      restored: value('restored_count'),
      remaining: value('unavailable_after_count'),
      newOutages: value('newly_unavailable_count'),
      simulationsRemaining: value('simulations_remaining'),
      committed:
        typeof result.committed_in_sandbox === 'boolean'
          ? result.committed_in_sandbox
          : fieldBoolean(raw, 'committed_in_sandbox'),
    });
  }
  return { nodes, repairs };
}
