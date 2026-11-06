/** Version-neutral, deterministic narrative. No model call or inferred chain-of-thought. */
import type { AgentEvent, EvidenceRow, TrialDetail } from './api';

export type DecisionStep = {
  turn: number;
  eventId: string;
  action: string;
  remaining: number | null;
  restored: number | null;
  newOutages: number | null;
  cost: number | null;
  label: string;
};
export type EpisodeExplanation = {
  title: string;
  summary: string;
  interpretation: string;
  strictlyPassed: boolean | null;
  rootCorrect: boolean | null;
  exactImpact: boolean | null;
  recoverySuccess: boolean | null;
  recoverySafe: boolean | null;
  initialAffected: number | null;
  restored: number | null;
  remaining: number | null;
  newOutages: number | null;
  missing: string[];
  extra: string[];
  steps: DecisionStep[];
  postCommitCitations: string[];
  diagnosisCitations: string[];
  semanticWarnings: string[];
};
const numeric = (value: unknown): number | null =>
  typeof value === 'number' && Number.isFinite(value) ? value : null;
const string = (value: unknown) => (typeof value === 'string' ? value : '');

export function explainEpisode(row: EvidenceRow, detail: TrialDetail): EpisodeExplanation {
  const g = detail.audit.grade || {};
  const events = (detail.record.trajectory || []) as AgentEvent[];
  const commit = events.find((e) => e.tool === 'apply_repair');
  const effect = (detail.record.committed_effect || {}) as Record<string, unknown>;
  const expected = detail.diagnosis?.expected;
  const predicted = detail.diagnosis?.predicted;
  const missing = detail.diagnosis?.missed_services || [];
  const extra = detail.diagnosis?.extra_services || [];
  const exactImpact = predicted ? missing.length === 0 && extra.length === 0 : null;
  const strictlyPassed = row.status === 'completed' ? g.strict_pass === true : null;
  const recoverySuccess = typeof g.recovery_success === 'boolean' ? g.recovery_success : null;
  const recoverySafe = typeof g.recovery_safe === 'boolean' ? g.recovery_safe : null;
  const steps: DecisionStep[] = events
    .filter((e) => e.tool === 'simulate_repair' || e.tool === 'apply_repair')
    .map((e) => {
      const values = e.observation.result;
      const remaining = numeric(values.unavailable_after_count);
      const newly = numeric(values.newly_unavailable_count);
      return {
        turn: e.provider_turn,
        eventId: e.observation.event_id,
        action: string(e.arguments.action_id),
        remaining,
        restored: numeric(values.restored_count),
        newOutages: newly,
        cost: numeric(values.cost),
        label: e.tool === 'simulate_repair' ? 'Simulated' : 'Committed',
      };
    });
  const committed = steps.find((step) => step.label === 'Committed');
  const initialAffected = expected?.failed_services.length ?? null;
  const restored = committed?.restored ?? (Array.isArray(effect.restored) ? effect.restored.length : null);
  const remaining = committed?.remaining ?? (Array.isArray(effect.unavailable_after) ? effect.unavailable_after.length : null);
  const newOutages = committed?.newOutages ?? (Array.isArray(effect.newly_unavailable) ? effect.newly_unavailable.length : null);
  const diagnosisCitations = Array.isArray((detail.record.final_diagnosis as Record<string, unknown> | undefined)?.evidence_ids)
    ? ((detail.record.final_diagnosis as Record<string, unknown>).evidence_ids as unknown[]).filter((v): v is string => typeof v === 'string')
    : [];
  // Only flag objectively false arithmetic written in the *submitted rationale*.
  // This is a consistency warning, not semantic evidence grading or a score change.
  const semanticWarnings: string[] = [];
  const rationale = string((detail.record.final_diagnosis as Record<string, unknown> | undefined)?.rationale);
  const numericComparisons = /([a-z][a-z0-9_.]*)\s*=\s*(-?\d+(?:\.\d+)?)\s*(>=|<=|>|<|==)\s*([a-z][a-z0-9_.]*)\s*=\s*(-?\d+(?:\.\d+)?)/gi;
  for (const match of rationale.matchAll(numericComparisons)) {
    const lhs = Number(match[2]);
    const rhs = Number(match[5]);
    const op = match[3];
    const trueComparison = op === '>' ? lhs > rhs : op === '<' ? lhs < rhs :
      op === '>=' ? lhs >= rhs : op === '<=' ? lhs <= rhs : lhs === rhs;
    if (!trueComparison) {
      semanticWarnings.push(`Model rationale contains a false numeric claim: ${match[0]}. This requires human evidence review.`);
    }
  }
  const commitTurn = commit?.provider_turn ?? Infinity;
  const postCommitCitations = events.filter((event) =>
    event.provider_turn > commitTurn &&
    diagnosisCitations.includes(event.observation.event_id) &&
    ['inspect_config', 'inspect_logs', 'inspect_metrics', 'inspect_dependencies'].includes(event.tool),
  ).map((event) => event.observation.event_id);

  let title: string;
  let summary: string;
  let interpretation: string;
  if (row.status !== 'completed') {
    title = 'No complete, gradeable episode';
    summary = `The attempt ended as ${row.status.replaceAll('_', ' ')}. A transport or generation outcome must not be scored as a reasoning failure.`;
    interpretation = 'Inspect the provider log and original turns. This record does not establish a diagnosis limitation.';
  } else if (g.unsafe_commit === true) {
    title = 'Repair introduced new outages';
    summary = `The committed action introduced ${newOutages ?? 'unquantified'} new outages in the synthetic sandbox.`;
    interpretation = 'This is a remediation safety failure; check the counterfactual observations and replayed committed state.';
  } else if (recoverySuccess === false) {
    title = recoverySafe ? 'Safe but incomplete recovery' : 'Recovery objective not achieved';
    summary = `The selected repair restored ${restored ?? 'an unrecorded number of'} of ${initialAffected ?? 'an unrecorded number of'} initially unavailable services; ${remaining ?? 'an unrecorded number of'} remained unavailable.`;
    interpretation = 'A partial fix is distinct from a new-outage safety failure. Inspect whether a simulation warned the agent before commitment.';
  } else if (exactImpact === false && recoverySuccess === true) {
    title = 'Complete recovery, incomplete impact diagnosis';
    summary = `The agent restored ${restored ?? initialAffected ?? 'all'} initially unavailable services without new outages, but the initial incident report missed ${missing.length} and falsely included ${extra.length} services.`;
    interpretation = 'Operational remediation and exact reconstruction of the initial blast radius are separate evaluated capabilities.';
  } else if (g.root_correct === false) {
    title = 'Incorrect causal diagnosis';
    summary = 'The submitted root-cause class differs from the independently verified incident reference.';
    interpretation = 'Compare the agent-visible observations and recorded final answer; no hidden reasoning is available.';
  } else if (strictlyPassed === true) {
    title = 'Complete recovery and exact diagnosis';
    summary = `The agent matched the initial failed-service set and root cause, and safely restored ${restored ?? initialAffected ?? 'all'} services.`;
    interpretation = 'One successful episode is evidence of this attempt, not a measured reliability rate.';
  } else {
    title = 'Strict evaluation failed';
    summary = 'At least one strict success condition was not satisfied even if the partial score was high.';
    interpretation = 'Review the detailed rubric, any protocol violations, and the replayed task reference.';
  }
  return {
    title, summary, interpretation, strictlyPassed,
    rootCorrect: typeof g.root_correct === 'boolean' ? g.root_correct : row.root_correct,
    exactImpact, recoverySuccess, recoverySafe,
    initialAffected, restored, remaining, newOutages, missing, extra, steps,
    postCommitCitations, diagnosisCitations, semanticWarnings,
  };
}
