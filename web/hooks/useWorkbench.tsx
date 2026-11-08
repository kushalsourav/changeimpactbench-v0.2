'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import { getJSON, postJSON } from '../lib/api';
import type {
  Health,
  RunFile,
  RunInfo,
  Task,
  TaskDetail,
  TrialDetail,
  RunStatus,
  AgentEvent
} from '../lib/api';
import { explainEpisode } from '../lib/episode-analysis';
import { chartLabel, modelDisplay, short, isAgenticTask } from '../lib/presentation';
import type { Page, AgenticComparison, ChartRow } from '../lib/presentation';
import { useExecutionStream } from './useExecutionStream';
export function useWorkbench() {
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
    [analysisTab, setAnalysisTab] = useState('Summary'),
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
    [selectedTasks, setSelectedTasks] = useState(['RW01V6CF']);
  const [labDataset, setLabDataset] = useState('RW01V6CF');
  const [condition] = useState<'agentic'>('agentic');
  const [comparisonTask, setComparisonTask] = useState('RW01V6CF');
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
  const onStreamStatus = useCallback((state: RunStatus, logDelta: string, replaceLog: boolean) => {
    setJobUpdatedMs(Date.now());
    setJob((previous) => ({
      ...previous, ...state,
      log: replaceLog ? logDelta : ((previous.log || '') + logDelta).slice(-14000),
    }));
  }, []);
  useExecutionStream(job.status === 'running' || job.status === 'stopping', onStreamStatus);
  const handledTerminalJob = useRef<string | null>(null);
  const pendingEvidence = useRef<{ run: string; index: number } | null>(null);
  const runFetchSequence = useRef(0);
  const taskFetchSequence = useRef(0);
  const recordFetchSequence = useRef(0);

  // The saved header experiment + active record are the sole task selector.
  const taskId = info?.run === run ? info.rows[recordIndex]?.task || '' : '';
  const activeLabTaskId = taskId || labDataset;

  const selectPage = (value: Page) => {
    setPage(value);
  };
  const refreshRuns = useCallback(async () => {
    try {
      const list = await getJSON<RunFile[]>('/api/runs');
      setRuns(list);
      if (list.length === 0) { setInfo(null); setTrial(null); setRecordIndex(0); setFlowNotice(''); }
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
    if (!activeLabTaskId) return;
    getJSON<TaskDetail>(`/api/tasks/${encodeURIComponent(activeLabTaskId)}`)
      .then((data) => {
        if (sequence === taskFetchSequence.current) setTask(data);
      })
      .catch((e) => {
        if (sequence === taskFetchSequence.current) setError(String(e));
      });
  }, [activeLabTaskId]);
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
          // override a manually selected saved experiment.
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
    setAnalysisTab('Summary');
    setPage('analysis');
  };
  const openSavedEvidence = (filename: string, index: number) => {
    pendingEvidence.current = { run: filename, index };
    setRun(filename);
    if (run === filename) setRecordIndex(index);
    setAnalysisTab('Summary');
    setPage('analysis');
  };
  const loadModels = useCallback(async () => {
    setCatalogError('');
    setCatalogLoading(true);
    try {
      const [catalog, freshHealth] = await Promise.all([
        getJSON<{ id: string; name: string }[]>('/api/models'),
        getJSON<Health>('/api/health'),
      ]);
      setHealth(freshHealth);
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
        condition?: 'agentic';
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
  const plan = selectedModels.length * selectedTasks.length * trialCount * 48;
  const readyToRun = Boolean(
    (!selectedModels.some(x => x.startsWith('google-ai-studio/')) || Boolean(health?.google_key_configured)) &&
    (!selectedModels.some(x => x.startsWith('anthropic/')) || Boolean(health?.anthropic_key_configured)) &&
    (!selectedModels.some(x => !x.startsWith('google-ai-studio/') && !x.startsWith('anthropic/')) || Boolean(health?.openrouter_key_configured)) &&
    selectedModels.length &&
    selectedTasks.length &&
    (selectedModels.length >= 1 && selectedModels.length <= 5 && selectedTasks.length === 1 && isAgenticTask(selectedTasks[0])) &&
    plan > 0 &&
    plan <= 1200 &&
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

  return {
    page, setPage, collapsed, setCollapsed, dark, setDark, health, setHealth, runs, setRuns, run, setRun, info, setInfo, tasks, setTasks, task, setTask, nodeId, setNodeId, previewActionId, setPreviewActionId, repairState, setRepairState, labMode, setLabMode, labSideView, setLabSideView, recordIndex, setRecordIndex, trial, setTrial, analysisTab, setAnalysisTab, expandedEvent, setExpandedEvent, loading, setLoading, error, setError, search, setSearch, filter, setFilter, modelFilter, setModelFilter, models, setModels, catalogError, setCatalogError, catalogLoading, setCatalogLoading, catalogLoaded, setCatalogLoaded, catalogFilter, setCatalogFilter, flowNotice, setFlowNotice, selectedModels, setSelectedModels, selectedTasks, setSelectedTasks, comparisonTask, setComparisonTask, crossRun, setCrossRun, reviewer, setReviewer, reviewNotes, setReviewNotes, reviewStatus, setReviewStatus, reviewChecks, setReviewChecks, reviewBusy, setReviewBusy, reviewMessage, setReviewMessage, trialCount, setTrialCount, maxTokens, setMaxTokens, effort, setEffort, temperature, setTemperature, delay, setDelay, approved, setApproved, job, setJob, starting, setStarting, themeLoaded, setThemeLoaded, clockNowMs, setClockNowMs, jobUpdatedMs, setJobUpdatedMs, handledTerminalJob, pendingEvidence, runFetchSequence, taskFetchSequence, recordFetchSequence, condition, taskId, selectPage, refreshRuns, refreshRun, chooseTrial, openSavedEvidence, loadModels, launch, stop, rows, matching, summaries, completed, passed, apiErrors, incomplete, avgPartial, totalLatency, avgLatency, tokens, eligibleReliability, maxK, comparison, latencyByModel, usageByModel, taskRows, selected, activeLabTaskId, validLabRecord, labCommittedAction, actionId, recordedPreview, recordedCommitState, labTask, agentEvents, commitEvent, committedAction, matchedSimulation, simulatedRemaining, committedRemaining, decisionMiss, plan, readyToRun, shownModels, inProgress, clockLagMs, elapsedLive, clockStale, affected, repairs, repair, shownDown, directFailures, issueCount, selectedTrialReady, explanation, storyServices, actualEffect, storyInitialDown, storyAfterDown, crossRunCompleted, crossRunChart, counts, labDataset, setLabDataset
  };
}
