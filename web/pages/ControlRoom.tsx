'use client';
import { useEffect, useState } from 'react';
import { ArrowRight, CheckCircle2, Circle, LoaderCircle, Play, RefreshCw, Square } from 'lucide-react';
import { modelDisplay, duration, incidentName } from '../lib/presentation';
import { parseLiveWorkflow } from '../lib/live-activity';
import { getJSON } from '../lib/api';
import type { TaskDetail } from '../lib/api';
import { Topology } from '../components/Topology';
import { Status, Panel, Field } from '../components/ui';
import { useWorkbenchState } from '../store/WorkbenchContext';

export function ControlRoom() {
  const {
    trialCount, setTrialCount, setPage, health, setRun, tasks, setAnalysisTab,
    models, catalogLoading, selectedModels, setSelectedModels, selectedTasks, setSelectedTasks,
    maxTokens, setMaxTokens, effort, setEffort, temperature, setTemperature,
    delay, setDelay, approved, setApproved, job, starting, refreshRuns,
    loadModels, launch, stop, readyToRun, inProgress, elapsedLive, clockStale,
  } = useWorkbenchState();

  const googleSelected = selectedModels.some(x => x.startsWith('google-ai-studio/'));
  const anthropicSelected = selectedModels.some(x => x.startsWith('anthropic/'));
  const openrouterSelected = selectedModels.some(x => !x.startsWith('google-ai-studio/') && !x.startsWith('anthropic/'));
  const googleKeyMissing = googleSelected && !health?.google_key_configured;
  const anthropicKeyMissing = anthropicSelected && !health?.anthropic_key_configured;
  const openrouterKeyMissing = openrouterSelected && !(health?.openrouter_key_configured ?? health?.key_configured);
  const settingsLocked = inProgress || starting;
  const started = job.status !== 'idle' || Boolean(job.output_file);
  // The backend owns the active task ID so a page reload cannot attach a stale
  // selector or a previous experiment's topology to the current investigation.
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

  const incident = tasks.find(t => t.id === selectedTasks[0]);
  const workflow = parseLiveWorkflow(job.log || '', inProgress);
  const showLive = started && Boolean(job.output_file);
  const activeModels = job.models?.length ? job.models : selectedModels;
  const plannedEpisodes = (job.models?.length || selectedModels.length) * (job.trials || trialCount);
  const launchBlocker = settingsLocked ? '' : selectedModels.length === 0 ? 'Select a model.' :
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

  return <div className="agent-launch-workspace agent-launch-simple">
    <section className="agent-launch-intro">
      <h1>Test an AI incident responder</h1>
      <p>Choose an incident and a model to begin.</p>
    </section>

    <Panel title="Set up a test">
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
              {models.filter(m => !m.id.startsWith('google-ai-studio/')).map(m =>
                <label key={m.id} className="check-row">
                  <input type="checkbox" checked={selectedModels.includes(m.id)}
                    disabled={settingsLocked || (!selectedModels.includes(m.id) && selectedModels.length >= 5)}
                    onChange={e => toggleModel(m.id, e.target.checked)}/>
                  <span>{modelDisplay(m.id, m.name)}</span>
                </label>,
              )}
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
          <Field label="Max output tokens per response">
            <input aria-label="Maximum output tokens per model response" type="number" min={512} max={16000}
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
        <p className="muted">Output tokens limit the model's response, not input context. Reasoning settings are provider-dependent. Keep these settings the same when comparing models.</p>
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
    </Panel>

    {showLive && <Panel title="Live investigation" side={<Status value={job.status}/> }>
      <div className="simple-run-heading">
        <div>
          <strong>{incidentName(activeTaskId)}</strong>
          <span className="muted">{activeModels.map(x => modelDisplay(x)).join(' · ') || 'Selected model'} · {duration(elapsedLive)}</span>
        </div>
        <div className="toolbar">
          {inProgress && <button className="button danger" onClick={stop}><Square size={14}/>Stop</button>}
          {job.output_file && !inProgress && (job.records_saved || 0) > 0 && <button className="button primary" onClick={async () => {
            await refreshRuns(); setRun(job.output_file || ''); setAnalysisTab('Summary'); setPage('analysis');
          }}>View result and evidence <ArrowRight size={14}/></button>}
        </div>
      </div>
      <div className="live-metrics">
        <div><small>Model requests used</small><strong>{job.requests_started || 0} / {job.requests_planned || '—'} max</strong></div>
        <div><small>Saved trials</small><strong>{job.records_saved || 0} / {plannedEpisodes || '—'}</strong></div>
        <div><small>Current step</small><strong>{job.current_request || (inProgress ? 'Running' : job.status)}</strong></div>
      </div>
      {clockStale && <p role="status" className="muted">Live updates paused. Check the backend connection.</p>}
      <div className="live-workflow-grid">
        <section aria-label="Recorded investigation workflow" className="live-workflow-stages">
          <h3>What the AI is doing</h3>
          <ol>
            {workflow.steps.map(step => <li key={step.key} className={`workflow-stage workflow-${step.state}`}>
              {step.state === 'done' ? <CheckCircle2 size={18} aria-label="Recorded"/> :
                step.state === 'current' ? <LoaderCircle size={18} aria-label="Waiting for the next recorded step"/> :
                <Circle size={18} aria-label="Not recorded"/>}
              <span>{step.label}</span>
              <small>{step.state === 'done' ? 'Recorded' : step.state === 'current' ? 'Awaiting evidence' : 'Not yet recorded'}</small>
            </li>)}
          </ol>
        </section>
        <section className="live-topology-panel" aria-label="Service dependency diagram">
          <h3>Service dependency view</h3>
          {topology ? <Topology key={activeTaskId} nodes={topology.case.facts.topology} failed={[]} unknown/> :
            <div className="live-topology-placeholder">{activeTaskId ? 'Loading service map…' : 'Service map unavailable for this run.'}</div>}
          <small>Reference topology for reviewers; not the model's observed health. Final outcomes appear in Results.</small>
        </section>
      </div>
      <div className="live-activity-heading"><h3>Recorded activity</h3><span className="muted">Latest events</span></div>
      <div className="live-activity" role="log" aria-live="polite">
        {workflow.activity.length ? workflow.activity.slice(-8).reverse().map(item =>
          <div className={`live-activity-item live-activity-${item.kind}`} key={item.key}>
            <strong>{item.title}</strong><span>{item.detail}</span>
          </div>,
        ) : <p className="muted">Waiting for the first recorded tool event.</p>}
      </div>
      <details className="story-raw"><summary>Technical log</summary><pre className="run-log-text">{job.log || 'No log entries yet.'}</pre></details>
    </Panel>}
  </div>;
}
