'use client';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  BarChart,
  Bar,
  ResponsiveContainer,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  LabelList,
  LineChart,
  Line,
} from 'recharts';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BookOpen,
  Check,
  CheckCircle,
  ChevronLeft,
  ChevronRight,
  Clipboard,
  CloudOff,
  Database,
  Download,
  FileCheck2,
  FileJson,
  FileText,
  FlaskConical,
  GitBranch,
  Info,
  LayoutDashboard,
  Menu,
  Minus,
  Network,
  Pause,
  Play,
  RefreshCw,
  Search,
  Settings2,
  Shield,
  Square,
  Sun,
  Moon,
  Terminal,
  TriangleAlert,
  X,
} from 'lucide-react';
import { API, getJSON, postJSON } from '../lib/api';
import type {
  Health,
  RunFile,
  RunInfo,
  EvidenceRow,
  EvalSummary,
  Task,
  TaskDetail,
  TrialDetail,
  RunStatus,
  AgentEvent,
} from '../lib/api';
import { Topology } from '../components/Topology';
import { explainEpisode } from '../lib/episode-analysis';
type Page = 'overview' | 'lab' | 'control' | 'analysis';
type AgenticComparison = {
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
type ChartRow = {
  name: string;
  model: string;
  pass: number | null;
  partial: number | null;
  count: number;
  passK: number | null;
};
const CHART_FONT = { fontFamily: 'Roboto, system-ui, sans-serif', fontSize: 12, fill: '#5F6368' };
const chartLabel = (value: string) => (value.length > 17 ? `${value.slice(0, 16)}…` : value);
const NAV: { id: Page; label: string; icon: typeof Activity }[] = [
  { id: 'overview', label: 'Research overview', icon: LayoutDashboard },
  { id: 'lab', label: 'Incident lab', icon: Network },
  { id: 'control', label: 'Control room', icon: FlaskConical },
  { id: 'analysis', label: 'Execution analysis', icon: GitBranch },
];
const desc: Record<Page, string> = {
  overview: 'Verified findings and model comparisons, all on screen.',
  lab: 'Understand the synthetic incident and its dependency graph.',
  control: 'Launch a bounded agent evaluation with explicit approval.',
  analysis: 'Explanation, full tool trajectory, and independent evidence verification.',
};
const p100 = (v: number | null | undefined) => (v == null ? 'N/A' : `${(v * 100).toFixed(1)}%`);
const niceTitle = (value: string) =>
  value.replaceAll('-', ' ').replace(/\b\w/g, (c) => c.toUpperCase());
const modelDisplay = (id: string, advertised?: string) => {
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
const short = (model: string) => modelDisplay(model).split(' · ').at(-1) || model;
const taskDisplay = (id: string, tasks: Task[]) => {
  const t = tasks.find((x) => x.id === id);
  return t ? `${t.id} — ${t.title}` : id;
};
const benchmarkLabel = (v?: string) => {
  if (!v) return 'Unversioned';
  if (v.startsWith('agentic-')) return `Agentic investigation ${v.slice('agentic-'.length)}`;
  if (v.startsWith('advanced-v')) return `Advanced ${v.slice('advanced-'.length)}`;
  if (v.startsWith('baseline-v')) return `Baseline ${v.slice('baseline-'.length)}`;
  return v;
};
const runDisplay = (r: RunFile) => {
  const version = r.benchmark_versions?.map((v) => benchmarkLabel(v)).join(' / ') || 'Unversioned';
  const tasks = r.tasks.length ? r.tasks.join(', ') : 'No tasks';
  const models = r.models.length === 1 ? short(r.models[0]) : `${r.models.length} models`;
  return `${version} · ${tasks} · ${models} · ${r.records} attempts`;
};
const date = (v?: string) => (v ? new Date(v).toLocaleString() : 'Not recorded');
const isAgenticTask = (id: string) => ['AG08','AG08V2','AG08V3','AG08V4','AG09','AG10','AG11','AG12'].includes(id);
const agentTraceItems = (record: Record<string, unknown>) => {
  const accepted = ((record.trajectory || []) as AgentEvent[]).map((event) => ({
    kind: 'accepted' as const,
    turn: event.provider_turn,
    event,
  }));
  const rejected = ((record.turns || []) as Array<{
    turn: number;
    raw_model_output: string;
    protocol_error?: string;
    timestamp_utc?: string;
    request_elapsed_seconds?: number;
  }>).filter((item) => typeof item.protocol_error === 'string').map((item) => ({
    kind: 'rejected' as const,
    turn: item.turn,
    item,
  }));
  return [...accepted, ...rejected].sort((a, b) => a.turn - b.turn);
};

// The live run clock reports server-monotonic elapsed time. Model-request
// duration is a separate metric measured by the Python evaluator.
const duration = (seconds: number | null | undefined) => {
  if (seconds == null || !Number.isFinite(seconds)) return 'Not recorded';
  const whole = Math.floor(Math.max(0, seconds));
  const hours = Math.floor(whole / 3600);
  const minutes = Math.floor((whole % 3600) / 60);
  const secs = whole % 60;
  return hours > 0
    ? `${hours}h ${String(minutes).padStart(2, '0')}m ${String(secs).padStart(2, '0')}s`
    : `${minutes}m ${String(secs).padStart(2, '0')}s`;
};
const metric = (v: number | null | undefined, digits = 0) =>
  v == null ? 'N/A' : v.toLocaleString(undefined, { maximumFractionDigits: digits });
const statusLabel = (v: string) => v.replaceAll('_', ' ').replace(/\b\w/g, (s) => s.toUpperCase());
const safe = (s: unknown) => (typeof s === 'string' ? s : JSON.stringify(s ?? '', null, 2));
function Status({ value }: { value: string }) {
  const cls = ['completed', 'finished', 'passed'].includes(value)
    ? 'good'
    : ['error', 'failed'].includes(value)
      ? 'bad'
      : ['incomplete_generation', 'empty_generation', 'unverified', 'running', 'stopping'].includes(
            value,
          )
        ? 'warn'
        : 'neutral';
  return (
    <span className={`badge ${cls}`}>
      {cls === 'good' ? (
        <Check size={12} />
      ) : cls === 'bad' ? (
        <X size={12} />
      ) : cls === 'warn' ? (
        <TriangleAlert size={12} />
      ) : (
        <Minus size={12} />
      )}{' '}
      {statusLabel(value)}
    </span>
  );
}
function Panel({
  title,
  description,
  children,
  side,
  footer,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  side?: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>{title}</h2>
          {description && <p>{description}</p>}
        </div>
        {side}
      </div>
      <div className="panel-content">{children}</div>
      {footer && <div className="panel-footer">{footer}</div>}
    </section>
  );
}
function Empty({ title, detail }: { title: string; detail?: string }) {
  return (
    <div className="empty">
      <CloudOff size={24} />
      <strong>{title}</strong>
      {detail && <p>{detail}</p>}
    </div>
  );
}
function Json({ value }: { value: unknown }) {
  return <pre className="block-code">{JSON.stringify(value, null, 2)}</pre>;
}
function Code({ value }: { value: unknown }) {
  const content = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
  return (
    <div className="block-code mono">
      {content.split('\n').map((line, i) => (
        <div className="code-line" key={i}>
          <span className="ln">{i + 1}</span>
          <span>{line || ' '}</span>
        </div>
      ))}
    </div>
  );
}
function Figure({ children, caption }: { children: React.ReactNode; caption: string }) {
  return (
    <>
      <div className="chart">{children}</div>
      <div className="fig-caption">{caption}</div>
    </>
  );
}
/** Exact service tiles derived from the loaded deterministic oracle, never invented counts. */
function IncidentStateStrip({
  title, services, unavailable, caption,
}: {
  title: string;
  services: string[];
  unavailable: string[];
  caption: string;
}) {
  const down = new Set(unavailable);
  return (
    <div className="research-state-card">
      <span className="research-eyebrow">{title}</span>
      <div className="research-state-value">{unavailable.length} down <small>/ {services.length} services</small></div>
      <div className="research-service-cells" role="img" aria-label={`${unavailable.length} of ${services.length} services unavailable`}>
        {services.map((name) => (
          <span key={name} title={`${name}: ${down.has(name) ? 'unavailable' : 'healthy'}`} className={down.has(name) ? 'service-cell-down' : 'service-cell-up'}/>
        ))}
      </div>
      <p className="muted">{caption}</p>
    </div>
  );
}
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="field-group">
      <label>{label}</label>
      {children}
    </div>
  );
}
function Metric({
  label,
  value,
  caption,
  onClick,
}: {
  label: string;
  value: string | number;
  caption: string;
  onClick?: () => void;
}) {
  return (
    <div
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onClick={onClick}
      onKeyDown={(e) => {
        if (onClick && (e.key === 'Enter' || e.key === ' ')) onClick();
      }}
      className={`stat ${onClick ? 'link' : ''} ${['Exact pass rate', 'Mean partial score'].includes(label) ? 'featured' : ''}`}
    >
      <label>{label}</label>
      <strong>{value}</strong>
      <small>{caption}</small>
    </div>
  );
}
function Tabs({
  values,
  value,
  onChange,
}: {
  values: string[];
  value: string;
  onChange: (t: string) => void;
}) {
  return (
    <div className="tabs" role="tablist">
      {values.map((t) => (
        <button
          type="button"
          key={t}
          role="tab"
          aria-selected={t === value}
          className={`tab ${t === value ? 'selected' : ''}`}
          onClick={() => onChange(t)}
        >
          {t}
        </button>
      ))}
    </div>
  );
}
function DownloadLink({ href, label }: { href: string; label: string }) {
  return (
    <a className="button" href={`${API}${href}`} download>
      <Download size={15} />
      {label}
    </a>
  );
}
function Integrity({
  label,
  status,
  detail,
}: {
  label: string;
  status: 'pass' | 'fail' | 'warning';
  detail: string;
}) {
  return (
    <div className="integrity-item">
      <span
        className={
          status === 'pass' ? 'text-success' : status === 'fail' ? 'text-error' : 'text-warning'
        }
      >
        {status === 'pass' ? <CheckCircle size={18} /> : <AlertTriangle size={18} />}
      </span>
      <span>
        {label}
        <small style={{ display: 'block' }}>{detail}</small>
      </span>
      <Status value={status === 'pass' ? 'passed' : status === 'fail' ? 'failed' : 'unverified'} />
    </div>
  );
}
function Table({
  rows,
  onSelect,
}: {
  rows: (EvidenceRow & {
    index: number;
  })[];
  onSelect: (index: number) => void;
}) {
  const [sort, setSort] = useState<'task' | 'model' | 'score'>('task');
  const [ascending, setAscending] = useState(true);
  const [page, setPage] = useState(0);
  const [compact, setCompact] = useState(false);
  const ordered = useMemo(
    () =>
      [...rows].sort((a, b) => {
        const av = sort === 'score' ? (a.score ?? -1) : String(a[sort]);
        const bv = sort === 'score' ? (b.score ?? -1) : String(b[sort]);
        const d =
          typeof av === 'number' && typeof bv === 'number'
            ? av - bv
            : String(av).localeCompare(String(bv));
        return ascending ? d : -d;
      }),
    [rows, sort, ascending],
  );
  const order = (key: typeof sort) => {
    setPage(0);
    if (key === sort) setAscending((v) => !v);
    else {
      setSort(key);
      setAscending(true);
    }
  };
  const last = Math.max(0, Math.ceil(ordered.length / 10) - 1);
  const current = Math.min(page, last);
  return (
    <>
      <div className="toolbar">
        <span className="muted">
          {ordered.length} records · page {current + 1} of {last + 1}
        </span>
        <div className="grow" />
        <label>
          <input type="checkbox" checked={compact} onChange={(e) => setCompact(e.target.checked)} />{' '}
          Compact columns
        </label>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>
                <button className="button" onClick={() => order('task')}>
                  Task
                </button>
              </th>
              <th>
                <button className="button" onClick={() => order('model')}>
                  Model
                </button>
              </th>
              <th>Trial</th>
              <th>Status</th>
              <th className="num">
                <button className="button" onClick={() => order('score')}>
                  Score
                </button>
              </th>
              {!compact && (
                <>
                  <th>Root</th>
                  <th>Repair</th>
                </>
              )}
              <th>Evidence</th>
            </tr>
          </thead>
          <tbody>
            {ordered.slice(current * 10, current * 10 + 10).map((r) => (
              <tr
                className="clickable"
                tabIndex={0}
                key={r.index}
                onClick={() => onSelect(r.index)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') onSelect(r.index);
                }}
              >
                <td className="mono">{r.task}</td>
                <td title={r.model}>{short(r.model)}</td>
                <td>{r.trial}</td>
                <td>
                  <Status value={r.status} />
                </td>
                <td className="num">{p100(r.score)}</td>
                {!compact && (
                  <>
                    <td>
                      {r.root_correct == null ? '—' : r.root_correct ? 'Correct' : 'Incorrect'}
                    </td>
                    <td>{r.fix_correct == null ? '—' : r.fix_correct ? 'Correct' : 'Incorrect'}</td>
                  </>
                )}
                <td>
                  <button
                    className="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelect(r.index);
                    }}
                  >
                    Open <ArrowRight size={13} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!ordered.length && (
          <Empty
            title="No matching records"
            detail="Choose a completed run or change the filter."
          />
        )}
      </div>
      <div className="toolbar" style={{ justifyContent: 'flex-end', marginTop: 12 }}>
        <button className="button" disabled={current <= 0} onClick={() => setPage(current - 1)}>
          <ChevronLeft size={16} />
          Previous
        </button>
        <button className="button" disabled={current >= last} onClick={() => setPage(current + 1)}>
          Next <ChevronRight size={16} />
        </button>
      </div>
    </>
  );
}
export default function Home() {
  const [page, setPage] = useState<Page>('overview'),
    [collapsed, setCollapsed] = useState(false),
    [dark, setDark] = useState(false);
  const [health, setHealth] = useState<Health | null>(null),
    [runs, setRuns] = useState<RunFile[]>([]),
    [run, setRun] = useState(''),
    [info, setInfo] = useState<RunInfo | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]),
    [task, setTask] = useState<TaskDetail | null>(null),
    [nodeId, setNodeId] = useState(''),
    [previewActionId, setPreviewActionId] = useState<string | null>(null),
    [repairState, setRepairState] = useState<'before' | 'after'>('before'),
    [labMode, setLabMode] = useState<'actual' | 'whatif'>('actual'),
    [labSideView, setLabSideView] = useState<'service' | 'reviewer'>('service');
  const [recordIndex, setRecordIndex] = useState(0),
    [trial, setTrial] = useState<TrialDetail | null>(null),
    [analysisTab, setAnalysisTab] = useState('Explanation'),
    [expandedEvent, setExpandedEvent] = useState('');
  const [loading, setLoading] = useState(false),
    [error, setError] = useState(''),
    [search, setSearch] = useState(''),
    [filter, setFilter] = useState(''),
    [modelFilter, setModelFilter] = useState('all');
  const [models, setModels] = useState<
      {
        id: string;
        name: string;
      }[]
    >([]),
    [catalogError, setCatalogError] = useState(''),
    [catalogLoading, setCatalogLoading] = useState(false),
    [catalogLoaded, setCatalogLoaded] = useState(false),
    [catalogFilter, setCatalogFilter] = useState(''),
    [flowNotice, setFlowNotice] = useState(''),
    [selectedModels, setSelectedModels] = useState<string[]>([]),
    [selectedTasks, setSelectedTasks] = useState(['T08', 'T09']);
  const [condition, setCondition] = useState<'single-turn' | 'agentic'>('single-turn');
  const [comparisonTask, setComparisonTask] = useState('AG08V4');
  const [crossRun, setCrossRun] = useState<AgenticComparison | null>(null);
  const [reviewer, setReviewer] = useState('');
  const [reviewNotes, setReviewNotes] = useState('');
  const [reviewStatus, setReviewStatus] = useState<'uncertain' | 'verified' | 'needs_revision'>('uncertain');
  const [reviewChecks, setReviewChecks] = useState([false, false, false]);
  const [reviewBusy, setReviewBusy] = useState(false);
  const [reviewMessage, setReviewMessage] = useState('');
  const [trialCount, setTrialCount] = useState(1),
    [maxTokens, setMaxTokens] = useState(8000),
    [effort, setEffort] = useState('low'),
    [temperature, setTemperature] = useState(0),
    [delay, setDelay] = useState(4),
    [approved, setApproved] = useState(false);
  const [job, setJob] = useState<RunStatus>({ status: 'idle' }),
    [starting, setStarting] = useState(false),
    [themeLoaded, setThemeLoaded] = useState(false);
  // Smooth one-second display between 3-second server polls. Never keep a
  // stale timer ticking indefinitely after backend connectivity is lost.
  const [clockNowMs, setClockNowMs] = useState(0);
  const [jobUpdatedMs, setJobUpdatedMs] = useState(0);
  const handledTerminalJob = useRef<string | null>(null);
  const pendingEvidence = useRef<{ run: string; index: number } | null>(null);
  const runFetchSequence = useRef(0);
  const taskFetchSequence = useRef(0);
  const recordFetchSequence = useRef(0);

  // The saved header experiment + active record are the sole task selector.
  const taskId = info?.run === run ? info.rows[recordIndex]?.task || '' : '';

  const selectPage = (value: Page) => {
    setPage(value);
  };
  const refreshRuns = useCallback(async () => {
    try {
      const list = await getJSON<RunFile[]>('/api/runs');
      setRuns(list);
      setRun((old) => (old && list.some((r) => r.name === old) ? old : list[0]?.name || ''));
    } catch (e) {
      setError(`Could not reach FastAPI: ${String(e)}`);
    }
  }, []);
  const refreshRun = useCallback(async () => {
    // Ignore an older response if the user selected a different experiment.
    const sequence = ++runFetchSequence.current;
    if (!run) {
      setInfo(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setInfo(null);
    try {
      const next = await getJSON<RunInfo>(`/api/runs/${encodeURIComponent(run)}`);
      if (sequence !== runFetchSequence.current) return;
      setInfo(next);
      setError('');
    } catch (e) {
      if (sequence !== runFetchSequence.current) return;
      setError(String(e));
      setInfo(null);
    } finally {
      if (sequence === runFetchSequence.current) setLoading(false);
    }
  }, [run]);
  useEffect(() => {
    getJSON<Health>('/api/health')
      .then(setHealth)
      .catch(() => setHealth(null));
    getJSON<Task[]>('/api/tasks')
      .then(setTasks)
      .catch((e) => setError(String(e)));
    refreshRuns();
  }, [refreshRuns]);
  useEffect(() => {
    refreshRun();
  }, [refreshRun]);
  useEffect(() => {
    // A new run cannot reuse trial indices or details from the prior run.
    setRecordIndex(0);
    setTrial(null);
    setReviewMessage('');
  }, [run]);
  useEffect(() => {
    if (info && pendingEvidence.current?.run === info.run) {
      setRecordIndex(pendingEvidence.current.index);
      pendingEvidence.current = null;
    }
  }, [info]);
  useEffect(() => {
    setReviewMessage('');
    setReviewStatus('uncertain');
    setReviewChecks([false, false, false]);
    setReviewer('');
    setReviewNotes('');
  }, [run, recordIndex]);
  useEffect(() => {
    if (isAgenticTask(taskId)) setComparisonTask(taskId);
  }, [taskId]);
  useEffect(() => {
    if (page !== 'overview') return;
    let alive = true;
    getJSON<AgenticComparison>(`/api/agentic/comparison?task_id=${encodeURIComponent(comparisonTask)}`)
      .then((value) => { if (alive) setCrossRun(value); })
      .catch(() => { if (alive) setCrossRun(null); });
    return () => { alive = false; };
  }, [page, comparisonTask, runs]);
  useEffect(() => {
    const sequence = ++taskFetchSequence.current;
    setTask(null);
    setNodeId('');
    setPreviewActionId(null);
    setRepairState('before');
    setLabMode('actual');
    setLabSideView('service');
    if (!taskId) return;
    getJSON<TaskDetail>(`/api/tasks/${encodeURIComponent(taskId)}`)
      .then((data) => {
        if (sequence === taskFetchSequence.current) setTask(data);
      })
      .catch((e) => {
        if (sequence === taskFetchSequence.current) setError(String(e));
      });
  }, [taskId]);
  useEffect(() => {
    // Saved episodes can share a task ID. Never carry a previous episode's
    // repair preview or selected node into a newly selected record.
    setNodeId('');
    setPreviewActionId(null);
    setRepairState('before');
    setLabMode('actual');
    setLabSideView('service');
  }, [run, recordIndex]);
  useEffect(() => {
    const sequence = ++recordFetchSequence.current;
    setTrial(null);
    if (!run || !info || recordIndex >= info.record_count) return;
    getJSON<TrialDetail>(`/api/runs/${encodeURIComponent(run)}/records/${recordIndex}`)
      .then((data) => {
        if (sequence === recordFetchSequence.current) setTrial(data);
      })
      .catch((e) => {
        if (sequence === recordFetchSequence.current) setError(String(e));
      });
  }, [info, recordIndex, run]);
  useEffect(() => {
    if (job.status !== 'running' && job.status !== 'stopping') return;
    setClockNowMs(Date.now());
    const timer = window.setInterval(() => setClockNowMs(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [job.status]);
  useEffect(() => {
    if (page !== 'control' && job.status !== 'running' && job.status !== 'stopping') return;
    const poll = () =>
      getJSON<RunStatus>('/api/experiment/status')
        .then((s) => {
          setJobUpdatedMs(Date.now());
          setJob(s);
          // A finished job is handled only once. Repeated polling must never
          // override a manually selected historical experiment.
          const terminal = ['finished', 'error', 'stopped'].includes(s.status);
          if (terminal && s.id && handledTerminalJob.current !== s.id) {
            handledTerminalJob.current = s.id;
            void refreshRuns();
            if (s.status === 'finished' && s.output_file) {
              setRun(s.output_file);
              setFlowNotice(
                `Experiment finished. ${s.records_saved ?? 0} saved records are ready for explanation and independent verification.`,
              );
            } else if (s.status === 'stopped') {
              setFlowNotice(
                `Experiment stopped. ${s.records_saved ?? 0} completed attempts remain saved; this is not a complete run.`,
              );
            } else if (s.status === 'error') {
              setError('Experiment failed. Inspect the execution log and saved attempts.');
            }
          }
        })
        .catch(() => {});
    poll();
    const tid = setInterval(poll, 3000);
    return () => clearInterval(tid);
  }, [page, job.status, refreshRuns]);
  useEffect(() => {
    if (page === 'control')
      getJSON<Health>('/api/health')
        .then(setHealth)
        .catch(() => setHealth(null));
  }, [page]);
  useEffect(() => {
    setThemeLoaded(true);
  }, []);
  useEffect(() => {
    if (themeLoaded) document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  }, [dark, themeLoaded]);
  const chooseTrial = (index: number) => {
    setRecordIndex(index);
    setAnalysisTab('Explanation');
    setPage('analysis');
  };
  const openSavedEvidence = (filename: string, index: number) => {
    pendingEvidence.current = { run: filename, index };
    setRun(filename);
    if (run === filename) setRecordIndex(index);
    setAnalysisTab('Explanation');
    setPage('analysis');
  };
  const loadModels = useCallback(async () => {
    setCatalogError('');
    setCatalogLoading(true);
    try {
      const catalog = await getJSON<{ id: string; name: string }[]>('/api/models');
      setModels(
        [...catalog].sort((a, b) =>
          modelDisplay(a.id, a.name).localeCompare(modelDisplay(b.id, b.name)),
        ),
      );
      setCatalogLoaded(true);
    } catch (e) {
      setCatalogError(String(e));
    } finally {
      setCatalogLoading(false);
    }
  }, []);
  useEffect(() => {
    if (page === 'control' && !catalogLoaded && !catalogLoading && !catalogError) void loadModels();
  }, [page, catalogLoaded, catalogLoading, catalogError, loadModels]);
  const launch = async () => {
    setError('');
    setFlowNotice('');
    setStarting(true);
    try {
      const r = await postJSON<{
        output_file: string;
        requests_planned: number;
        started_utc: string;
        elapsed_seconds: number;
        condition?: 'single-turn' | 'agentic';
      }>('/api/experiment/start', {
        models: selectedModels,
        tasks: selectedTasks,
        trials: trialCount,
        max_tokens: maxTokens,
        reasoning_effort: effort,
        temperature,
        delay,
        confirm: approved,
        condition,
      });
      setJobUpdatedMs(Date.now());
      setClockNowMs(Date.now());
      setJob({
        status: 'running',
        output_file: r.output_file,
        requests_planned: r.requests_planned,
        started_utc: r.started_utc,
        elapsed_seconds: r.elapsed_seconds,
        condition: r.condition,
      });
      setApproved(false);
    } catch (e) {
      setError(String(e));
    } finally {
      setStarting(false);
    }
  };
  const stop = async () => {
    if (!window.confirm('Stop the experiment? Completed trials will remain saved.')) return;
    try {
      await postJSON('/api/experiment/stop', {});
      setJob((j) => ({ ...j, status: 'stopping', log: (j.log || '') + '\nStop requested.' }));
    } catch (e) {
      setError(String(e));
    }
  };
  const rows = (info?.rows || []).map((r, index) => ({ ...r, index }));
  const matching = rows.filter(
    (r) =>
      (modelFilter === 'all' || r.model === modelFilter) &&
      `${r.task} ${r.model} ${r.status} ${r.trial}`.toLowerCase().includes(filter.toLowerCase()) &&
      (!search || `${r.task} ${r.model} ${r.trial}`.toLowerCase().includes(search.toLowerCase())),
  );
  const summaries = info?.summary || [];
  const completed = summaries.reduce((v, r) => v + r.completed, 0),
    passed = summaries.reduce((v, r) => v + r.passed, 0),
    apiErrors = summaries.reduce((v, r) => v + r.api_errors, 0),
    incomplete = summaries.reduce((v, r) => v + r.incomplete, 0);
  const avgPartial = completed
    ? summaries.reduce((v, r) => v + (r.mean_partial || 0) * r.completed, 0) / completed
    : null;
  const totalLatency = rows.filter((r) => r.status === 'completed' && r.latency_s != null);
  const avgLatency = totalLatency.length
    ? totalLatency.reduce((n, r) => n + (r.latency_s || 0), 0) / totalLatency.length
    : null;
  const tokens = rows.reduce((n, r) => n + (r.prompt_tokens || 0) + (r.completion_tokens || 0), 0);
  const eligibleReliability = Boolean(info && info.expected_trials >= 2);
  const maxK = eligibleReliability ? summaries.filter((s) => s.pass_power_k != null) : [];
  const comparison: ChartRow[] = summaries.map((m) => ({
    name: chartLabel(short(m.model)),
    model: m.model,
    pass: m.exact_pass_rate == null ? null : Math.round(100 * m.exact_pass_rate),
    partial: m.mean_partial == null ? null : Math.round(100 * m.mean_partial),
    passK: !eligibleReliability || m.pass_power_k == null ? null : Math.round(100 * m.pass_power_k),
    count: m.completed,
  }));
  const latencyByModel = summaries.map((m) => {
    const valid = rows.filter(
      (r) => r.model === m.model && r.latency_s != null && r.status === 'completed',
    );
    return {
      name: short(m.model).slice(0, 16),
      mean: valid.length
        ? Math.round((100 * valid.reduce((n, r) => n + (r.latency_s || 0), 0)) / valid.length) / 100
        : null,
      count: valid.length,
    };
  });
  const usageByModel = summaries.map((m) => {
    const valid = rows.filter(
      (r) => r.model === m.model && (r.prompt_tokens != null || r.completion_tokens != null),
    );
    return {
      name: short(m.model).slice(0, 16),
      input: valid.length ? valid.reduce((n, r) => n + (r.prompt_tokens || 0), 0) : null,
      output: valid.length ? valid.reduce((n, r) => n + (r.completion_tokens || 0), 0) : null,
      count: valid.length,
    };
  });
  const taskRows = tasks
    .filter((t) => rows.some((r) => r.task === t.id))
    .map((t) => ({
      task: t.id,
      values: summaries.map((s) => {
        const subset = rows.filter(
          (r) =>
            r.task === t.id && r.model === s.model && r.status === 'completed' && r.pass !== null,
        );
        return {
          model: s.model,
          total: subset.length,
          rate: subset.length ? subset.filter((r) => r.pass).length / subset.length : null,
          index: subset[0]?.index,
        };
      }),
    }));
  const selected = rows.find((r) => r.index === recordIndex);
  const activeLabTaskId = taskId || undefined;
  // A recorded agent commitment is the default after-state. A manual counterfactual
  // preview is explicitly separate and never mistaken for what the agent did.
  const validLabRecord = trial?.index === recordIndex &&
    trial?.record?.task_id === activeLabTaskId && info?.run === run;
  const labCommittedAction = validLabRecord && isAgenticTask(activeLabTaskId || '')
    ? ((trial?.record?.committed_effect as { action_id?: string } | undefined)?.action_id || '')
    : '';
  const actionId = labMode === 'actual' ? labCommittedAction : (previewActionId || '');
  const recordedPreview = labMode === 'actual' && Boolean(labCommittedAction);
  const recordedCommitState = validLabRecord && trial?.record?.committed_effect &&
    typeof trial.record.committed_effect === 'object'
    ? (trial.record.committed_effect as { action_id?: string; unavailable_after?: string[] })
    : null;
  // A stale task response must never display under a newly selected run.
  const labTask = task?.case.id === activeLabTaskId ? task : null;
  const agentEvents = ((trial?.record?.trajectory || []) as AgentEvent[]);
  const commitEvent = agentEvents.find((event) => event.tool === 'apply_repair');
  const committedAction = commitEvent?.arguments?.action_id;
  const matchedSimulation = [...agentEvents].reverse().find((event) =>
    event.tool === 'simulate_repair' && event.arguments?.action_id === committedAction,
  );
  const simulatedRemaining = matchedSimulation ? Number(matchedSimulation.observation.result.unavailable_after_count) : null;
  const committedRemaining = commitEvent ? Number(commitEvent.observation.result.unavailable_after_count) : null;
  const decisionMiss = simulatedRemaining !== null && simulatedRemaining > 0 && committedAction != null;
  // Agentic episodes issue one provider request per tool turn, NOT one per task.
  const plan = selectedModels.length * selectedTasks.length * trialCount * (condition === 'agentic' ? 24 : 1);
  const readyToRun = Boolean(
    health?.key_configured &&
    selectedModels.length &&
    selectedTasks.length &&
    (condition !== 'agentic' || (selectedModels.length === 1 && selectedTasks.length === 1 && isAgenticTask(selectedTasks[0]) && trialCount === 1)) &&
    plan > 0 &&
    plan <= 45 &&
    trialCount >= 1 &&
    trialCount <= 5 &&
    maxTokens >= 512 &&
    maxTokens <= 16000 &&
    delay >= 3 &&
    delay <= 30 &&
    temperature >= 0 &&
    temperature <= 1,
  );
  const shownModels = models.filter((m) =>
    `${modelDisplay(m.id, m.name)} ${m.id}`.toLowerCase().includes(catalogFilter.toLowerCase()),
  );
  const inProgress = job.status === 'running' || job.status === 'stopping';
  // Server time is authoritative. Interpolate for up to 6 seconds between
  // polls so that disconnected browsers don't display invented live time.
  const clockLagMs = jobUpdatedMs ? Math.max(0, clockNowMs - jobUpdatedMs) : 0;
  const elapsedLive =
    job.elapsed_seconds == null
      ? null
      : job.elapsed_seconds + (inProgress ? Math.min(clockLagMs, 6000) / 1000 : 0);
  const clockStale = Boolean(inProgress && jobUpdatedMs && clockLagMs > 10000);
  const affected = labTask?.reference.failed_services || [];
  const repairs = labTask?.audit.actions || {};
  const repair = actionId ? repairs[actionId] : undefined;
  const shownDown = repairState === 'after' && recordedPreview && Array.isArray(recordedCommitState?.unavailable_after)
    ? recordedCommitState.unavailable_after
    : repairState === 'after' && repair ? repair.failed_after : affected;
  const directFailures =
    repairState === 'after' && repair
      ? repair.direct_failed_after || []
      : labTask?.direct_failed_services || [];
  const issueCount = rows.filter(
    (r) =>
      r.prompt_verified === false ||
      r.grade_verified === false ||
      r.reference_verified === false ||
      r.warnings,
  ).length;
  const selectedTrialReady = Boolean(selected && trial && trial.index === recordIndex &&
    trial.record.task_id === selected.task && info?.run === run);
  const explanation = selectedTrialReady && selected && trial && isAgenticTask(selected.task)
    ? explainEpisode(selected, trial) : null;
  const storyServices = labTask?.case.facts.topology.map((n) => n.id) || [];
  const actualEffect = selectedTrialReady ? recordedCommitState : null;
  const storyInitialDown = labTask?.reference.failed_services || [];
  const storyAfterDown = actualEffect && Array.isArray(actualEffect.unavailable_after) ? actualEffect.unavailable_after : null;
  const crossRunCompleted = crossRun?.groups.reduce((n, g) => n + g.completed, 0) || 0;
  const crossRunChart = (crossRun?.groups || []).map((g, index) => ({
    name: `${chartLabel(short(g.model))} ${index + 1}`,
    strict: g.completed ? Math.round(g.strict_passes * 1000 / g.completed) / 10 : null,
    recovery: g.completed ? Math.round(g.complete_safe_repairs * 1000 / g.completed) / 10 : null,
    impact: g.completed ? Math.round((g.completed - g.initial_impact_errors) * 1000 / g.completed) / 10 : null,
  }));
  const counts = {
    validPrompts: rows.filter((r) => r.prompt_verified === true).length,
    validGrades: rows.filter((r) => r.grade_verified === true).length,
    validRefs: rows.filter((r) => r.reference_verified === true).length,
    completed: rows.filter((r) => r.status === 'completed').length,
  };
  return (
    <div className={`shell ${page === 'lab' ? 'shell--incident-lab' : ''}`}>
      <aside className={`rail ${collapsed ? 'collapsed' : ''}`}>
        <div className="brand">
          <div className="brand-symbol">
            <GitBranch size={20} />
          </div>
          <div className="brand-copy">
            <strong>ChangeImpactBench</strong>
            <small>Research & evaluation lab</small>
          </div>
        </div>
        <nav aria-label="Main navigation" className="nav">
          {NAV.map((n) => {
            const Icon = n.icon;
            return (
              <button
                title={n.label}
                aria-current={page === n.id ? 'page' : undefined}
                className={`nav-item ${page === n.id ? 'selected' : ''}`}
                onClick={() => selectPage(n.id)}
                                key={n.id}
              >
                <Icon size={18} />
                <span className="nav-label">
                  {n.label}
                  
                </span>
              </button>
            );
          })}
        </nav>
        <div className="rail-footer">
          <span className={health ? 'text-success' : 'text-error'}>
            {health ? <CheckCircle size={17} /> : <CloudOff size={17} />}
          </span>
          <span>{health ? 'FastAPI connected' : 'Backend unavailable'}</span>
          <button
            className="icon-btn"
            title={collapsed ? 'Expand navigation' : 'Collapse navigation'}
            onClick={() => setCollapsed((v) => !v)}
          >
            {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </button>
        </div>
      </aside>
      <main className="workspace">
        <header className="appbar">
          <button
            className="icon-btn"
            aria-label="Toggle navigation"
            onClick={() => setCollapsed((v) => !v)}
          >
            <Menu size={18} />
          </button>
          <strong className="appbar-context">ChangeImpactBench / {NAV.find((item) => item.id === page)?.label}</strong>
          <div className="grow" />
          <div className="appbar-search">
            <Search size={15} />
            <input
              aria-label="Search evidence"
              placeholder="Find model, trial, task ID"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') { setFilter(search); setAnalysisTab('Explanation'); setPage('analysis'); }
              }}
            />
          </div>
          <select
            aria-label="Select experiment"
            value={run}
            onChange={(e) => {
              setRun(e.target.value);
              setRecordIndex(0);
              setTrial(null);
            }}
          >
            <option value="">Select a saved experiment</option>
            {runs.map((r) => (
              <option key={r.name} value={r.name} title={r.name}>
                {runDisplay(r)}
              </option>
            ))}
          </select>
          <button
            title="Reload evidence"
            className="icon-btn"
            onClick={() => {
              refreshRuns();
              refreshRun();
            }}
          >
            <RefreshCw size={16} />
          </button>
          <button title="Toggle theme" className="icon-btn" onClick={() => setDark((v) => !v)}>
            {dark ? <Sun size={17} /> : <Moon size={17} />}
          </button>
        </header>
        <nav className="mobile-menu" aria-label="Mobile navigation">
          {NAV.map((n) => (
            <button
              key={n.id}
              className={`button ${page === n.id ? 'primary' : ''}`}
              onClick={() => setPage(n.id)}
            >
              {n.label}
            </button>
          ))}
        </nav>
        <div className={`page ${page === 'lab' ? 'page--incident-lab' : ''}`}>
          {page !== 'lab' && page !== 'overview' && (
          <div className="page-heading">
            <div>
              <h1>{NAV.find((n) => n.id === page)?.label}</h1>
              <p>{desc[page]}</p>
              <div className="workflow-next">
                {page === 'overview' ? (
                  <button className="button" onClick={() => setPage('control')}>
                    Configure a new experiment <ArrowRight size={14} />
                  </button>
                ) : page === 'control' ? (
                  <button
                    className="button"
                    onClick={() => setPage('lab')}
                  >
                    Review saved incident <ArrowRight size={14} />
                  </button>
                ) : page === 'analysis' ? (
                  <button className="button" onClick={() => setPage('overview')}>
                    Compare experiment results <ArrowRight size={14} />
                  </button>
                ) : null}
              </div>
            </div>
            <div className="document-meta">
              REPORT / CIB-RESEARCH
              <br />
              SOURCE / {run || 'None selected'}
              <br />
              ENGINE / deterministic Python
              <br />
              BENCHMARK / {info?.benchmark_versions?.join(' / ') || 'Not recorded'}
            </div>
          </div>
          )}
          {page === 'control' && (
            <div className="research-flow" aria-label="Evaluation workflow">
              <span>01 Configure models and tasks</span>
              <ArrowRight size={14} />
              <span>02 Run on FastAPI</span>
              <ArrowRight size={14} />
              <span>03 Read verified explanation</span>
              <ArrowRight size={14} />
              <span>04 Inspect trace & replay</span>
            </div>
          )}
          {page !== 'lab' && flowNotice && (
            <div className="notice" role="status">
              <CheckCircle size={16} />
              <span style={{ flex: 1 }}>{flowNotice}</span>
              <button
                className="button"
                onClick={() => {
                  setAnalysisTab('Explanation');
                  setPage('analysis');
                  setFlowNotice('');
                }}
              >
                View explanation <ArrowRight size={13} />
              </button>
              <button
                className="button"
                aria-label="Dismiss notification"
                onClick={() => setFlowNotice('')}
              >
                <X size={13} />
              </button>
            </div>
          )}
          {page !== 'lab' && error && (
            <div role="alert" className="notice error">
              <AlertTriangle size={18} />
              <span style={{ flex: 1 }}>{error}</span>
              <button className="button" onClick={() => setError('')}>
                Dismiss
              </button>
            </div>
          )}
          {!health && (
            <div className="notice warning">
              <CloudOff size={18} />
              FastAPI is not connected. Start the backend on 127.0.0.1:8000, then reload.
            </div>
          )}
          {loading && (
            <div role="status" className="notice">
              <Info size={16} />
              Loading saved records from FastAPI.
            </div>
          )}
          {page === 'overview' && (
            <>
              <section className="research-hero" aria-label="Research question">
                <div className="research-eyebrow">CHANGEIMPACTBENCH / AI RELIABILITY RESEARCH</div>
                <h1>Can an AI fix an outage and explain what failed?</h1>
                <p>We give AI agents realistic, synthetic software incidents to investigate. They inspect limited evidence, test repairs in a sandbox, and report the cause. An independent Python evaluator checks both the recovery and the report.</p>
                <div className="research-hero-actions">
                  <button className="button primary" onClick={() => setPage('lab')}>Explore the incident <ArrowRight size={15}/></button>
                  <button className="button" onClick={() => setPage('control')}>Run an AI experiment <Play size={14}/></button>
                  <span>Real saved model turns · Synthetic infrastructure · Verifiable outcomes</span>
                </div>
              </section>
              {selected && selectedTrialReady && trial ? (
                <section className="research-feature" aria-label="Featured observed experiment">
                  <div className="research-feature-header">
                    <div><div className="research-eyebrow">OBSERVED EPISODE · {selected.task} · TRIAL {selected.trial}</div><h2>{explanation?.title || (selected.status !== 'completed' ? 'No gradeable model result' : selected.pass ? 'The model met the strict criteria' : 'The response differs from the verified reference')}</h2><p>{modelDisplay(selected.model)} · {selected.status === 'completed' ? 'Completed provider episode' : statusLabel(selected.status)}</p></div>
                    <div className="research-feature-verdict"><span>Independent strict verdict</span><strong className={selected.pass === true ? 'text-success' : selected.pass === false ? 'text-error' : ''}>{selected.pass == null ? 'NOT GRADED' : selected.pass ? 'PASS' : 'FAIL'}</strong><small>Partial credit {p100(selected.score)}</small></div>
                  </div>
                  {explanation ? (
                    <>
                      <div className="research-feature-metrics">
                        <div><span>Recovered after commit</span><strong>{explanation.restored == null ? 'N/A' : `${explanation.restored} / ${explanation.initialAffected ?? '?'}`}</strong><small>Initially unavailable services</small></div>
                        <div><span>Errors in incident report</span><strong>{explanation.missing.length + explanation.extra.length}</strong><small>{explanation.missing.length} missed · {explanation.extra.length} falsely listed</small></div>
                        <div><span>New outages caused</span><strong>{explanation.newOutages ?? 'N/A'}</strong><small>From recorded sandbox commit</small></div>
                      </div>
                      {storyServices.length > 0 && storyAfterDown && (
                        <div className="research-state-comparison">
                          <IncidentStateStrip title="BEFORE · INITIAL INCIDENT" services={storyServices} unavailable={storyInitialDown} caption="Red cells are services the oracle found unavailable before any repair."/>
                          <IncidentStateStrip title="AFTER · ACTUAL AGENT COMMIT" services={storyServices} unavailable={storyAfterDown} caption={`Recorded ${actualEffect?.action_id || 'sandbox'} repair. Green cells are healthy; red cells remain down.`}/>
                        </div>
                      )}
                      <div className="research-story-grid">
                        <div>
                          <h3>What the agent actually did</h3>
                          <div className="research-journey">
                            <div className="research-journey-item"><span className="research-journey-index">01</span><div><strong>Investigated the outage</strong><p>{agentEvents.filter(e=>['read_alert','inspect_config','inspect_dependencies','inspect_logs','inspect_metrics'].includes(e.tool)).length} recorded investigation tool calls; the task's reference answer was hidden from the agent.</p></div></div>
                            {explanation.steps.map((step, i) => (
                              <button key={step.eventId} className="research-journey-item research-journey-link" onClick={() => {setAnalysisTab('Full timeline');setExpandedEvent(step.eventId);setPage('analysis');}}>
                                <span className="research-journey-index">{String(i+2).padStart(2,'0')}</span><div><strong>{step.label === 'Simulated' ? `Tested repair ${step.action}` : `Committed repair ${step.action}`}</strong><p>{step.remaining == null ? 'Effect unavailable in this record' : `${step.remaining} services remain down`} · {step.newOutages ?? '?'} new outages · turn {step.turn} / {step.eventId}</p></div><ArrowRight size={14}/>
                              </button>
                            ))}
                            <div className="research-journey-item"><span className="research-journey-index">{String(explanation.steps.length+2).padStart(2,'0')}</span><div><strong>Submitted the incident report</strong><p>{explanation.missing.length + explanation.extra.length ? `${explanation.missing.length + explanation.extra.length} service classification errors in the original outage inventory.` : explanation.strictlyPassed ? 'Exact initial impact and diagnosis verified.' : 'Check the strict criterion differences in Execution Analysis.'}</p></div></div>
                          </div>
                        </div>
                        <div className="research-interpretation">
                          <h3>What the evaluator found</h3>
                          <p>{explanation.summary}</p>
                          {(explanation.missing.length > 0 || explanation.extra.length > 0) && <div className="research-error-lists">
                            {explanation.missing.length > 0 && <div><span>Actually down, but missed by the agent</span><div className="research-service-links">{explanation.missing.map((name) => <button key={name} type="button" title={`Inspect ${name} in Incident Lab`} onClick={() => { setNodeId(name);setLabMode('actual');setRepairState('before');setLabSideView('service');setPage('lab'); }}>{name} <ArrowRight size={12}/></button>)}</div></div>}
                            {explanation.extra.length > 0 && <div><span>Reported down, but actually healthy</span><div className="research-service-links">{explanation.extra.map((name) => <button key={name} type="button" title={`Inspect ${name} in Incident Lab`} onClick={() => { setNodeId(name);setLabMode('actual');setRepairState('before');setLabSideView('service');setPage('lab'); }}>{name} <ArrowRight size={12}/></button>)}</div></div>}
                          </div>}
                          <p className="research-insight"><strong>Why it matters:</strong> {explanation.interpretation}</p>
                          <p className="muted">Automatic grader and tool-event analysis; human semantic review: {trial.human_review?.status || 'pending'}. One episode is not an estimated failure rate.</p>
                          {selected.task === 'AG08V2' && <p className="muted">Historical AG08V2 instruction/grader ambiguity is documented. Do not compare its score as if it were the same task as v3.</p>}
                          <button className="button primary" onClick={() => {setAnalysisTab('Explanation');setPage('analysis');}}>Inspect the evidence <ArrowRight size={14}/></button>
                        </div>
                      </div>
                    </>
                  ) : (
                    <div className="research-sample-note"><Info size={18}/><span>The recorded outcome is shown without inventing an agentic recovery story for a single-turn or incomplete experiment. Open its original evidence for details.</span></div>
                  )}
                </section>
              ) : <section className="research-feature research-empty-feature"><h2>No saved result selected yet</h2><p>Choose an experiment from the top bar or launch one in Control Room. We do not populate the research dashboard with demonstration scores.</p><button className="button primary" onClick={()=>setPage('control')}>Configure an experiment <ArrowRight size={14}/></button></section>}
              <div className="research-comparison-heading"><div><span className="research-eyebrow">ACROSS EXPERIMENTS</span><h2>Does this behavior repeat across models?</h2><p>Every chart below uses real saved episodes. Different versions and generation settings are never pooled.</p></div></div>
              <Panel title="Model comparison · observed evidence" description="Same task version and model settings only. Real completed episodes are the denominator; provider errors are excluded.">
                <div className="row-gap">
                  <div className="toolbar">
                    <Field label="Benchmark task version">
                      <select aria-label="Compare agentic task version" value={comparisonTask} onChange={(e) => setComparisonTask(e.target.value)}>
                        {tasks.filter((t) => isAgenticTask(t.id)).map((t) => <option key={t.id} value={t.id}>{t.id} · {t.benchmark_version}</option>)}
                      </select>
                    </Field>
                    <div className="grow" />
                    <span className="muted">{crossRun?.groups.reduce((n, g) => n + g.completed, 0) ?? 0} completed · {crossRun?.groups.length ?? 0} model/settings groups</span>
                  </div>
                  {crossRun?.groups.length ? (
                    <>
                      {crossRunCompleted > 1 ? <div className="chart-panels">
                        <div>
                          <h3>Model outcomes</h3>
                          <div className="chart story-chart">
                            <ResponsiveContainer>
                              <BarChart data={crossRunChart} margin={{ top: 12, right: 18, bottom: 45, left: 0 }} barCategoryGap="26%">
                                <CartesianGrid stroke="var(--rule)" vertical={false}/>
                                <XAxis dataKey="name" tick={CHART_FONT} interval={0} angle={-15} height={65} textAnchor="end"/>
                                <YAxis type="number" domain={[0, 100]} unit="%" tick={CHART_FONT}/>
                                <Tooltip formatter={(v, name) => [v == null ? 'N/A' : `${v}%`, name]}/>
                                <Legend wrapperStyle={CHART_FONT}/>
                                <Bar dataKey="strict" name="Strict pass %" fill="var(--primary)" isAnimationActive={false}/>
                                <Bar dataKey="recovery" name="Complete safe recovery %" fill="var(--success)" isAnimationActive={false}/>
                                <Bar dataKey="impact" name="Exact impact inventory %" fill="var(--ink-muted)" isAnimationActive={false}/>
                              </BarChart>
                            </ResponsiveContainer>
                          </div>
                          <p className="fig-caption">Separate measurements; a repair can succeed while the initial outage inventory is wrong. n and model settings appear in the table.</p>
                        </div>
                        <div>
                          <h3>Failure categories · selected task</h3>
                          <div className="story-bars">
                            {[
                              { label: 'Initial impact inventory errors', value: crossRun.groups.reduce((n, g) => n + g.initial_impact_errors, 0) },
                              { label: 'Root-cause classification errors', value: crossRun.groups.reduce((n, g) => n + g.root_cause_errors, 0) },
                              { label: 'Incomplete safe repairs', value: crossRun.groups.reduce((n, g) => n + g.incomplete_repairs, 0) },
                              { label: 'Unsafe commitments', value: crossRun.groups.reduce((n, g) => n + g.unsafe_commits, 0) },
                              { label: 'Protocol error episodes', value: crossRun.groups.reduce((n, g) => n + g.protocol_error_episodes, 0) },
                            ].map((b) => <div key={b.label} className="story-bar-line"><div className="summary-line"><span>{b.label}</span><strong>{b.value}</strong></div><div className="progress"><div style={{ width: `${crossRunCompleted ? b.value * 100 / crossRunCompleted : 0}%`, background: 'var(--primary)' }}/></div></div>)}
                          </div>
                          <p className="fig-caption">Multi-label counts: one episode may appear in more than one category. These are observed outcomes, not projected error rates.</p>
                        </div>
                      </div> : (
                        <div className="research-sample-note">
                          <Info size={17}/>
                          <div><strong>One completed episode is a case study, not a performance estimate.</strong><p>Run independent repeats with the same task version and settings to compare success rates. This single outcome remains accessible below.</p></div>
                        </div>
                      )}
                      <div className="table-wrap">
                        <table>
                          <thead><tr><th>Model / exact settings</th><th className="num">n complete</th><th className="num">Strict pass</th><th className="num">Safe recovery</th><th className="num">Impact errors</th><th className="num">Root errors</th><th className="num">API / incomplete</th></tr></thead>
                          <tbody>{crossRun.groups.map((g, i) => <tr key={`${g.model}-${i}`}>
                            <td><strong>{modelDisplay(g.model)}</strong><small className="muted" style={{display:'block'}}>temp {g.temperature ?? 'N/A'} · tokens {g.max_tokens ?? 'N/A'} · reasoning {g.reasoning_effort ?? 'N/A'}</small></td>
                            <td className="num">{g.completed}</td><td className="num">{g.strict_passes}/{g.completed} · {p100(g.strict_pass_rate_completed)}</td>
                            <td className="num">{g.complete_safe_repairs}/{g.completed}</td><td className="num">{g.initial_impact_errors}</td><td className="num">{g.root_cause_errors}</td><td className="num">{g.api_errors + g.generation_incomplete}</td>
                          </tr>)}</tbody>
                        </table>
                      </div>
                      <div className="row-gap">
                        <h3>Open the original evidence</h3>
                        <div className="toolbar story-evidence-links">
                          {crossRun.groups.flatMap((group) => group.evidence.map((e) => (
                            <button className="button" key={`${e.run}-${e.index}`} onClick={() => openSavedEvidence(e.run, e.index)}>
                              {e.run} · record {e.index + 1} · {e.status} <ArrowRight size={12}/>
                            </button>
                          )))}
                        </div>
                      </div>
                    </>
                  ) : (
                    <Empty title="No verified agentic episodes found for this version" detail="Run an episode in Control Room; saved results will appear here. No sample scores are invented." />
                  )}
                  <p className="muted">{crossRun?.scope || 'Loading version-specific comparison from FastAPI.'} A single episode does not establish repeatability; use at least three trials per model and task when possible.</p>
                </div>
              </Panel>
            </>
          )}
          {page === 'lab' && (
            <>
              {!info || !activeLabTaskId ? (
                <Panel title="Select an experiment" description="Incident Lab follows the experiment chosen in the top bar.">
                  <Empty title="No saved incident selected" detail="Choose a saved experiment from the top bar, or launch one in Control Room. The incident graph will load automatically." />
                </Panel>
              ) : (
                <>
                  <div className="incident-lab-layout">
                    <Panel
                      title="Service topology"
                      description={labTask ? `${activeLabTaskId} · ${labTask.case.facts.topology.length} services · ${affected.length} initially unavailable · reviewer-only reference` : `Loading ${activeLabTaskId} topology`}
                      side={
                        <div className="chipbar" aria-label="Incident repair state">
                          <button className={`button ${repairState === 'before' ? 'primary' : ''}`} onClick={() => setRepairState('before')}>Before outage</button>
                          <button className={`button ${repairState === 'after' ? 'primary' : ''}`} disabled={!actionId} onClick={() => setRepairState('after')}>{labMode === 'actual' ? 'After agent repair' : 'After what-if repair'}</button>
                        </div>
                      }
                    >
                      {rows.length > 1 && (
                        <div className="toolbar incident-attempt-selector">
                          <label htmlFor="lab-attempt">Trial in selected experiment</label>
                          <select
                            id="lab-attempt"
                            aria-label="Trial in selected experiment"
                            value={recordIndex}
                            onChange={(e) => setRecordIndex(Number(e.target.value))}
                          >
                            {rows.map((item) => (
                              <option key={item.index} value={item.index}>
                                {item.task} · {short(item.model)} · trial {item.trial}
                              </option>
                            ))}
                          </select>
                          <button className="button" onClick={() => chooseTrial(recordIndex)}>
                            View analysis <ArrowRight size={14}/>
                          </button>
                        </div>
                      )}
                      {labTask && (
                        <div className="incident-repair-controls">
                          <div className="incident-mode-tabs" role="group" aria-label="Graph evidence mode">
                            <button type="button" className={`button ${labMode === 'actual' ? 'primary' : ''}`} aria-pressed={labMode === 'actual'} onClick={() => { setLabMode('actual'); setPreviewActionId(null); setRepairState('after'); }}>Actual agent execution</button>
                            <button type="button" className={`button ${labMode === 'whatif' ? 'primary' : ''}`} aria-pressed={labMode === 'whatif'} onClick={() => { setLabMode('whatif'); setPreviewActionId(labTask.case.actions[0]?.id || ''); setRepairState('after'); }}>Explore alternative repairs</button>
                          </div>
                          {labMode === 'actual' ? (
                            <p className="incident-mode-note" role="status">
                              <strong>{labCommittedAction ? `Recorded model action: ${labCommittedAction}` : 'No recorded agent repair'}</strong>
                              <span>{labCommittedAction && repairState === 'after' ? `${repair?.failed_after.length ?? 'Unknown'} remain unavailable after the recorded commit.` : 'Choose After agent repair to inspect the model’s committed outcome. No hypothetical repair is being shown.'}</span>
                            </p>
                          ) : (
                            <div className="toolbar incident-repair-selector">
                              <label htmlFor="lab-repair">Hypothetical repair · not executed by the agent</label>
                              <select id="lab-repair" aria-label="Displayed repair: agent commitment or manual counterfactual" value={previewActionId || ''} onChange={(e) => {setPreviewActionId(e.target.value); setRepairState('after');}}>
                                {labTask.case.actions.map((a) => (
                                  <option key={a.id} value={a.id}>Preview {a.id} · cost {a.cost} · {repairs[a.id]?.full_recovery ? 'complete recovery' : 'incomplete recovery'}</option>
                                ))}
                              </select>
                              <strong className="incident-hypothesis-alert" role="status">Counterfactual preview only · {repair?.failed_after.length ?? 'Unknown'} remain down</strong>
                            </div>
                          )}
                        </div>
                      )}
                      {labTask ? (
                        <Topology
                          key={activeLabTaskId}
                          nodes={labTask.case.facts.topology}
                          failed={shownDown}
                          directFailed={directFailures}
                          before={affected}
                          selected={nodeId}
                          onSelect={(id) => { setNodeId(id); setLabSideView('service'); }}
                        />
                      ) : (
                        <Empty title="Loading incident graph" detail="The displayed topology will be verified against the selected task ID." />
                      )}
                    </Panel>
                    <Panel title="Incident inspector" description="Select a node or inspect reference facts">
                      <div className="incident-inspector-tabs" role="tablist" aria-label="Incident inspector">
                        <button
                          type="button"
                          role="tab"
                          id="incident-service-tab"
                          aria-controls="incident-inspector-content"
                          aria-selected={labSideView === 'service'}
                          className={`tab ${labSideView === 'service' ? 'selected' : ''}`}
                          onClick={() => setLabSideView('service')}
                        >
                          Service details
                        </button>
                        <button
                          type="button"
                          role="tab"
                          id="incident-reviewer-tab"
                          aria-controls="incident-inspector-content"
                          aria-selected={labSideView === 'reviewer'}
                          className={`tab ${labSideView === 'reviewer' ? 'selected' : ''}`}
                          onClick={() => setLabSideView('reviewer')}
                        >
                          Reviewer view
                        </button>
                      </div>
                      <div id="incident-inspector-content" role="tabpanel" aria-labelledby={labSideView === 'service' ? 'incident-service-tab' : 'incident-reviewer-tab'} className="incident-inspector-scroll">
                        {labSideView === 'reviewer' ? (
                          labTask ? (
                            <div className="incident-reviewer-content">
                              <p className="muted">Synthetic, reviewer-only oracle. The agent never sees the complete reference graph.</p>
                              <p>{labTask.case.context}</p>
                              <h3>Failure rules</h3>
                              <p>{labTask.case.semantics}</p>
                              <dl className="keyvals">
                                <dt>Initial outages</dt><dd>{labTask.reference.failed_services.length} of {labTask.case.facts.topology.length}</dd>
                                <dt>Reference root cause</dt><dd>{labTask.reference.root_cause}</dd>
                                <dt>Reference repair</dt><dd>{labTask.reference.fix_id}</dd>
                                <dt>Versioned task</dt><dd>{activeLabTaskId}</dd>
                              </dl>
                              <details className="story-raw"><summary>Versioned agent prompt</summary><Code value={labTask.prompt}/></details>
                              <details className="story-raw"><summary>Synthetic configuration (JSON)</summary><Json value={labTask.case.facts}/></details>
                            </div>
                          ) : <Empty title="Loading reference" detail="Reviewer data follows the selected incident." />
                        ) : labTask && nodeId ? (
                          (() => {
                            const node = labTask.case.facts.topology.find((item) => item.id === nodeId);
                            return node ? (
                              <div className="incident-service-detail">
                                <h3>{node.id}</h3>
                                <p><Status value={shownDown.includes(node.id) ? 'failed' : 'completed'} /></p>
                                <dl className="keyvals">
                                  <dt>Required services</dt><dd>{node.needs_all.join(', ') || 'None'}</dd>
                                  <dt>Alternative services</dt><dd>{node.needs_any.join(', ') || 'None'}</dd>
                                  <dt>Quorum requirement</dt><dd>{node.needs_at_least ? `${node.needs_at_least.count} of ${node.needs_at_least.of.join(', ')}` : 'None'}</dd>
                                  <dt>Cause of failure</dt>
                                  <dd>{shownDown.includes(node.id) ? directFailures.includes(node.id) ? 'Local failure' : 'Dependency cascade' : 'Healthy'}</dd>
                                  <dt>Initial state</dt><dd>{affected.includes(node.id) ? 'Unavailable' : 'Healthy'}</dd>
                                  <dt>Displayed state</dt><dd>{shownDown.includes(node.id) ? 'Unavailable' : 'Healthy'}</dd>
                                </dl>
                              </div>
                            ) : <Empty title="Service not found" detail="Select a valid node from the current incident." />;
                          })()
                        ) : (
                          <div className="incident-intro-inspector">
                            <h3>Understand the outage</h3>
                            <p>This is a synthetic {labTask?.case.facts.topology.length || '?'}-service system. {affected.length} services were unavailable initially, caused by local failures and dependency cascades.</p>
                            <div className="incident-inspector-stat"><span>Initially unavailable</span><strong>{affected.length}</strong></div>
                            <div className="incident-inspector-stat"><span>Current graph</span><strong>{repairState === 'before' ? 'Before repair' : recordedPreview ? 'Actual agent repair' : 'What-if simulation'}</strong></div>
                            <p className="muted">Select any service on the diagram to inspect its required dependencies, redundancy rules and state. Reviewer view contains the reference rules and source facts.</p>
                          </div>
                        )}
                      </div>
                    </Panel>
                  </div>
                </>
              )}
            </>
          )}
          {page === 'analysis' && (
            <>
              <div className="toolbar">
                <input aria-label="Filter trials" placeholder="Find task, model or trial" type="search" value={filter} onChange={(e)=>setFilter(e.target.value)}/>
                <select aria-label="Filter by model" value={modelFilter} onChange={(e)=>setModelFilter(e.target.value)}>
                  <option value="all">All models</option>
                  {summaries.map((s)=><option key={s.model} value={s.model}>{modelDisplay(s.model)}</option>)}
                </select>
                <div className="grow"/><span className="muted">{matching.length} records in the selected run</span>
              </div>
              <div className="split-trace analysis-split">
                <Panel title="Saved attempts" description="Open any recorded episode">
                  <div className="trial-list">
                    {matching.map((r)=><button className={`record-button ${recordIndex===r.index?'active':''}`} key={r.index} onClick={()=>{setRecordIndex(r.index);setAnalysisTab('Explanation');}}>
                      <span><strong>{r.task} · trial {r.trial}</strong><small style={{display:'block'}}>{short(r.model)}</small><small className="muted">{r.pass === null ? 'Not gradeable' : r.pass ? 'Strict pass' : 'Strict fail'} · {p100(r.score)}</small></span>
                    </button>)}
                    {!matching.length && <Empty title="No matching attempts"/>}
                  </div>
                </Panel>
                <Panel title="Execution analysis" description={selected ? `${selected.task} · ${modelDisplay(selected.model)} · trial ${selected.trial}` : 'Select an experiment'} side={selected && <Status value={selected.status}/>}>
                  {selected && trial ? <>
                    <Tabs values={['Explanation','Full timeline','Verification']} value={analysisTab} onChange={setAnalysisTab}/>
                    <div className="section-space row-gap">
                      {analysisTab === 'Explanation' ? (
                        <div className="row-gap">
                          <div className="story-verdict">
                            <div><span className="label">Automatically derived from recorded evidence</span><h2>{explanation?.title || (selected.pass ? 'Exact answer verified' : selected.status === 'completed' ? 'Diagnosis differs from reference' : 'Not gradeable')}</h2><p>{explanation?.summary || (selected.status === 'completed' ? 'One or more predicted fields differ from the independent reference. See exact differences below.' : 'The provider did not produce a complete, gradeable response.')}</p></div>
                            <div className="verdict-score"><span className="label">Strict result</span><strong className={selected.pass ? 'text-success' : 'text-error'}>{selected.pass == null ? 'N/A' : selected.pass ? 'PASS' : 'FAIL'}</strong><span className="muted">Partial {p100(selected.score)}</span></div>
                          </div>
                          <div className="analysis-first-insight"><strong>Why this result matters</strong><p>{explanation?.interpretation || 'The strict grade and partial score measure different aspects of the result.'}</p><small>Derived from the recorded agent trajectory and independently recomputed grade. Human interpretation review remains separate.</small></div>
                          <div className="story-metrics">
                            <div><small>Root cause</small><strong>{selected.root_correct == null ? 'N/A' : selected.root_correct ? 'Correct' : 'Incorrect'}</strong></div>
                            <div><small>Initial service F1</small><strong>{p100(selected.affected_f1)}</strong></div>
                            <div><small>Committed repair</small><strong>{selected.fix_correct == null ? 'N/A' : selected.fix_correct ? 'Correct' : 'Incorrect'}</strong></div>
                            <div><small>Recovered</small><strong>{explanation?.restored == null ? 'N/A' : `${explanation.restored}/${explanation.initialAffected ?? '?'}`}</strong></div>
                          </div>
                          {isAgenticTask(selected.task) && (
                            <div className="row-gap">
                              <h3>Decision sequence · click an event to read the raw evidence</h3>
                              {explanation?.steps.length ? <div className="decision-path">
                                {explanation.steps.map((step)=><button className="decision-step" key={step.eventId} onClick={()=>{setAnalysisTab('Full timeline');setExpandedEvent(step.eventId);}}>
                                  <span className="label">TURN {step.turn} · {step.eventId}</span>
                                  <strong>{step.label} {step.action}</strong>
                                  <small>{step.restored ?? '?'} restored · {step.remaining ?? '?'} remaining · {step.newOutages ?? '?'} new outages</small>
                                  <ArrowRight size={14}/>
                                </button>)}
                              </div> : <p className="muted">No simulated or committed repair is present in this trajectory.</p>}
                              {explanation?.steps.some((s)=>s.label==='Simulated'&&s.remaining!==null&&s.remaining>0) && explanation.steps.some((s)=>s.label==='Committed'&&s.remaining!==null&&s.remaining>0) && <p className="notice warning"><AlertTriangle size={15}/>The agent committed incomplete recovery. Check whether the committed action was previously simulated and what feedback was visible.</p>}
                            </div>
                          )}
                          <div className="grid-11">
                            <div className="story-diff"><h3>Missed initially unavailable services</h3>{trial.diagnosis?.missed_services.length ? <ul>{trial.diagnosis.missed_services.map((v)=><li key={v} className="mono">{v}</li>)}</ul> : <p className="muted">None recorded</p>}</div>
                            <div className="story-diff"><h3>Falsely marked unavailable</h3>{trial.diagnosis?.extra_services.length ? <ul>{trial.diagnosis.extra_services.map((v)=><li key={v} className="mono">{v}</li>)}</ul> : <p className="muted">None recorded</p>}</div>
                          </div>
                          <div className="story-diff"><h3>Root cause and repair</h3><dl className="keyvals"><dt>Verified root cause</dt><dd>{trial.diagnosis?.expected?.root_cause || 'N/A'}</dd><dt>Model root cause</dt><dd>{trial.diagnosis?.predicted?.root_cause || 'N/A'}</dd><dt>Verified repair</dt><dd>{trial.diagnosis?.expected?.fix_id || 'N/A'}</dd><dt>Model repair</dt><dd>{trial.diagnosis?.predicted?.fix_id || 'N/A'}</dd></dl></div>
                          {explanation?.postCommitCitations.length ? <div className="notice warning"><Info size={15}/><span>The final diagnosis cites inspection evidence obtained after the sandbox repair ({explanation.postCommitCitations.join(', ')}). Current-state measurements do not necessarily describe the original failure state. Semantic review is required; this flag does not automatically change the score.</span></div> : null}
                          {explanation?.semanticWarnings.map((warning) => <div className="notice warning" key={warning}><Info size={15}/><span>{warning} The deterministic grader score is unchanged; human validation is pending.</span></div>)}
                          {selected.task === 'AG08V2' && <p className="notice warning"><Info size={15}/>Historical task-validity caveat: the v2 alert did not explicitly state full recovery, although the strict grader required it. The v3 instruction resolves this prospectively.</p>}
                          <p className="muted">Only recorded tool observations and deterministic grader comparisons are used. This is not an LLM-generated explanation, hidden chain-of-thought, or proof of a population-level model limitation. Human review: {trial.human_review?.status || 'pending'}.</p>
                          <div className="toolbar"><button className="button primary" onClick={()=>setAnalysisTab('Full timeline')}>Inspect original turns <ArrowRight size={14}/></button><button className="button" onClick={()=>setAnalysisTab('Verification')}>View independent verification</button></div>
                        </div>
                      ) : analysisTab === 'Full timeline' ? (
                        <div className="row-gap">
                          <div className="notice"><Shield size={15}/>Full observable trace. The agent's tool requests and synthetic responses are recorded in order; no hidden reasoning is available.</div>
                          {isAgenticTask(selected.task) ? <>
                            {agentTraceItems(trial.record).map((step,i)=>step.kind==='rejected' ?
                              <details className="agent-event trace-step" key={`rej-${step.turn}-${i}`} defaultOpen={expandedEvent===`rejected-${step.turn}`}>
                                <summary><strong>Turn {step.turn} · rejected request</strong><span className="muted">{step.item.protocol_error}</span></summary>
                                <p className="muted">{date(step.item.timestamp_utc)} · {duration(step.item.request_elapsed_seconds)}</p><Code value={step.item.raw_model_output}/>
                              </details>
                              : <details className="agent-event trace-step" key={step.event.observation.event_id} defaultOpen={expandedEvent===step.event.observation.event_id}>
                                <summary><strong>{step.event.observation.event_id} · {step.event.tool.replaceAll('_',' ')} · turn {step.turn}</strong><span className="muted">{date(step.event.timestamp_utc)} · {duration(step.event.provider_elapsed_seconds)}</span></summary>
                                <h3>Actual model tool request</h3><Json value={{tool:step.event.tool,arguments:step.event.arguments}}/>
                                <h3>Actual sandbox observation</h3><Json value={step.event.observation.result}/>
                                <details><summary className="muted">Raw model message</summary><Code value={step.event.raw_model_output}/></details>
                              </details>)}
                            {agentTraceItems(trial.record).length===0 && <Empty title="No tool events saved" detail="Check the provider metadata below."/>}
                            <details className="story-raw"><summary>Reviewer-only committed state</summary><Json value={trial.record.committed_effect || {committed:false}}/></details>
                          </> : <div className="row-gap"><h3>Single-turn response</h3><Code value={trial.record.raw_output || ''}/><p>Finish reason: {selected.finish_reason || 'N/A'} · latency: {duration(selected.latency_s)}</p></div>}
                          <details className="story-raw"><summary>Exact versioned prompt</summary><Code value={trial.record.prompt || 'Prompt not embedded; see hash audit and task source.'}/></details>
                          <details className="story-raw"><summary>All raw provider turn records and token metadata</summary><Json value={trial.record.turns || [trial.record]}/></details>
                          <button className="button" onClick={()=>setAnalysisTab('Explanation')}>Back to explanation</button>
                        </div>
                      ) : (
                        <div className="row-gap">
                          <div className="notice"><FileCheck2 size={16}/><span>These checks are recomputed by the FastAPI backend from the saved record. Downloads preserve the original evidence. Semantic correctness of the model's written explanation requires separate human review.</span></div>
                          <div className="story-metrics"><div><small>Strict result</small><strong>{selected.pass == null ? 'N/A' : selected.pass?'PASS':'FAIL'}</strong></div><div><small>Partial score</small><strong>{p100(selected.score)}</strong></div><div><small>Automated citations</small><strong>{trial.audit.grade?.evidence_score == null ? 'N/A' : `${trial.audit.grade.evidence_score}/10`}</strong></div><div><small>Human review</small><strong>{trial.human_review?.status || 'Pending'}</strong></div></div>
                          <Integrity label="Prompt SHA-256 matches frozen source" status={trial.audit.prompt_sha_matches===true?'pass':trial.audit.prompt_sha_matches===false?'fail':'warning'}/>
                          <Integrity label="Stored grade matches independent replay" status={trial.audit.stored_grade_matches===true?'pass':trial.audit.stored_grade_matches===false?'fail':'warning'}/>
                          <Integrity label="Reference matches deterministic oracle" status={trial.audit.reference_matches===true?'pass':trial.audit.reference_matches===false?'fail':'warning'}/>
                          <div className="story-diff"><h3>Grading breakdown</h3><dl className="keyvals"><dt>Initial affected-service F1</dt><dd>{p100(selected.affected_f1)}</dd><dt>Combined root cause</dt><dd>{selected.root_correct==null?'N/A':selected.root_correct?'Correct':'Incorrect'}</dd><dt>Repair selection</dt><dd>{selected.fix_correct==null?'N/A':selected.fix_correct?'Correct':'Incorrect'}</dd><dt>Complete & safe recovery</dt><dd>{trial.audit.grade?.recovery_success === true && trial.audit.grade?.recovery_safe === true ? 'Pass' : trial.audit.grade?.recovery_success === false ? 'Failed' : 'N/A'}</dd><dt>Unsafe committed repair</dt><dd>{trial.audit.grade?.unsafe_commit ? 'Yes' : 'No'}</dd><dt>Rejected tool attempts</dt><dd>{Array.isArray(trial.audit.grade?.protocol_errors) ? trial.audit.grade.protocol_errors.length : 0}</dd><dt>Human semantic evidence review</dt><dd>{trial.human_review?.status || 'Pending — automated provenance is not semantic support'}</dd></dl></div>
                          <details className="story-raw"><summary>Full independent grader response (JSON)</summary><Json value={trial.audit.grade}/></details>
                          <details className="story-raw"><summary>Original reference vs submitted model JSON</summary><div className="grid-11"><div><h3>Oracle reference</h3><Json value={trial.diagnosis?.expected || trial.audit.expected}/></div><div><h3>Model submission</h3><Json value={trial.diagnosis?.predicted || {available:false}}/></div></div></details>
                          {isAgenticTask(selected.task) && <div className="story-review row-gap"><h3>Human semantic review · optional, separate from score</h3><p className="muted">Review record is hash-bound to the selected episode. It does not alter the model output or official grade. Do not mark Verified without independently inspecting the oracle, task/grader alignment, and actual tool evidence.</p>
                            {trial.human_review && <p><strong>{trial.human_review.status}</strong> · {trial.human_review.reviewer}: {trial.human_review.notes}</p>}
                            <Field label="Reviewer initials or name"><input aria-label="Reviewer name or initials" maxLength={80} value={reviewer} onChange={(e)=>setReviewer(e.target.value)}/></Field>
                            <Field label="Review outcome"><select value={reviewStatus} onChange={(e)=>setReviewStatus(e.target.value as typeof reviewStatus)}><option value="uncertain">Uncertain</option><option value="needs_revision">Task or grader needs revision</option><option value="verified">Verified against evidence</option></select></Field>
                            <Field label="Evidence-backed review notes"><textarea aria-label="Evidence-backed review notes" rows={4} maxLength={2400} value={reviewNotes} onChange={(e)=>setReviewNotes(e.target.value)}/></Field>
                            {['I independently checked the oracle and repair state','I checked the task wording against the strict grader','I inspected the model claims against its observed evidence'].map((label,index)=><label key={label} className="review-check"><input type="checkbox" checked={reviewChecks[index]} onChange={(e)=>setReviewChecks((a)=>a.map((v,j)=>index===j?e.target.checked:v))}/>{label}</label>)}
                            <button className="button primary" disabled={reviewBusy || reviewer.trim().length<2 || reviewNotes.trim().length<15 || (reviewStatus==='verified'&&!reviewChecks.every(Boolean))} onClick={async()=>{setReviewBusy(true);setReviewMessage('');try{await postJSON(`/api/runs/${encodeURIComponent(run)}/records/${recordIndex}/review`,{status:reviewStatus,reviewer,notes:reviewNotes,oracle_checked:reviewChecks[0],task_grader_alignment_checked:reviewChecks[1],evidence_support_checked:reviewChecks[2]});setTrial(await getJSON<TrialDetail>(`/api/runs/${encodeURIComponent(run)}/records/${recordIndex}`));setReviewMessage('Review saved separately; original model record and grade remain unchanged.');void refreshRun();}catch(e){setReviewMessage(String(e));}finally{setReviewBusy(false);}}}>Save human review</button>
                            {reviewMessage && <p role="status">{reviewMessage}</p>}
                          </div>}
                          <div className="story-diff row-gap"><h3>Download reproducibility evidence</h3><p>These are supplementary proof files. The verdict, charts and full trace are displayed directly in the UI above.</p><div className="export-options"><DownloadLink href={`/api/runs/${encodeURIComponent(run)}/raw.jsonl`} label="Raw JSONL"/><DownloadLink href={`/api/runs/${encodeURIComponent(run)}/audit.json`} label="Independent audit JSON"/><DownloadLink href={`/api/runs/${encodeURIComponent(run)}/export.csv`} label="Regraded CSV"/><DownloadLink href={`/api/runs/${encodeURIComponent(run)}/bundle.zip`} label="Reproducibility bundle ZIP"/></div></div>
                          <p className="muted">Selected source: {run} · record #{recordIndex} · task version: {selected.task} · recorded prompt SHA-256: {safe(trial.record.prompt_sha256)}. Synthetic incident; no production infrastructure access.</p>
                        </div>
                      )}
                    </div>
                  </> : <Empty title="Choose a recorded attempt" detail="Select a run in the top bar or launch an experiment in Control Room."/>}
                </Panel>
              </div>
            </>
          )}
          {page === 'control' && (
            <>
              <div className="notice control-explainer"><FlaskConical size={19}/><span><strong>A real model is tested, not a simulated AI.</strong> It investigates a fictional service outage with bounded tools and a single sandbox repair. Each agentic episode may make up to 24 separate provider requests; review the quota before approving.</span></div>
              <div className="grid-11">
                <div className="row-gap">
                  <Panel
                    title="1. Select models"
                    description="Live free catalog from FastAPI. Friendly names with exact IDs retained for reproducibility."
                    side={
                      <button
                        className="button"
                        disabled={catalogLoading}
                        onClick={() => void loadModels()}
                      >
                        <RefreshCw size={15} />
                        {catalogLoading ? 'Loading' : 'Refresh models'}
                      </button>
                    }
                  >
                    {catalogError && (
                      <div role="alert" className="notice error">
                        {catalogError}
                      </div>
                    )}
                    <div className="model-catalog-toolbar">
                      <input
                        aria-label="Search free models"
                        value={catalogFilter}
                        onChange={(e) => setCatalogFilter(e.target.value)}
                        placeholder="Search model name or provider"
                        type="search"
                      />
                      <span className="muted">
                        {selectedModels.length} of {condition === 'agentic' ? 1 : 4} selected · {models.length} listed
                      </span>
                    </div>
                    <div className="select-list">
                      {catalogLoading && !models.length ? (
                        <p className="muted">Loading free-model catalog from FastAPI…</p>
                      ) : models.length ? (
                        shownModels.map((m) => (
                          <label className="check-row" key={m.id}>
                            <input
                              type="checkbox"
                              disabled={
                                !selectedModels.includes(m.id) && selectedModels.length >= (condition === 'agentic' ? 1 : 4)
                              }
                              checked={selectedModels.includes(m.id)}
                              onChange={(e) => {
                                setSelectedModels((v) =>
                                  e.target.checked ? [...v, m.id] : v.filter((x) => x !== m.id),
                                );
                                setApproved(false);
                              }}
                            />
                            <span>
                              <strong>{modelDisplay(m.id, m.name)}</strong>
                              <small style={{ display: 'block' }} className="mono">
                                {m.id}
                              </small>
                            </span>
                          </label>
                        ))
                      ) : (
                        <Empty
                          title="No models available"
                          detail="Check FastAPI connectivity or refresh the live catalog. If a model is missing, the provider may have removed its free endpoint."
                        />
                      )}
                    </div>
                  </Panel>
                  <Panel
                    title="2. Tasks and parameters"
                    description="Use controlled settings to compare model responses"
                  >
                    <Field label="Evaluation condition">
                      <select
                        aria-label="Evaluation condition"
                        value={condition}
                        onChange={(e) => {
                          const next = e.target.value as 'single-turn' | 'agentic';
                          setCondition(next);
                          setSelectedTasks(next === 'agentic' ? ['AG08V4'] : ['T08', 'T09']);
                          if (next === 'agentic') {
                            setSelectedModels((current) => current.slice(0, 1));
                            setTrialCount(1);
                          }
                          setApproved(false);
                        }}
                      >
                        <option value="single-turn">Single-turn · full incident facts</option>
                        <option value="agentic">Agentic investigation · tools + sandbox repair</option>
                      </select>
                    </Field>
                    {condition === 'agentic' && (
                      <div className="notice section-space" role="status">
                        <Shield size={15} />
                        AG08V4 and AG09–AG12 (plus historical AG08 variants): one model and one episode per launch. Each episode may make up
                        to 24 OpenRouter requests. All tool calls and committed repairs operate
                        ONLY on a synthetic Python environment. The agent does not receive the reference answer.
                      </div>
                    )}
                    <h3>Benchmark tasks</h3>
                    <p className="muted">
                      {condition === 'agentic'
                        ?  'AG08V4 fixes cost-optimality grading prospectively. Distinct AG09–AG12 incidents use the same strict contract. AG08 v1/v2/v3 remain frozen and separate.' 
                        : 'Baseline and structured causal cases run separately. Selecting a case from another version resets the selection.'}
                    </p>
                    <div className="select-list">
                      {tasks.filter((t) => condition === 'agentic' ? isAgenticTask(t.id) : !isAgenticTask(t.id)).map((t) => (
                        <label className="check-row" key={t.id}>
                          <input
                            type="checkbox"
                            checked={selectedTasks.includes(t.id)}
                            onChange={(e) => {
                              setSelectedTasks((v) => {
                                if (!e.target.checked) return v.filter((x) => x !== t.id);
                                const currentVersion =
                                  tasks.find((x) => x.id === v[0])?.benchmark_version ||
                                  'baseline-v0.1';
                                const nextVersion = t.benchmark_version || 'baseline-v0.1';
                                return currentVersion === nextVersion ? [...v, t.id] : [t.id];
                              });
                              setApproved(false);
                            }}
                          />
                          <span>
                            <strong>
                              {t.id} — {t.title}
                            </strong>
                            <small style={{ display: 'block' }}>
                              {benchmarkLabel(t.benchmark_version)} ·{' '}
                              {t.services} services · {condition === 'agentic' ? 'evidence revealed by tools' : `${t.failed} reference unavailable`}
                            </small>
                          </span>
                        </label>
                      ))}
                    </div>
                    <div className="form-grid section-space">
                      <Field label="Trials per task">
                        <input
                          type="number"
                          min={1}
                          max={condition === 'agentic' ? 1 : 5}
                          disabled={condition === 'agentic'}
                          value={trialCount}
                          onChange={(e) => {
                            setTrialCount(Number(e.target.value));
                            setApproved(false);
                          }}
                        />
                      </Field>
                      <Field label="Maximum tokens">
                        <input
                          type="number"
                          min={512}
                          max={16000}
                          value={maxTokens}
                          onChange={(e) => {
                            setMaxTokens(Number(e.target.value));
                            setApproved(false);
                          }}
                        />
                      </Field>
                      <Field label="Temperature (0–1)">
                        <input
                          type="number"
                          min={0}
                          max={1}
                          step={0.1}
                          value={temperature}
                          onChange={(e) => {
                            setTemperature(Number(e.target.value));
                            setApproved(false);
                          }}
                        />
                      </Field>
                      <Field label="Delay between requests (seconds)">
                        <input
                          type="number"
                          min={3}
                          max={30}
                          step={1}
                          value={delay}
                          onChange={(e) => {
                            setDelay(Number(e.target.value));
                            setApproved(false);
                          }}
                        />
                      </Field>
                      <Field label="Reasoning effort">
                        <select
                          value={effort}
                          onChange={(e) => {
                            setEffort(e.target.value);
                            setApproved(false);
                          }}
                        >
                          {['none', 'minimal', 'low', 'medium', 'high'].map((t) => (
                            <option key={t}>{t}</option>
                          ))}
                        </select>
                      </Field>
                    </div>
                  </Panel>
                </div>
                <div className="row-gap">
                  <Panel
                    title="3. Review and approve"
                    description="The FastAPI backend controls launching; OpenRouter secrets never enter the browser"
                  >
                    <div className="preview-grid">
                      <div>
                        <span className="label">Models</span>
                        <h2>{selectedModels.length}</h2>
                      </div>
                      <div>
                        <span className="label">Tasks × trials</span>
                        <h2>
                          {selectedTasks.length} × {trialCount}
                        </h2>
                      </div>
                      <div>
                        <span className="label">{condition === 'agentic' ? 'Maximum provider calls' : 'Planned API requests'}</span>
                        <h2>{plan}</h2>
                      </div>
                    </div>
                    <div className="selection-summary">
                      <strong>Models</strong>
                      <span>
                        {selectedModels
                          .map((id) => modelDisplay(id, models.find((m) => m.id === id)?.name))
                          .join('; ') || 'Choose at least one free model'}
                      </span>
                      <strong>Tasks</strong>
                      <span>
                        {selectedTasks.map((id) => taskDisplay(id, tasks)).join('; ') ||
                          'Choose at least one benchmark case'}
                      </span>
                      <strong>Benchmark</strong>
                      <span>
                        {tasks.find((t) => t.id === selectedTasks[0])?.benchmark_version ||
                          'Not selected'}
                      </span>
                    </div>
                    <p className="section-space">
                      {condition === 'agentic' ? 'Agentic sessions use one API call per tool turn (up to 24), not one per episode. Real usage may be lower. ' : 'Maximum 45 calls per launch. '}
                      The provider may impose stricter daily quotas and upstream limits.
                    </p>
                    <label className="check-row">
                      <input
                        type="checkbox"
                        checked={approved}
                        onChange={(e) => setApproved(e.target.checked)}
                      />
                      I approve {condition === 'agentic' ? 'up to ' : ''}{plan} real provider requests to selected OpenRouter free-model endpoints.
                    </label>
                    <div className="toolbar">
                      <button
                        className="button primary"
                        onClick={launch}
                        disabled={!readyToRun || !approved || starting || inProgress}
                      >
                        <Play size={16} />
                        {starting ? 'Starting' : 'Approve and start'}
                      </button>
                      <span className="muted">
                        {health?.key_configured
                          ? 'Server API key configured'
                          : 'API key missing on FastAPI server'}
                      </span>
                    </div>
                  </Panel>
                  <Panel
                    title="Live execution monitor"
                    description="Actual subprocess log; refreshed every three seconds"
                    side={<Status value={job.status} />}
                  >
                    <div className="toolbar">
                      {job.output_file && <span className="mono">{job.output_file}</span>}
                      <div className="grow" />
                      {inProgress && (
                        <button className="button danger" onClick={stop}>
                          <Square size={14} />
                          Stop run
                        </button>
                      )}
                      {job.output_file && (
                        <button
                          className="button"
                          disabled={!job.records_saved && inProgress}
                          onClick={async () => {
                            await refreshRuns();
                            setRun(job.output_file || '');
                            setPage('overview');
                          }}
                        >
                          Open {inProgress ? 'saved trials' : 'results'} <ArrowRight size={15} />
                        </button>
                      )}
                    </div>
                    <div className="preview-grid" style={{ margin: '14px 0' }}>
                      <div>
                        <span className="label">{inProgress ? 'Elapsed · live' : 'Run duration'}</span>
                        <strong className="mono" role="timer" aria-live="off">
                          {duration(elapsedLive)}
                        </strong>
                      </div>
                      <div>
                        <span className="label">Started · local time</span>
                        <strong>{date(job.started_utc)}</strong>
                      </div>
                      <div>
                        <span className="label">Completed requests</span>
                        <strong>
                          {job.requests_finished || 0} / {job.requests_planned || 0}
                        </strong>
                      </div>
                    </div>
                    {clockStale && (
                      <div className="notice" role="status">
                        <AlertTriangle size={15} />
                        Server progress has not updated for over 10 seconds. The timer is paused;
                        reconnect to FastAPI to get the actual elapsed time.
                      </div>
                    )}
                    <div className="progress">
                      <div
                        style={{
                          width: `${job.requests_planned ? Math.min(100, (100 * (job.requests_finished || 0)) / job.requests_planned) : 0}%`,
                        }}
                      />
                    </div>
                    <p className="muted" style={{ margin: '8px 0' }}>
                      Finished {job.requests_finished || 0} of {job.requests_planned || 0} {job.condition === 'agentic' ? 'maximum provider calls' : 'requests'}
                      · {job.records_saved || 0} durable records.{' '}
                      {job.current_request ? `Now: ${job.current_request}` : ''}
                    </p>
                    <p className="muted">
                      {job.condition === 'agentic' ? 'Agentic progress counts individual provider turns, not episodes. Every sandbox tool observation is logged, and the full trajectory is saved on completion.' : 'Run duration includes setup and delays. Individual model request durations are available in Execution Analysis.'}
                    </p>
                    <div className="run-log" role="log" aria-live="polite">
                      <pre>{job.log || 'No experiment started in this session.'}</pre>
                    </div>
                  </Panel>
                </div>
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
