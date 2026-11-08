'use client';
import { ArrowRight, Play } from 'lucide-react';
import { Panel, Field } from '../components/ui';
import { incidentName, isAgenticTask, modelDisplay, p100, short } from '../lib/presentation';
import { useWorkbenchState } from '../store/WorkbenchContext';

/** Human-first results. Full evidence, reviewer checks, and exports stay in the episode view. */
export function Overview() {
  const {
    setPage, run, tasks, info, selected, selectedTrialReady, trial, explanation,
    openSavedEvidence, comparisonTask, setComparisonTask, crossRun,
  } = useWorkbenchState();
  const grade = selectedTrialReady && trial?.audit.grade ? trial.audit.grade : null;
  const problems = (grade?.strict_failure_reasons || []) as string[];
  const modelRows = crossRun?.groups || [];

  return <div className="results-workspace">
    <section className="results-intro">
      <div>
        <h1>Results</h1>
        <p>What happened, did the AI succeed, and why?</p>
      </div>
      <button className="button primary" onClick={() => setPage('control')}>Run another test <Play size={14}/></button>
    </section>

    {info && info.rows.length > 0 ? <>
      <Panel title="Saved investigations">
        <div className="results-episode-list">
          {info.rows.map((record, index) => <button key={`${record.model}-${record.trial}-${index}`}
            className={`result-episode-button ${selected?.index === index ? 'selected' : ''}`}
            onClick={() => openSavedEvidence(run, index)}>
            <span><strong>{incidentName(record.task)}</strong><small>{short(record.model)} · Trial {record.trial}</small></span>
            <span className={record.pass === true ? 'text-success' : record.pass === false ? 'text-error' : 'muted'}>
              {record.pass == null ? 'Not graded' : record.pass ? 'PASS' : 'FAIL'}
            </span>
            <ArrowRight size={15}/>
          </button>)}
        </div>
      </Panel>
      {selected && <Panel title="Selected outcome">
        <div className="results-verdict">
          <div>
            <strong>{modelDisplay(selected.model)}</strong>
            <p>{incidentName(selected.task)} · Trial {selected.trial}</p>
          </div>
          <div className={`results-verdict-status ${selected.pass === true ? 'text-success' : selected.pass === false ? 'text-error' : ''}`}>
            {selected.pass == null ? 'NOT GRADED' : selected.pass ? 'PASS' : 'FAIL'}
            <small>Score {p100(selected.score)}</small>
          </div>
        </div>
        <div className="results-token-usage" aria-label="Recorded token usage">
          <div><small>Input tokens used</small><strong>{selected.prompt_tokens ?? 'Not reported'}</strong></div>
          <div><small>Output tokens used</small><strong>{selected.completion_tokens ?? 'Not reported'}</strong></div>
          <div><small>Reasoning tokens reported</small><strong>{selected.reasoning_tokens ?? 'Not reported'}</strong></div>
        </div>
        <div className="results-reason">
          <h3>Why?</h3>
          <p>{explanation?.summary || (selected.pass == null
            ? 'This attempt did not produce a verified, gradeable result.'
            : 'Open the evidence for the verified grading details.')}</p>
          {problems.length > 0 && <ul>{problems.slice(0, 4).map(reason => <li key={reason}>{reason.replaceAll('_', ' ')}</li>)}</ul>}
        </div>
        <button className="button primary" onClick={() => openSavedEvidence(run, selected.index)}>
          View full evidence <ArrowRight size={14}/>
        </button>
      </Panel>}
    </> : <Panel title="No results yet">
      <p>Run an investigation to see its score, repair outcome, and evidence here.</p>
      <button className="button primary" onClick={() => setPage('control')}>Start Investigation <ArrowRight size={14}/></button>
    </Panel>}

    <Panel title="Compare models">
      <div className="results-compare-controls">
        <Field label="Incident">
          <select aria-label="Compare agentic task version" value={comparisonTask}
            onChange={e => setComparisonTask(e.target.value)}>
            {tasks.filter(t => isAgenticTask(t.id)).map(t =>
              <option value={t.id} key={t.id}>{t.original_source_name || incidentName(t.id)}</option>)}
          </select>
        </Field>
      </div>
      {modelRows.some(x => x.completed > 0) ? <div className="table-wrap">
        <table>
          <thead><tr><th>Model</th><th>Completed trials</th><th>Strict passes</th><th>Safe repairs</th></tr></thead>
          <tbody>{modelRows.filter(x => x.completed > 0).map((group, index) =>
            <tr key={`${group.model}-${index}`}>
              <td>{modelDisplay(group.model)}</td>
              <td>{group.completed}</td>
              <td>{group.strict_passes} / {group.completed}</td>
              <td>{group.complete_safe_repairs} / {group.completed}</td>
            </tr>)}</tbody>
        </table>
      </div> : <p className="muted">No completed trials for this incident yet.</p>}
      <p className="muted">Comparisons use recorded episodes and matching task versions. Open an individual result to inspect its exact settings and evidence.</p>
    </Panel>
  </div>;
}
