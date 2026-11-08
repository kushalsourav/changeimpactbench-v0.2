'use client';
import { useEffect, useState } from 'react';
import { AlertTriangle, ArrowRight, CheckCircle2, Circle, LoaderCircle, Play, RefreshCw, Square } from 'lucide-react';
import { modelDisplay, duration, incidentName } from '../lib/presentation';
import { currentEpisodeLog, parseLiveWorkflow } from '../lib/live-activity';
import { observationsFromLog } from '../lib/live-observations';
import { healthFromLog } from '../lib/observed-health';
import { getJSON } from '../lib/api';
import type { TaskDetail } from '../lib/api';
import { Topology } from '../components/Topology';
import { Status, Panel, Field } from '../components/ui';
import { useWorkbenchState } from '../store/WorkbenchContext';

export function ControlRoom() {
  const {
    trialCount, setTrialCount, setPage, health, setRun, tasks, setAnalysisTab,
    models, catalogLoading, selectedModels, setSelectedModels, selectedTasks, setSelectedTasks,
    maxTokens, setMaxTokens, maxInputTokens, setMaxInputTokens, effort, setEffort, temperature, setTemperature,
    delay, setDelay, approved, setApproved, job, starting, refreshRuns,
    loadModels, launch, stop, readyToRun, inProgress, elapsedLive, clockStale,
  } = useWorkbenchState();
  const [setupOpen, setSetupOpen] = useState(true);
  const settingsLocked = inProgress || starting;
  const started = job.status !== 'idle' || Boolean(job.output_file);
  const activeTaskId = job.task_id || (started && !inProgress ? selectedTasks[0] : '');
  const [topology, setTopology] = useState<TaskDetail | null>(null);
  useEffect(() => {
    let valid = true;
    setTopology(null);
    if (!started || !activeTaskId) return;
    getJSON<TaskDetail>(`/api/tasks/${encodeURIComponent(activeTaskId)}`)
      .then(detail => { if (valid && detail.case.id === activeTaskId) setTopology(detail); })
      .catch(() => { if (valid) setTopology(null); });
    return () => { valid = false; };
  }, [started, activeTaskId]);
  useEffect(() => { if (inProgress) setSetupOpen(false); }, [inProgress]);

  const googleSelected = selectedModels.some(x => x.startsWith('google-ai-studio/'));
  const anthropicSelected = selectedModels.some(x => x.startsWith('anthropic/'));
  const openrouterSelected = selectedModels.some(x => !x.startsWith('google-ai-studio/') && !x.startsWith('anthropic/'));
  const googleKeyMissing = googleSelected && !health?.google_key_configured;
  const anthropicKeyMissing = anthropicSelected && !health?.anthropic_key_configured;
  const openrouterKeyMissing = openrouterSelected && !(health?.openrouter_key_configured ?? health?.key_configured);
  const workflow = parseLiveWorkflow(job.log || '', inProgress);
  const episodeLog = currentEpisodeLog(job.log || '');
  const observedHealth = healthFromLog(episodeLog);
  const liveObservations = observationsFromLog(episodeLog);
  const observedUnavailable = Object.values(observedHealth).filter(value => value === 'unavailable').length;
  const simulated = workflow.activity.filter(item => item.kind === 'tool' && item.tool === 'simulate_repair').length;
  const activeService = [...workflow.activity].reverse().find(item =>
    item.kind === 'tool' && item.target.startsWith('svc-'),
  )?.target;
  const inputSnapshots = [...episodeLog.matchAll(/input tokens: (\d+) \/ (\d+) \(cumulative provider-reported\)/g)];
  const inputLatest = inputSnapshots.at(-1);
  const activeModels = job.models?.length ? job.models : selectedModels;
  const plannedEpisodes = (job.models?.length || selectedModels.length) * (job.trials || trialCount);
  const launchBlocker = settingsLocked ? '' : !selectedModels.length ? 'Select a model.' :
    googleKeyMissing ? 'Google API key missing. Set GOOGLE_API_KEY and restart the backend.' :
    anthropicKeyMissing ? 'Anthropic API key missing. Set ANTHROPIC_API_KEY and restart the backend.' :
    openrouterKeyMissing ? 'OpenRouter API key missing. Set OPENROUTER_API_KEY and restart the backend.' :
    !readyToRun ? 'Check the selected incident and settings.' : '';

  const toggleModel = (modelId: string, checked: boolean) => {
    if (settingsLocked) return;
    if (!checked) setSelectedModels(selectedModels.filter(x => x !== modelId));
    else if (!selectedModels.includes(modelId) && selectedModels.length < 5) setSelectedModels([...selectedModels, modelId]);
    setApproved(false);
  };
  const viewResult = async () => {
    await refreshRuns();
    if (job.output_file) setRun(job.output_file);
    setAnalysisTab('Summary');
    setPage('overview');
  };
  return <div className="agent-launch-workspace agent-launch-simple cib-run-page">
    <details className="cib-setup" open={setupOpen} onToggle={e => setSetupOpen(e.currentTarget.open)}>
      <summary>Set up a test <small>{!setupOpen ? `${selectedModels.length} model${selectedModels.length === 1 ? '' : 's'} · ${trialCount} trial${trialCount === 1 ? '' : 's'}` : ''}</small></summary>
      <div className="cib-setup-body">
        <div className="simple-launch-fields">
          <Field label="Incident">
            <select aria-label="Select agentic incident" disabled={settingsLocked}
              value={selectedTasks[0] || 'RW01V6CF'}
              onChange={e => { setSelectedTasks([e.target.value]); setApproved(false); }}>
              {tasks.map(t => <option key={t.id} value={t.id}>{t.original_source_name || t.dataset_name || incidentName(t.id)}</option>)}
            </select>
          </Field>
          <Field label="Trials per model">
            <select aria-label="Trials per model" disabled={settingsLocked} value={trialCount}
              onChange={e => { setTrialCount(Number(e.target.value)); setApproved(false); }}>
              {[1, 2, 3, 4, 5].map(n => <option key={n} value={n}>{n} {n === 1 ? 'trial' : 'trials'}</option>)}
            </select>
          </Field>
          <Field label={`AI models (${selectedModels.length} selected)`}>
            <div className="model-choose-row">
              <div className="model-multiselect" role="group" aria-label="Select one to five models">
                {models.map(m => <label key={m.id} className="check-row">
                  <input type="checkbox" checked={selectedModels.includes(m.id)}
                    disabled={settingsLocked || (!selectedModels.includes(m.id) && selectedModels.length >= 5)}
                    onChange={e => toggleModel(m.id, e.target.checked)}/>
                  <span>{modelDisplay(m.id, m.name)}</span>
                </label>)}
                {!models.length && <span className="muted">No models found. Check the backend connection.</span>}
              </div>
              <button type="button" className="button" aria-label="Refresh models"
                disabled={catalogLoading || settingsLocked} onClick={() => void loadModels()}>
                <RefreshCw size={15}/>{catalogLoading ? 'Loading' : 'Refresh'}
              </button>
            </div>
          </Field>
        </div>
        <details className="agent-settings">
          <summary>Advanced settings</summary>
          <div className="agent-settings-grid">
            <Field label="Max input tokens per trial">
              <input aria-label="Maximum cumulative input tokens per trial" type="number" min={4096} max={10000000} step={1000}
                disabled={settingsLocked} value={maxInputTokens}
                onChange={e => { setMaxInputTokens(Number(e.target.value)); setApproved(false); }}/>
            </Field>
            <Field label="Max output tokens per response">
              <input aria-label="Maximum output tokens per model response" type="number" min={512} max={20000}
                disabled={settingsLocked} value={maxTokens}
                onChange={e => { setMaxTokens(Number(e.target.value)); setApproved(false); }}/>
            </Field>
            <Field label="Reasoning effort">
              <select aria-label="Reasoning effort" disabled={settingsLocked} value={effort}
                onChange={e => { setEffort(e.target.value); setApproved(false); }}>
                {['none', 'minimal', 'low', 'medium', 'high'].map(x => <option key={x}>{x}</option>)}
              </select>
            </Field>
            <Field label="Temperature">
              <input type="number" min={0} max={1} step={0.1} disabled={settingsLocked}
                value={temperature} onChange={e => { setTemperature(Number(e.target.value)); setApproved(false); }}/>
            </Field>
            <Field label="Delay between requests (seconds)">
              <input type="number" min={3} max={30} disabled={settingsLocked} value={delay}
                onChange={e => { setDelay(Number(e.target.value)); setApproved(false); }}/>
            </Field>
          </div>
          <p className="muted">Input tokens are counted across one trial. The next request is stopped once the provider-reported limit is reached; the last request may cross it. Output tokens are limited per response.</p>
        </details>
        <div className="simple-launch-approval">
          <label className="check-row">
            <input type="checkbox" checked={approved} disabled={settingsLocked} onChange={e => setApproved(e.target.checked)}/>
            <span>Approve up to <strong>{48 * selectedModels.length * trialCount} provider requests</strong> ({selectedModels.length * trialCount} trials). API usage may cost money.</span>
          </label>
          <button className="button primary" disabled={!readyToRun || !approved || settingsLocked} onClick={launch}>
            <Play size={16}/>{starting ? 'Starting…' : 'Start Investigation'}
          </button>
          {launchBlocker && <p role="alert" className="muted">{launchBlocker}</p>}
        </div>
      </div>
    </details>

    {started && <div className="cib-live-layout">
      <div className="cib-live-left">
        <Panel title={incidentName(activeTaskId)} side={<Status value={job.status}/> }>
          <div className="simple-run-heading">
            <div><span className="muted">{activeModels.map(x => modelDisplay(x)).join(' · ') || 'Selected model'} · {duration(elapsedLive)}</span></div>
            <div className="toolbar">
              {inProgress && <button className="button danger" onClick={stop}><Square size={14}/>Stop</button>}
              {!inProgress && job.output_file && (job.records_saved || 0) > 0 && <button className="button primary" onClick={() => void viewResult()}>View results <ArrowRight size={14}/></button>}
            </div>
          </div>
          <div className="live-metrics">
            <div><small>Model requests</small><strong>{job.requests_started || 0} / {job.requests_planned || '—'}</strong></div>
            <div><small>Unavailable found</small><strong>{Object.keys(observedHealth).length ? observedUnavailable : '—'}</strong></div>
            <div><small>Simulations used</small><strong>{simulated} / 5</strong></div>
          </div>
          <div className="cib-run-meta">
            {job.restored_from_disk ? 'Recovered from results folder · ' : ''}
            {workflow.episode ? `Episode ${workflow.episode} · ` : ''}{job.records_saved || 0} / {plannedEpisodes} trials saved
            {inputLatest ? ` · ${Number(inputLatest[1]).toLocaleString()} / ${Number(inputLatest[2]).toLocaleString()} input tokens` : ''}
          </div>
          {clockStale && <p role="status" className="muted">Live updates paused. Check the backend connection.</p>}
        </Panel>
        <Panel title="What the AI is doing">
          <ol className="cib-step-list" aria-label="Recorded investigation workflow">
            {workflow.steps.map(step => <li key={step.key} className={`workflow-stage workflow-${step.state}`}>
              {step.state === 'done' ? <CheckCircle2 size={18} aria-label="Recorded"/> :
                step.state === 'warning' ? <AlertTriangle size={18} aria-label="Unverified"/> :
                step.state === 'current' ? <LoaderCircle size={18} aria-label="Waiting for evidence"/> :
                <Circle size={18} aria-label="Not recorded"/>}
              <span>{step.label}</span><small>{step.detail || (step.state === 'current' ? 'In progress' : step.state === 'not-reached' ? 'Not reached' : '')}</small>
            </li>)}
          </ol>
        </Panel>
        {liveObservations.repairs.length > 0 && <Panel title="Repair checks">
          <div className="cib-repair-checks" aria-label="Recorded repair simulations and applications">
            {liveObservations.repairs.map(repair => {
              const tone = repair.newOutages === 0 ? 'safe' : repair.newOutages != null ? 'unsafe' : 'neutral';
              const facts = [
                repair.cost != null ? `cost ${repair.cost}` : '',
                repair.restored != null ? `${repair.restored} restored` : '',
                repair.remaining != null ? `${repair.remaining} remain` : '',
                repair.newOutages != null ? `${repair.newOutages} new outage${repair.newOutages === 1 ? '' : 's'}` : '',
              ].filter(Boolean);
              return <div className={`cib-repair-row cib-repair-${tone}`} key={`${repair.eventId}-${repair.kind}`}>
                <div><strong>{repair.action}</strong><span>{repair.kind === 'applied' ? 'Applied in sandbox' : 'Simulation only'}</span></div>
                <p>{facts.join(' · ') || 'Outcome fields were not visible in this older log.'}</p>
                <small>{repair.newOutages === 0 ? 'No new outages' : repair.newOutages != null ? 'Introduced new outages' : 'Outcome recorded'} · {repair.eventId}</small>
              </div>;
            })}
          </div>
        </Panel>}
        <Panel title="Recorded activity">
          <div className="live-activity cib-activity" role="log" aria-live="polite">
            {workflow.activity.length ? workflow.activity.slice(-60).reverse().map(item =>
              <div className={`live-activity-item live-activity-${item.kind}`} key={item.key}>
                <div className="cib-activity-head"><strong>{item.title}</strong><span>{item.id}{item.turn ? ` · turn ${item.turn}` : ''}</span></div>
                <span>{item.detail}</span>
              </div>,
            ) : <p className="muted">Waiting for the first recorded tool event.</p>}
          </div>
        </Panel>
      </div>
      <div className="cib-live-right">
        <Panel title="Service dependency view">
          <div className="cib-graph">
            {topology ? <Topology key={activeTaskId} nodes={topology.case.facts.topology} failed={[]}
              observedHealth={observedHealth} serviceCodes={topology.service_codes} selected={activeService}
              nodeObservations={liveObservations.nodes}/> :
              <div className="live-topology-placeholder">{activeTaskId ? 'Loading service map…' : 'Service map unavailable.'}</div>}
          </div>
          <p className="cib-graph-note">Reference connections; service colors reflect only observed health checks, not hidden ground truth.</p>
        </Panel>
        <Panel title="Technical log">
          <pre className="run-log-text cib-technical-log">{episodeLog || 'Waiting for the first event.'}</pre>
        </Panel>
      </div>
    </div>}
    {!started && <div className="cib-empty-live"><Circle size={16}/>Start an investigation to see its live workflow here.</div>}
  </div>;
}
