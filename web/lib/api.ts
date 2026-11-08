export const API = process.env.NEXT_PUBLIC_API_BASE || 'http://127.0.0.1:8000';
export type RunFile = {
  name: string;
  records: number;
  updated_utc: string;
  models: string[];
  tasks: string[];
  benchmark_versions?: string[];
  planned_trials?: number | null;
  requests_planned?: number | null;
  condition?: 'agentic';
};
export type Health = {
  status: string;
  version: string;
  key_configured: boolean;
  openrouter_key_configured?: boolean;
  google_key_configured?: boolean;
  anthropic_key_configured?: boolean;
  timestamp_utc: string;
};
export type Task = {
  id: string;
  title: string;
  context: string;
  alert?: string;
  dataset_name?: string;
  original_source_name?: string;
  source_seed?: string;
  dataset_origin?: string;
  source_url?: string;
  documented_facts?: string[];
  model_assumptions?: string[];
  services: number;
  failed: number;
  condition?: 'agentic';
  benchmark_version?: string;
};
export type EvalSummary = {
  model: string;
  completed: number;
  passed: number;
  wrong: number;
  api_errors: number;
  incomplete: number;
  unverified: number;
  exact_pass_rate: number | null;
  mean_partial: number | null;
  pass_power_k: number | null;
  full_trial_groups: number;
  agentic_non_gradeable?: number;
  unsafe_committed_episodes?: number;
};
export type EvidenceRow = {
  model: string;
  actual_model: string;
  task: string;
  trial: number;
  timestamp_utc: string;
  status: string;
  pass: boolean | null;
  score: number | null;
  affected_f1: number | null;
  root_correct: boolean | null;
  fix_correct: boolean | null;
  format_valid: boolean | null;
  latency_s: number | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  reasoning_tokens: number | null;
  finish_reason: string;
  prompt_verified: boolean | null;
  grade_verified: boolean | null;
  reference_verified: boolean | null;
  warnings: string;
  condition?: 'agentic';
  unsafe_commit?: boolean | null;
  recovery_success?: boolean | null;
  tool_calls?: number | null;
};
export type RunInfo = {
  run: string;
  expected_trials: number;
  expected_trials_source?: 'explicit' | 'recorded-at-launch' | 'inferred-from-records';
  run_manifest?: Record<string, unknown> | null;
  benchmark_versions?: string[];
  summary: EvalSummary[];
  rows: EvidenceRow[];
  record_count: number;
  counts: {
    completed: number;
    api_errors: number;
    incomplete: number;
    unverified: number;
    agentic_non_gradeable?: number;
    unsafe_committed_episodes?: number;
    human_reviews_verified?: number;
    human_reviews_pending?: number;
  };
};
export type NodeInfo = {
  id: string;
  needs_all: string[];
  needs_any: string[];
  needs_at_least?: { count: number; of: string[] };
};
export type Case = {
  id: string;
  title: string;
  context: string;
  semantics: string;
  facts: {
    topology: NodeInfo[];
    [key: string]: unknown;
  };
  provenance?: {source_url?:string; documented_facts?:string[]; reconstructed_elements?:string[]; origin?:string;measurement_note?:string};
  hypotheses: {
    id: string;
    description: string;
  }[];
  actions: {
    id: string;
    cost: number;
    meaning: string;
  }[];
};
export type TaskDetail = {
  case: Case;
  prompt: string;
  reference: {
    failed_services: string[];
    root_cause: string;
    fix_id: string;
  };
  direct_failed_services: string[];
  audit: {
    actions: Record<
      string,
      {
        cost: number;
        failed_after: string[];
        direct_failed_after: string[];
        full_recovery: boolean;
      }
    >;
    [key: string]: unknown;
  };
};
export type TrialDetail = {
  human_review?: { status: string; reviewer: string; notes: string; updated_utc?: string } | null;
  index: number;
  record: Record<string, unknown>;
  audit: {
    status: string;
    warnings: string[];
    prompt_sha_matches: boolean | null;
    stored_grade_matches: boolean | null;
    reference_matches: boolean | null;
    grade: Record<string, unknown> | null;
    expected: Record<string, unknown> | null;
  };
  diagnosis: {
    predicted: {
      failed_services: string[];
      root_cause?: string;
      root_cause_id?: string;
      root_cause_explanation?: string;
      fix_id: string;
    } | null;
    expected: {
      failed_services: string[];
      root_cause?: string;
      root_cause_id?: string;
      root_cause_explanation?: string;
      fix_id: string;
    };
    missed_services: string[];
    extra_services: string[];
    can_parse: boolean;
  } | null;
  visible_reasoning_note: string;
};
export type RunStatus = {
  id?: string;
  status: 'idle' | 'running' | 'stopping' | 'stopped' | 'finished' | 'error';
  return_code?: number;
  output_file?: string;
  started_utc?: string;
  elapsed_seconds?: number | null;
  log?: string;
  requests_planned?: number;
  requests_started?: number;
  requests_finished?: number;
  records_saved?: number;
  current_request?: string | null;
  condition?: 'agentic';
};
export type AgentEvent = {
  tool: string;
  arguments: Record<string, unknown>;
  raw_model_output: string;
  provider_turn: number;
  timestamp_utc?: string;
  provider_elapsed_seconds?: number;
  observation: { event_id: string; tool: string; result: Record<string, unknown> };
};
export async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`, { cache: 'no-store' });
  if (!res.ok) {
    let detail = '';
    try {
      const x = await res.json();
      detail = typeof x.detail === 'string' ? x.detail : JSON.stringify(x.detail);
    } catch {}
    throw new Error(detail || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}
export async function postJSON<T>(path: string, data: unknown): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    let detail = '';
    try {
      const x = await res.json();
      detail = typeof x.detail === 'string' ? x.detail : JSON.stringify(x.detail);
    } catch {}
    throw new Error(detail || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}
