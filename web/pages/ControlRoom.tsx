'use client';
import { ArrowRight, GitBranch, Play, RefreshCw, Square } from 'lucide-react';
import { modelDisplay, isGraphTask, duration, incidentLabel, incidentName } from '../lib/presentation';
import { parseLiveActivity } from '../lib/live-activity';
import { Status, Panel, Field } from '../components/ui';
import { useWorkbenchState } from '../store/WorkbenchContext';

export function ControlRoom() {
  const { trialCount, setTrialCount, setPage, health, setRun, tasks, setAnalysisTab, models, catalogLoading, selectedModels, setSelectedModels, selectedTasks, setSelectedTasks, maxTokens, setMaxTokens, effort, setEffort, temperature, setTemperature, delay, setDelay, approved, setApproved, job, starting, refreshRuns, loadModels, launch, stop, readyToRun, inProgress, elapsedLive, clockStale } = useWorkbenchState();
  const googleSelected = selectedModels.some(x => x.startsWith('google-ai-studio/'));
  const anthropicSelected = selectedModels.some(x => x.startsWith('anthropic/'));
  const openrouterSelected = selectedModels.some(x => !x.startsWith('google-ai-studio/') && !x.startsWith('anthropic/'));
  const googleKeyMissing = googleSelected && !health?.google_key_configured;
  const anthropicKeyMissing = anthropicSelected && !health?.anthropic_key_configured;
  const openrouterKeyMissing = openrouterSelected && !(health?.openrouter_key_configured ?? health?.key_configured);
  const launchBlocker = selectedModels.length === 0 ? 'Select a model to begin.' :
    googleKeyMissing ? 'Google API key is not loaded by FastAPI. Set GOOGLE_API_KEY in the project-root .env file and restart the backend.' :
    anthropicKeyMissing ? 'Anthropic API key is not loaded by FastAPI. Set ANTHROPIC_API_KEY in the project-root .env file and restart the backend.' :
    openrouterKeyMissing ? 'OpenRouter API key is not loaded by FastAPI. Set OPENROUTER_API_KEY in the project-root .env file and restart the backend.' :
    !approved ? 'Tick the provider-request approval checkbox to enable the launch.' :
    !readyToRun ? 'Check incident, trial count and advanced settings before launching.' : '';
  const toggleModel = (modelId: string, checked: boolean) => {
    if (!checked) setSelectedModels(selectedModels.filter(x => x !== modelId));
    else if (!selectedModels.includes(modelId) && selectedModels.length < 5) setSelectedModels([...selectedModels, modelId]);
    setApproved(false);
  };
  const incident = tasks.find(t => t.id === selectedTasks[0]);
  const feed = parseLiveActivity(job.log || '');
  const started = job.status !== 'idle' || Boolean(job.output_file);
  const maximum = job.requests_planned || (48 * selectedModels.length * trialCount);
  const progress = maximum ? Math.min(100, ((job.requests_started || 0) / maximum) * 100) : 0;

  return <div className="agent-launch-workspace agent-launch-simple">
    <section className="agent-launch-intro">
      <span className="research-eyebrow">CHANGEIMPACTBENCH / NATIVE AGENT EXPERIMENT</span>
      <h1>Run an AI incident responder</h1>
      <p>Choose a V6 neutral/counterfactual incident (or preserved V5/V4 scenarios) and an approved provider model. The existing LangGraph tools record every action for independent replay.</p>
    </section>

    <Panel title="Compare incident responders" description="One versioned incident · multiple AI models · independent trials and evidence">
      <div className="simple-launch-fields">
        <Field label="Incident">
          <select aria-label="Select agentic incident" value={selectedTasks[0] || 'RW01V6N'} onChange={e => {setSelectedTasks([e.target.value]);setApproved(false);}}>
            {tasks.filter(t => t.id.endsWith('V6CF') || t.id.endsWith('V6N') || t.id.endsWith('V5') || t.id.endsWith('V4')).map(t => <option key={t.id} value={t.id}>{incidentLabel(t.id)}</option>)}
          </select>
        </Field>
        <Field label={`Models · ${selectedModels.length} selected (up to 5 across providers)`}>
          <div className="model-choose-row">
            <div className="model-multiselect" role="group" aria-label="Select one to five models">
              {models.filter(m => !m.id.startsWith('google-ai-studio/')).map(m => <label key={m.id} className="check-row">
                <input type="checkbox" checked={selectedModels.includes(m.id)}
                  disabled={!selectedModels.includes(m.id) && selectedModels.length >= 5}
                  onChange={e => toggleModel(m.id, e.target.checked)}/>
                {modelDisplay(m.id,m.name)} {m.id.startsWith('anthropic/') ? '· Direct Anthropic API' : '· OpenRouter free'}
              </label>)}
              {!models.length && <span className="muted">No models available. Check backend provider settings.</span>}
            </div>
            <button type="button" className="button" aria-label="Refresh models" disabled={catalogLoading} onClick={() => void loadModels()}><RefreshCw size={15}/>{catalogLoading ? 'Loading' : 'Refresh'}</button>
          </div>
          <p className="muted">Select up to five models across OpenRouter and direct Anthropic. Google AI Studio is reserved for structured post-run Research Lab analysis.</p>
          {googleSelected && <p className="muted">Google API: up to five trials per selected model. Usage quotas and rate limits depend on your Google project and model; access is not unlimited.</p>}
        </Field>
        <Field label="Independent trials per model">
          <select aria-label="Trials per model" value={trialCount} onChange={e=>{setTrialCount(Number(e.target.value));setApproved(false);}}>
            {[1,2,3,4,5].map(n=><option key={n} value={n}>{n} {n===1?'trial':'trials'}</option>)}
          </select>
        </Field>
      </div>
      {incident && <div className="simple-dataset-summary">
        <strong>{incidentName(incident.id)}</strong>
        <span className="muted">{incident.services} modeled services · {incident.failed} initially unavailable in reconstruction · {incident.id}</span>
        <p>{incident.alert || incident.dataset_name || incident.title.replace('Incident response · ', '')}</p>
        <small>{(incident.id.endsWith('V5') || incident.id.endsWith('V6N') || incident.id.endsWith('V6CF')) ? 'Fully synthetic versioned scenario. Clues and repair effects must be investigated through sandbox tools; no actual outage telemetry.' : 'Based on a published operator postmortem. The service graph, candidate repairs and costs are reconstructed for evaluation—not original production telemetry.'}</small>
        {incident.source_url && <p><a href={incident.source_url} target="_blank" rel="noopener noreferrer">Read original incident postmortem</a></p>}
        {incident.documented_facts?.length ? <details><summary>Source-backed facts vs simulation assumptions</summary>
          <strong>Reported by incident operator</strong><ul>{incident.documented_facts.map(x=><li key={x}>{x}</li>)}</ul>
          <strong>Reconstructed for testing</strong><ul>{(incident.model_assumptions || []).map(x=><li key={x}>{x}</li>)}</ul>
        </details> : null}
        <button className="text-link-action" type="button" onClick={() => setPage('lab')}>Explore the service topology <ArrowRight size={14}/></button>
      </div>}
      <details className="agent-settings"><summary>Advanced settings and reproducibility</summary>
        <div className="agent-settings-grid">
          <Field label="Output token limit"><input type="number" min={512} max={16000} value={maxTokens} onChange={e=>{setMaxTokens(Number(e.target.value));setApproved(false);}}/></Field>
          <Field label="Temperature"><input type="number" min={0} max={1} step={0.1} value={temperature} onChange={e=>{setTemperature(Number(e.target.value));setApproved(false);}}/></Field>
          <Field label="Minimum delay between calls (s)"><input type="number" min={3} max={30} value={delay} onChange={e=>{setDelay(Number(e.target.value));setApproved(false);}}/></Field>
          <Field label="Reasoning effort"><select value={effort} onChange={e=>{setEffort(e.target.value);setApproved(false);}}>{['none','minimal','low','medium','high'].map(x=><option key={x}>{x}</option>)}</select></Field>
        </div>
        {googleSelected && <p className="muted">Google-hosted models may apply model-specific sampling defaults (Gemini 3.5 Flash-Lite temperature may be ignored). Reasoning effort is not forwarded to Google; Gemma 4 thinking settings are not automatically mapped. Run a pilot to validate native tool calls.</p>}
        <p className="muted">Exact model IDs: {selectedModels.join(', ') || 'none selected'}. LangChain <code>create_agent</code> on LangGraph, native tool IDs and checkpointing. The deterministic oracle replays tool calls separately.</p>
      </details>
      <div className="simple-launch-approval">
        <label className="check-row"><input type="checkbox" checked={approved} onChange={e=>setApproved(e.target.checked)}/> I approve up to <strong>{48 * selectedModels.length * trialCount} real provider requests</strong> across {selectedModels.length * trialCount} episodes ({48} per episode).</label>
        <button className="button primary" disabled={!readyToRun || !approved || starting || inProgress} onClick={launch}><Play size={16}/>{starting ? 'Starting…' : 'Start investigation'}</button>
        {launchBlocker && <p role="alert" className="muted">{launchBlocker}</p>}
        <span className="muted">{googleSelected && (health?.google_key_configured ? 'Google API key configured · ' : 'Set GOOGLE_API_KEY · ')}{anthropicSelected && (health?.anthropic_key_configured ? 'Anthropic key configured · ' : 'Set ANTHROPIC_API_KEY · ')}{openrouterSelected && (health?.openrouter_key_configured ? 'OpenRouter key configured' : 'Set OPENROUTER_API_KEY')}</span>
      </div>
    </Panel>

    {started && <Panel title="Live investigation" description="Actual model requests and sandbox observations—not hidden model thoughts" side={<Status value={job.status}/> }>
      <div className="simple-run-heading">
        <div><strong>{incidentName(selectedTasks[0] || '')}</strong><span className="muted">{selectedModels.length ? selectedModels.map(x=>modelDisplay(x)).join(' · ') : 'Saved experiment'} · {duration(elapsedLive)}</span></div>
        <div className="toolbar">
          {inProgress && <button className="button danger" onClick={stop}><Square size={14}/>Stop</button>}
          {job.output_file && <button className="button primary" onClick={async()=>{await refreshRuns();setRun(job.output_file || '');setAnalysisTab('Summary');setPage('analysis');}}>View episode evidence <ArrowRight size={14}/></button>}
        </div>
      </div>
      <div className="live-metrics">
        <div><small>Provider requests</small><strong>{job.requests_started || 0} / {maximum}</strong></div>
        <div><small>Saved episodes</small><strong>{job.records_saved || 0}</strong></div>
        <div><small>Status</small><strong>{job.status === 'finished' ? 'Finished' : job.status === 'running' ? 'Investigating' : job.status}</strong></div>
      </div>
      <div className="progress" aria-label="Provider request budget used"><div style={{width:`${progress}%`}}/></div>
      {clockStale && <p role="status" className="muted">The execution monitor has not refreshed recently. Check backend connectivity.</p>}
      <div className="live-activity" role="log" aria-live="polite">
        {feed.length ? feed.slice(-14).reverse().map(item => <div className={`live-activity-item live-activity-${item.kind}`} key={item.key}>
          <strong>{item.title}</strong><span>{item.detail}</span>
        </div>) : <p className="muted">No tool observations recorded yet. The first provider response may take some time.</p>}
      </div>
      <details className="story-raw"><summary>Original execution log (verbatim)</summary><pre className="run-log-text">{job.log || 'No events recorded.'}</pre></details>
      <p className="muted">A saved episode can be non-gradeable after budget exhaustion or provider failure. Exact evidence and raw traces appear in Episode evidence.</p>
    </Panel>}
  </div>;
}
