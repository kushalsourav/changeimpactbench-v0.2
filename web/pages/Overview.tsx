'use client';
import { ArrowRight, Play } from 'lucide-react';
import { Panel, Field } from '../components/ui';
import { savedRunFacts } from '../lib/saved-run-facts';
import { incidentName, isAgenticTask, modelDisplay, p100, short } from '../lib/presentation';
import { useWorkbenchState } from '../store/WorkbenchContext';

/** Display real saved JSONL records through FastAPI, including non-gradeable trials. */
export function Overview() {
  const {
    setPage, run, tasks, info, selected, selectedTrialReady, trial, explanation,
    openSavedEvidence, comparisonTask, setComparisonTask, crossRun,
    setRecordIndex, search,
  } = useWorkbenchState();
  const grade = selectedTrialReady && trial?.audit.grade ? trial.audit.grade : null;
  const problems = (grade?.strict_failure_reasons || []) as string[];
  const modelRows = crossRun?.groups || [];
  const facts = selectedTrialReady && trial?.record ? savedRunFacts(trial.record, info?.run_manifest) : null;
  const query = search.trim().toLowerCase();
  const filtered = info?.rows.map((record, index) => ({record, index})).filter(({record}) =>
    `${incidentName(record.task)} ${record.task} ${record.model} ${record.trial} ${record.status}`.toLowerCase().includes(query)) || [];

  return <div className="results-workspace cib-results-page">
    <section className="results-intro">
      <div><h1>Results</h1><p>What happened, did the AI succeed, and why?</p></div>
      <button className="button primary" onClick={() => setPage('control')}>Run another test <Play size={14}/></button>
    </section>
    {info && info.rows.length ? <>
      <Panel title="Saved investigations">
        <div className="results-episode-list">
          {filtered.map(({record, index}) => <button key={`${record.model}-${record.trial}-${index}`}
            className={`result-episode-button ${selected?.index === index ? 'selected' : ''}`}
            aria-pressed={selected?.index === index}
            onClick={() => setRecordIndex(index)}>
            <span><strong>{incidentName(record.task)}</strong><small>{short(record.model)} · Trial {record.trial}</small></span>
            <span className={record.pass === true ? 'text-success' : record.pass === false ? 'text-error' : 'muted'}>
              {record.pass == null ? 'Not graded' : record.pass ? 'PASS' : 'FAIL'}
            </span>
          </button>)}
          {!filtered.length && <p className="muted">No saved investigations match your search.</p>}
        </div>
      </Panel>
      {selected && <Panel title="Selected outcome">
        <div className="results-verdict">
          <div><strong>{modelDisplay(selected.model)}</strong><p>{incidentName(selected.task)} · Trial {selected.trial}</p></div>
          <div className={`results-verdict-status ${selected.pass === true ? 'text-success' : selected.pass === false ? 'text-error' : ''}`}>
            {selected.pass == null ? 'NOT GRADED' : selected.pass ? 'PASS' : 'FAIL'}
            <small>Score {p100(selected.score)}</small>
          </div>
        </div>
        <div className="results-token-usage" aria-label="Recorded token usage">
          <div><small>Input tokens used / budget</small><strong>{selected.prompt_tokens?.toLocaleString() ?? 'Not reported'}{selected.max_input_tokens != null ? ` / ${selected.max_input_tokens.toLocaleString()}` : ''}</strong></div>
          <div><small>Output tokens used</small><strong>{selected.completion_tokens?.toLocaleString() ?? 'Not reported'}</strong></div>
          <div><small>Reasoning tokens reported</small><strong>{selected.reasoning_tokens?.toLocaleString() ?? 'Not reported'}</strong></div>
        </div>
        <div className="results-reason">
          <h3>Why?</h3>
          <p>{!selectedTrialReady ? 'Loading this saved episode…' : selected.pass == null
            ? facts?.summary || 'This episode was not independently gradeable.'
            : explanation?.summary || 'See the independent grade and recorded evidence.'}</p>
          {problems.length > 0 && <ul>{problems.slice(0, 4).map(reason => <li key={reason}>{reason.replaceAll('_', ' ')}</li>)}</ul>}
          {facts && <p className="muted">{facts.requests ?? '—'} model requests{facts.limit != null ? ` / ${facts.limit} max` : ''} · {facts.repairs.filter(r => !r.committed).length} repairs simulated · {facts.committed ? 'Repair applied' : 'No repair applied'} · {facts.submitted ? 'Diagnosis submitted' : 'No diagnosis submitted'}</p>}
        </div>
        {facts && facts.repairs.length > 0 && <details className="cib-repair-details">
          <summary>Recorded repair tests ({facts.repairs.length})</summary>
          <div className="table-wrap"><table>
            <thead><tr><th>Repair</th><th>Cost</th><th>Restored</th><th>New outages</th><th>Outcome</th></tr></thead>
            <tbody>{facts.repairs.map((item, index) => <tr key={`${item.action}-${index}`}>
              <td className="mono">{item.action}</td><td>{item.cost ?? '—'}</td><td>{item.restored ?? '—'}</td>
              <td>{item.newOutages ?? '—'}</td><td>{item.committed ? 'Applied' : item.newOutages != null && item.newOutages > 0 ? 'Unsafe simulation' : item.remaining === 0 ? 'Safe in simulation' : 'Incomplete simulation'}</td>
            </tr>)}</tbody>
          </table></div>
        </details>}
        {selectedTrialReady && trial?.record && Array.isArray(trial.record.audit_warnings) && trial.record.audit_warnings.length > 0 &&
          <p className="cib-audit-warning" role="alert">Audit warning: {trial.record.audit_warnings.map(String).join('; ')}</p>}
        {selectedTrialReady && trial?.audit && (trial.audit.prompt_sha_matches === false || trial.audit.stored_grade_matches === false || trial.audit.reference_matches === false) &&
          <p className="cib-audit-warning" role="alert">Independent replay checks did not all match. Review the original trace.</p>}
        <button className="button primary" onClick={() => openSavedEvidence(run, selected.index)}>View full evidence <ArrowRight size={14}/></button>
      </Panel>}
    </> : <Panel title="No results yet">
      <p>Saved investigations appear here after an actual model run.</p>
      <button className="button primary" onClick={() => setPage('control')}>Start Investigation <ArrowRight size={14}/></button>
    </Panel>}

    <Panel title="Compare models">
      <div className="results-compare-controls"><Field label="Incident">
        <select aria-label="Compare agentic task version" value={comparisonTask} onChange={e => setComparisonTask(e.target.value)}>
          {tasks.filter(t => isAgenticTask(t.id)).map(t => <option value={t.id} key={t.id}>{t.original_source_name || incidentName(t.id)}</option>)}
        </select>
      </Field></div>
      {modelRows.some(x => x.episodes > 0) ? <div className="table-wrap">
        <table>
          <thead><tr><th>Model</th><th>Trials</th><th>Gradeable</th><th>Strict passes</th><th>Safe recoveries</th><th>Unverified</th><th>Provider errors</th></tr></thead>
          <tbody>{modelRows.filter(x => x.episodes > 0).map((group, index) => <tr key={`${group.model}-${index}`}>
            <td>{modelDisplay(group.model)}</td><td>{group.episodes}</td><td>{group.completed}</td>
            <td>{group.strict_passes}{group.completed ? ` / ${group.completed}` : ''}</td>
            <td>{group.complete_safe_repairs}</td><td>{group.unverified}</td><td>{group.api_errors}</td>
          </tr>)}</tbody>
        </table>
      </div> : <p className="muted">No saved trials for this incident yet.</p>}
    </Panel>
  </div>;
}
