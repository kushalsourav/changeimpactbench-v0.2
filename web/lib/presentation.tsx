'use client';
import {
  Activity,
  FlaskConical,
  GitBranch,
  LayoutDashboard,
  Network
} from 'lucide-react';
import type { RunFile, Task, AgentEvent } from './api';
export type Page = 'overview' | 'lab' | 'control' | 'analysis';
export type AgenticComparison = {
  task_id: string;
  benchmark_version: string;
  scope: string;
  groups: Array<{
    model: string;
    benchmark_version: string;
    temperature: number | null;
    max_tokens: number | null;
    reasoning_effort: string | null;
    episodes: number;
    completed: number;
    strict_passes: number;
    strict_pass_rate_completed: number | null;
    incomplete_repairs: number;
    complete_safe_repairs: number;
    initial_impact_errors: number;
    root_cause_errors: number;
    repair_selection_errors: number;
    protocol_error_episodes: number;
    unsafe_commits: number;
    api_errors: number;
    generation_incomplete: number;
    other_non_gradeable: number;
    unverified: number;
    human_verified: number;
    evidence: Array<{ run: string; index: number; status: string; human_review: string }>;
  }>;
};
export type ChartRow = {
  name: string;
  model: string;
  pass: number | null;
  partial: number | null;
  count: number;
  passK: number | null;
};
export const CHART_FONT = { fontFamily: 'Roboto, system-ui, sans-serif', fontSize: 12, fill: '#5F6368' };
export const chartLabel = (value: string) => (value.length > 17 ? `${value.slice(0, 16)}…` : value);
export const NAV: { id: Page; label: string; icon: typeof Activity }[] = [
  { id: 'overview', label: 'Research overview', icon: LayoutDashboard },
  { id: 'lab', label: 'Incident lab', icon: Network },
  { id: 'control', label: 'Run a test', icon: FlaskConical },
  { id: 'analysis', label: 'Episode evidence', icon: GitBranch },
];
export const desc: Record<Page, string> = {
  overview: 'Verified findings and model comparisons, all on screen.',
  lab: 'Understand the reported incident and its modeled dependency graph.',
  control: 'Launch a bounded agent evaluation with explicit approval.',
  analysis: 'What the agent did, what the sandbox observed, and how independent replay checked it.',
};
export const p100 = (v: number | null | undefined) => (v == null ? 'N/A' : `${(v * 100).toFixed(1)}%`);
export const niceTitle = (value: string) =>
  value.replaceAll('-', ' ').replace(/\b\w/g, (c) => c.toUpperCase());
