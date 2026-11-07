import type { AgentEvent } from './api';

/** Plain-English summaries from observed tool outputs, not LLM inference. */
export function observedEventSummary(event: AgentEvent): string {
  const result = event.observation?.result || {};
  const n = (key: string) => typeof result[key] === 'number' ? result[key] as number : null;
  if (event.tool === 'read_alert') return 'Initial incident alert and neutral hypotheses read';
  if (event.tool === 'scan_service_health') {
    const statuses = result.statuses;
    if (statuses && typeof statuses === 'object' && !Array.isArray(statuses)) {
      const values = Object.values(statuses as Record<string, unknown>);
      return `${values.filter(v => v === 'unavailable').length} initially unavailable of ${values.length} services scanned`;
    }
    return 'Full synthetic availability scan recorded';
  }
  if (event.tool === 'inspect_metrics') {
    const probe = result.health_probe;
    const local = result.is_direct_local_fault;
    return `${typeof probe === 'string' ? `Health probe: ${probe}` : 'Metrics inspected'}${typeof local === 'boolean' ? ` · direct local fault: ${local ? 'yes' : 'no'}` : ''}`;
  }
  if (event.tool === 'inspect_config') {
    const values = result.referenced_values;
    return values && typeof values === 'object' && !Array.isArray(values)
      ? `Configuration rule and ${Object.keys(values).length} referenced values inspected`
      : 'Synthetic configuration inspected';
  }
  if (event.tool === 'inspect_dependencies') {
    const consumers = result.direct_consumers;
    return Array.isArray(consumers) ? `${consumers.length} direct consumers · upstream rules inspected` : 'Service dependencies inspected';
  }
  if (event.tool === 'inspect_logs') return 'Timestamped synthetic log evidence inspected';
  if (event.tool === 'list_repairs') {
    const candidates = result.candidate_repairs;
    return Array.isArray(candidates) ? `${candidates.length} sandbox repair candidates listed` : 'Repair candidates listed';
  }
  if (event.tool === 'prepare_repair') return 'Model-authored repair handoff accepted · no repair applied yet';
  if (event.tool === 'simulate_repair' || event.tool === 'apply_repair') {
    const restored = n('restored_count'), remaining = n('unavailable_after_count'), newDown = n('newly_unavailable_count');
    const prefix = event.tool === 'simulate_repair' ? 'Counterfactual only' : 'Committed to synthetic sandbox';
    return restored !== null && remaining !== null && newDown !== null
      ? `${prefix} · ${restored} restored · ${remaining} remain · ${newDown} new outages${event.tool === 'simulate_repair' && n('simulations_remaining') !== null ? ` · ${n('simulations_remaining')} simulations left` : ''}`
      : prefix;
  }
  if (event.tool === 'submit_diagnosis') return result.received === true ? 'Final incident report received for independent grading' : 'Final report submitted';
  return 'Observed sandbox tool result';
}
export function eventArguments(event: AgentEvent): string {
  const { service, action_id } = event.arguments || {};
  if (typeof service === 'string') return service;
  if (typeof action_id === 'string') return action_id;
  return '';
}
