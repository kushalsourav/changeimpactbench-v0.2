/** UI summaries from the saved JSONL episode only; never turn an unverified run into a failure. */
export type RecordedRepair = {
  action: string;
  cost: number | null;
  restored: number | null;
  newOutages: number | null;
  remaining: number | null;
  committed: boolean;
};
const number = (x: unknown): number | null => typeof x === 'number' && Number.isFinite(x) ? x : null;
const text = (x: unknown): string => typeof x === 'string' ? x : '';
export function savedRunFacts(raw: Record<string, unknown>, manifest?: Record<string, unknown> | null) {
  const events = Array.isArray(raw.trajectory) ? raw.trajectory as Array<Record<string, unknown>> : [];
  const repairs: RecordedRepair[] = [];
  let prepared = false, diagnosis = false;
  for (const entry of events) {
    const tool = text(entry.tool);
    if (tool === 'prepare_repair') prepared = true;
    if (tool === 'submit_diagnosis') diagnosis = true;
    if (tool !== 'simulate_repair' && tool !== 'apply_repair') continue;
    const args = (entry.arguments || {}) as Record<string, unknown>;
    const observation = (entry.observation || {}) as Record<string, unknown>;
    const result = (observation.result || {}) as Record<string, unknown>;
    repairs.push({
      action: text(result.action_id || args.action_id),
      cost: number(result.cost), restored: number(result.restored_count),
      newOutages: number(result.newly_unavailable_count),
      remaining: number(result.unavailable_after_count),
      committed: tool === 'apply_repair',
    });
  }
  const requests = number(raw.provider_requests);
  const limit = number(raw.max_agent_turns) ?? number(manifest?.max_agent_turns);
  const submitted = diagnosis || Boolean(raw.final_diagnosis);
  const committed = repairs.some(r => r.committed);
  const safeTested = repairs.filter(r => !r.committed && r.remaining === 0 && r.newOutages === 0)
    .sort((a, b) => (a.cost ?? Infinity) - (b.cost ?? Infinity))[0] || null;
  const status = text(raw.status);
  const termination = text(raw.termination_reason);
  const inputLimit = number(raw.max_input_tokens_requested) ?? number(manifest?.max_input_tokens);
  const inputUsed = number(raw.input_tokens_reported) ?? number((raw.usage as Record<string, unknown> | undefined)?.prompt_tokens);
  let summary: string;
  if (status !== 'completed') {
    const budget = requests != null && limit != null && requests >= limit;
    summary = termination === 'input_token_budget'
      ? `The agent reached its ${inputLimit?.toLocaleString() ?? 'configured'} input-token budget (${inputUsed?.toLocaleString() ?? 'unreported'} reported) and stopped before another model request.`
      : termination === 'provider_input_usage_missing'
      ? 'The provider did not report input-token usage, so another request was blocked to enforce the configured budget.'
      : budget
      ? `The attempt reached its ${limit} model-request limit before ${!committed ? 'applying a repair' : 'submitting a diagnosis'}.`
      : `The attempt ended as ${status.replaceAll('_', ' ') || 'unverified'} without a verified final outcome.`;
    if (safeTested && !committed)
      summary += ` It simulated ${safeTested.action} (cost ${safeTested.cost ?? 'not recorded'}), which restored ${safeTested.restored ?? 'an unrecorded number of'} services with no new outages, but did not commit it.`;
    if (!submitted) summary += ' No final diagnosis was submitted.';
  } else {
    summary = committed ? 'The agent committed a repair. See the verified outcome and grader below.' : 'The agent completed this episode. Review the saved evidence.';
  }
  return { repairs, prepared, submitted, committed, safeTested, requests, limit, summary };
}