export const modelDisplay = (id: string, advertised?: string) => {
  if (id.startsWith('google-ai-studio/')) return 'Google AI Studio · ' + niceTitle(id.slice('google-ai-studio/'.length));
  if (advertised && advertised.trim()) return advertised.replace(/\s*\(free\)\s*$/i, '').trim();
  const [provider, raw = id] = id.replace(/:free$/, '').split('/');
  const brands: Record<string, string> = {
    nvidia: 'NVIDIA',
    google: 'Google',
    cohere: 'Cohere',
    liquid: 'Liquid AI',
    'dots-studio': 'Dots Studio',
    thinkingmachines: 'Thinking Machines',
  };
  return `${brands[provider] || niceTitle(provider)} · ${niceTitle(raw)}`;
};
export const short = (model: string) => modelDisplay(model).split(' · ').at(-1) || model;
/** Human-first labels are presentation only; frozen task IDs remain in every record. */
export const INCIDENT_NAMES: Record<string, string> = {
  RW01V4: 'GitHub 2018 · MySQL failover',
  RW01V3: 'GitHub 2018 · MySQL failover',
  RW02V4: 'Cloudflare 2022 · Routing outage',
  RW02V3: 'Cloudflare 2022 · Routing outage',
  RW03V4: 'Cloudflare 2019 · WAF regex outage',
  RW03V3: 'Cloudflare 2019 · WAF regex outage',
  RW04V4: 'Cloudflare 2020 · Backbone routing',
  RW05V4: 'Cloudflare 2023 · Control plane',
  RW06V4: 'Cloudflare 2025 · Workers KV',
};
export const incidentName = (id: string) => INCIDENT_NAMES[id] || id;
export const incidentLabel = (id: string) => `${incidentName(id)} (${id})`;
export const taskDisplay = (id: string, tasks: Task[]) => {
  const t = tasks.find((x) => x.id === id);
  return t ? `${incidentLabel(id)} · ${t.services} services` : incidentLabel(id);
};
export const benchmarkLabel = (v?: string) => {
  if (!v) return 'Version not recorded';
  const match = v.match(/-(v\d+)-langgraph-(v\d+)$/i);
  return match ? `Benchmark ${match[1]} · LangGraph ${match[2]}` : v;
};
/** The filename remains a title/tooltip for reproducibility, never the visible label. */
export const runLabel = (r: RunFile): string => {
  const incident = r.tasks?.length ? r.tasks.map(incidentName).join(' + ') : 'Incident not recorded';
  const model = r.models?.length === 1 ? short(r.models[0]) : `${r.models?.length || 0} models`;
  const stamp = r.updated_utc ? new Date(r.updated_utc) : null;
  const when = stamp && !Number.isNaN(stamp.getTime())
    ? stamp.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    : 'date unavailable';
  return `${incident} · ${model} · ${when}`;
};
export const runDisplay = runLabel;
export const date = (v?: string) => (v ? new Date(v).toLocaleString() : 'Not recorded');
export const GRAPH_TASKS = ['RW01V4', 'RW02V4', 'RW03V4', 'RW04V4', 'RW05V4', 'RW06V4'];
export const isGraphTask = (id: string) => GRAPH_TASKS.includes(id) || ['RW01V3', 'RW02V3', 'RW03V3'].includes(id);
export const isAgenticTask = (id: string) => isGraphTask(id);
export const agentTraceItems = (record: Record<string, unknown>) => {
  const accepted = ((record.trajectory || []) as AgentEvent[]).map((event) => ({
    kind: 'accepted' as const,
    turn: event.provider_turn,
    event,
  }));
  const turns = (record.turns || []) as Array<{
    turn: number;
    raw_model_output: string;
    protocol_error?: string;
    timestamp_utc?: string;
    request_elapsed_seconds?: number;
  }>;
  const attempts = (record.tool_attempts || []) as Array<{
    provider_turn: number;
    rejected_reason?: string;
    tool?: string;
  }>;
  const rejectedAttempts = attempts.filter(a => typeof a.rejected_reason === 'string').map(a => ({
    kind: 'rejected' as const,
    turn: a.provider_turn,
    item: {
      ...(turns.find(t => t.turn === a.provider_turn) || { turn:a.provider_turn, raw_model_output:'' }),
      protocol_error: `${a.tool || 'Tool'}: ${a.rejected_reason}`,
    },
  }));
  const rejectedFromTurns = turns.filter(t => typeof t.protocol_error === 'string'
    && !rejectedAttempts.some(a => a.turn === t.turn)).map(item => ({
    kind: 'rejected' as const,
    turn: item.turn,
    item,
  }));
  return [...accepted, ...rejectedAttempts, ...rejectedFromTurns].sort((a,b) => a.turn - b.turn);
};

// The live run clock reports server-monotonic elapsed time. Model-request
// duration is a separate metric measured by the Python evaluator.
export const duration = (seconds: number | null | undefined) => {
  if (seconds == null || !Number.isFinite(seconds)) return 'Not recorded';
  const whole = Math.floor(Math.max(0, seconds));
  const hours = Math.floor(whole / 3600);
  const minutes = Math.floor((whole % 3600) / 60);
  const secs = whole % 60;
  return hours > 0
    ? `${hours}h ${String(minutes).padStart(2, '0')}m ${String(secs).padStart(2, '0')}s`
    : `${minutes}m ${String(secs).padStart(2, '0')}s`;
};
export const metric = (v: number | null | undefined, digits = 0) =>
  v == null ? 'N/A' : v.toLocaleString(undefined, { maximumFractionDigits: digits });
export const statusLabel = (v: string) => v.replaceAll('_', ' ').replace(/\b\w/g, (s) => s.toUpperCase());
export const safe = (s: unknown) => (typeof s === 'string' ? s : JSON.stringify(s ?? '', null, 2));
