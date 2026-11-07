'use client';
import { ResearchSynthesis } from '../components/ResearchSynthesis';
import {
  AlertTriangle,
  ArrowRight,
  Check,
  Download,
  FileCheck2,
  Info,
  Shield
} from 'lucide-react';
import { getJSON, postJSON } from '../lib/api';
import type { Task, TrialDetail } from '../lib/api';
import {
  p100,
  modelDisplay,
  short,
  date,
  isGraphTask,
  isAgenticTask,
  agentTraceItems,
  duration,
  safe
} from '../lib/presentation';
import {
  Status,
  Panel,
  Empty,
  Json,
  Code,
  Field,
  Tabs,
  DownloadLink,
  Integrity
} from '../components/ui';
import { useWorkbenchState } from '../store/WorkbenchContext';
import { observedEventSummary, eventArguments } from '../lib/trace-summary';
import { incidentName } from '../lib/presentation';
export function ExecutionAnalysis() {
  const { runs, run, task, recordIndex, setRecordIndex, trial, setTrial, analysisTab, setAnalysisTab, expandedEvent, setExpandedEvent, error, search, filter, setFilter, modelFilter, setModelFilter, models, reviewer, setReviewer, reviewNotes, setReviewNotes, reviewStatus, setReviewStatus, reviewChecks, setReviewChecks, reviewBusy, setReviewBusy, reviewMessage, setReviewMessage, refreshRun, launch, rows, matching, summaries, completed, incomplete, selected, affected, repair, explanation } = useWorkbenchState();
  const scoring = (trial?.audit.grade?.criterion_scores || {}) as Record<string, {earned:number;available:number;measurement:string}>;
  const rejectedReasons = (trial?.audit.grade?.strict_failure_reasons || []) as string[];
  const reasonLabels: Record<string,string> = {
    initial_service_inventory_inexact: 'The initial affected-service inventory does not exactly match the reference',
    root_cause_id_incorrect: 'The selected root-cause hypothesis ID is incorrect',
    repair_not_reference_optimal: 'Repair choice or commitment is not the reference lowest-cost safe repair',
    unsafe_repair: 'Committed repair introduced an unsafe outcome',
    incomplete_recovery: 'At least one initially unavailable service was not recovered',
    rejected_tool_attempts: 'At least one tool request was rejected; inspect the raw tool trace for the exact reason',
    insufficient_evidence_provenance: 'Insufficient verified event-ID citations',
  };
  const scoreLabels: Record<string,string> = {
    impact:'Initial affected-service inventory',
    root_cause_id:'Root-cause hypothesis ID',
    safe_complete_recovery:'Complete and safe sandbox recovery',
    evidence_provenance:'Evidence event-ID provenance',
    protocol_discipline:'Tool protocol discipline',
  };
  return (
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
                <Panel title="Saved episodes" description="Select an actual recorded investigation">
                  <div className="trial-list">
                    {matching.map((r)=><button className={`record-button ${recordIndex===r.index?'active':''}`} key={r.index} onClick={()=>{setRecordIndex(r.index);setAnalysisTab('Summary');}}>
                      <span><strong>{incidentName(r.task)} · trial {r.trial}</strong><small style={{display:'block'}}>{short(r.model)}</small><small className="muted">{r.pass === null ? 'Not gradeable' : r.pass ? 'Strict pass' : 'Strict fail'} · {p100(r.score)}</small></span>
                    </button>)}
                    {!matching.length && <Empty title="No matching attempts"/>}
                  </div>
                </Panel>
                <Panel title="Episode evidence" description={selected ? `${incidentName(selected.task)} (${selected.task}) · ${modelDisplay(selected.model)} · trial ${selected.trial}` : 'Select an experiment'} side={selected && <Status value={selected.status}/>}>
                  {selected && trial ? <>
                    {typeof trial.record.error_category === 'string' && <div className="notice error" role="alert"><AlertTriangle size={16}/><span><strong>Execution issue: {trial.record.error_category.replaceAll('_',' ')}</strong> · {typeof trial.record.error === 'string' ? trial.record.error : 'See the redacted exception details below.'} This is not a scored model diagnosis. LangGraph recursion limits and provider quotas are separate limits.</span></div>}
                    {Array.isArray(trial.audit.grade?.violations) && trial.audit.grade.violations.length > 0 &&
                      <div className="notice error" role="alert"><AlertTriangle size={18}/><span><strong>Sandbox safety violation recorded.</strong> Review independent replay and committed service state before interpreting the score.</span><button className="button" onClick={() => setAnalysisTab('Integrity checks')}>Inspect verification</button></div>}

                    {task?.case?.provenance?.source_url && <p className="muted"><strong>External source: </strong><a target="_blank" rel="noopener noreferrer" href={String(task.case.provenance.source_url)}>Read original operator postmortem</a> · Model service graph and repair costs are reconstructed, not production telemetry.</p>}
                    <Tabs values={['Summary','Tool trace','Integrity checks']} value={analysisTab} onChange={setAnalysisTab}/>
                    <div className="section-space row-gap">
                      {analysisTab === 'Summary' ? (<><ResearchSynthesis run={run} models={models}/>
                        <div className="row-gap">
                          <div className="story-verdict">
                            <div><span className="label">Automatically derived from recorded evidence</span><h2>{explanation?.title || (selected.pass ? 'Exact answer verified' : selected.status === 'completed' ? 'Diagnosis differs from reference' : 'Not gradeable')}</h2><p>{explanation?.summary || (selected.status === 'completed' ? 'One or more predicted fields differ from the independent reference. See exact differences below.' : 'The provider did not produce a complete, gradeable response.')}</p></div>
                            <div className="verdict-score"><span className="label">Strict result</span><strong className={selected.pass ? 'text-success' : 'text-error'}>{selected.pass == null ? 'N/A' : selected.pass ? 'PASS' : 'FAIL'}</strong><span className="muted">Partial {p100(selected.score)}</span></div>
                          </div>
                          {selected.status === 'completed' && <p className="muted" role="status"><strong>Outcome checks:</strong> Recovery {trial.audit.grade?.recovery_success === true && trial.audit.grade?.recovery_safe === true ? 'PASS' : 'FAIL'} · Lowest-cost safe repair {trial.audit.grade?.fix_correct === true ? 'PASS' : 'FAIL'} · Strict {trial.audit.grade?.strict_pass === true ? 'PASS' : 'FAIL'} · Weighted component score {p100(selected.score)}. A 100% component score does not override a strict optimality failure.</p>}
                          <div className="analysis-first-insight"><strong>Why this result matters</strong><p>{explanation?.interpretation || 'The strict grade and partial score measure different aspects of the result.'}</p><small>Derived from the recorded agent trajectory and independently recomputed grade. Human interpretation review remains separate.</small></div>
                          {rejectedReasons.length > 0 && <section className="story-diff row-gap" aria-label="Reasons for strict failure">
                            <h3>Why strict evaluation failed</h3>
                            <ul>{rejectedReasons.map(reason=><li key={reason}>{reasonLabels[reason] || reason.replaceAll('_',' ')}</li>)}</ul>
                            <p className="muted">Diagnostic classification, recovery safety, and protocol compliance are distinct checks. A rejected tool call does not mean the committed repair was unsafe.</p>
                          </section>}
                          <div className="story-metrics">
                            <div><small>Root cause ID</small><strong>{selected.root_correct == null ? 'N/A' : selected.root_correct ? 'Correct' : 'Incorrect'}</strong></div>
                            <div><small>Initial service F1</small><strong>{p100(selected.affected_f1)}</strong></div>
                            <div><small>Lowest-cost safe repair</small><strong>{selected.fix_correct == null ? 'N/A' : selected.fix_correct ? 'PASS' : 'FAIL'}</strong></div>
                            <div><small>Recovered</small><strong>{explanation?.restored == null ? 'N/A' : `${explanation.restored}/${explanation.initialAffected ?? '?'}`}</strong></div>
                          </div>
                          {trial.record.repair_brief && <section className="story-diff row-gap" aria-label="Agent-authored repair handoff">
                            <h3>Investigation → repair · the agent's own plan</h3>
                            <p className="muted">The model wrote this repair brief from observed tool evidence. LangGraph activates the versioned repair skill afterward; the brief does not override sandbox safety rules. The independent oracle checks the actual committed result.</p>
                            <Json value={trial.record.repair_brief}/>
                            <small className="muted">Repair-phase prompt SHA-256: {safe(trial.record.repair_system_prompt_sha256)} · archived for independent replay</small>
                          </section>}
                          {isAgenticTask(selected.task) && (
                            <div className="row-gap">
                              <h3>Decision sequence · click an event to read the raw evidence</h3>
                              {explanation?.steps.length ? <div className="decision-path">
                                {explanation.steps.map((step)=><button className="decision-step" key={step.eventId} onClick={()=>{setAnalysisTab('Tool trace');setExpandedEvent(step.eventId);}}>
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
                          <div className="story-diff"><h3>Root cause and repair · separate classification and explanation</h3><dl className="keyvals"><dt>Verified hypothesis ID</dt><dd>{trial.diagnosis?.expected?.root_cause || 'N/A'}</dd><dt>Agent's hypothesis ID</dt><dd>{trial.diagnosis?.predicted?.root_cause_id || 'N/A'}</dd><dt>Agent's causal explanation</dt><dd>{trial.diagnosis?.predicted?.root_cause_explanation || 'Not submitted'}</dd><dt>Explanation semantic validation</dt><dd>{trial.human_review?.status || 'Pending human evidence review (not automatically scored)'}</dd><dt>Verified repair</dt><dd>{trial.diagnosis?.expected?.fix_id || 'N/A'}</dd><dt>Model repair</dt><dd>{trial.diagnosis?.predicted?.fix_id || 'N/A'}</dd></dl></div>
                          {explanation?.postCommitCitations.length ? <div className="notice warning"><Info size={15}/><span>The final diagnosis cites inspection evidence obtained after the sandbox repair ({explanation.postCommitCitations.join(', ')}). Current-state measurements do not necessarily describe the original failure state. Semantic review is required; this flag does not automatically change the score.</span></div> : null}
                          {explanation?.semanticWarnings.map((warning) => <div className="notice warning" key={warning}><Info size={15}/><span>{warning} The deterministic grader score is unchanged; human validation is pending.</span></div>)}

                          <p className="muted">Only recorded tool observations and deterministic grader comparisons are used. This is not an LLM-generated explanation, hidden chain-of-thought, or proof of a population-level model limitation. Human review: {trial.human_review?.status || 'pending'}.</p>
                          <div className="toolbar"><button className="button primary" onClick={()=>setAnalysisTab('Tool trace')}>Inspect original turns <ArrowRight size={14}/></button><button className="button" onClick={()=>setAnalysisTab('Integrity checks')}>View independent verification</button></div>
                        </div>
                      </>) : analysisTab === 'Tool trace' ? (
                        <div className="row-gap">
                          <div className="notice"><Shield size={15}/>Full observable trace. The agent's tool requests and synthetic responses are recorded in order; no hidden reasoning is available.</div>
                          {isAgenticTask(selected.task) ? <>
                            {Array.isArray(trial.record.protocol_errors) && trial.record.protocol_errors.length > 0 && <div className="notice warning" role="status"><AlertTriangle size={16}/>The model made {trial.record.protocol_errors.length} rejected tool request(s). These are recorded separately from sandbox safety violations.</div>}
                            {agentTraceItems(trial.record).map((step,i)=>step.kind==='rejected' ?
                              <details className="agent-event trace-step trace-timeline" key={`rej-${step.turn}-${i}`} defaultOpen={expandedEvent===`rejected-${step.turn}`}>
                                <summary><strong>Turn {step.turn} · rejected tool request</strong><span className="muted">{step.item.protocol_error}</span></summary>
                                <p className="muted">{date(step.item.timestamp_utc)} · {duration(step.item.request_elapsed_seconds)}</p><Code value={step.item.raw_model_output}/>
                              </details>
                              : <details className={`agent-event trace-step trace-timeline ${step.event.tool === 'submit_diagnosis' ? 'trace-submission' : ''}`} key={step.event.observation.event_id} defaultOpen={expandedEvent===step.event.observation.event_id}>
                                <summary>
                                  <span className="trace-event-title"><strong>Turn {step.turn} · {step.event.tool.replaceAll('_',' ')}{eventArguments(step.event) ? ` (${eventArguments(step.event)})` : ''}</strong><small>{step.event.observation.event_id} · {date(step.event.timestamp_utc)}</small></span>
                                  <span className="trace-event-summary">{observedEventSummary(step.event)}</span>
                                </summary>
                                {step.event.tool === 'submit_diagnosis' && <p className="trace-submission-verdict"><strong>Independent verdict:</strong> {selected.pass == null ? 'Not gradeable' : selected.pass ? 'Strict PASS' : 'Strict FAIL'} · partial {p100(selected.score)}</p>}
                                <div className="trace-event-detail"><h3>Model's actual tool request</h3><Json value={{tool:step.event.tool,arguments:step.event.arguments}}/>
                                <h3>Sandbox observation · {step.event.observation.event_id}</h3><Json value={step.event.observation.result}/>
                                <p className="muted">Recorded at {date(step.event.timestamp_utc)} · provider elapsed {duration(step.event.provider_elapsed_seconds)}</p>
                                <details className="story-raw"><summary>Original provider message</summary><Code value={step.event.raw_model_output}/></details></div>
                              </details>)}
                            {agentTraceItems(trial.record).length===0 && <Empty title="No accepted tool events saved" detail="Check the provider metadata below."/>}
                            {trial.record.repair_system_prompt && <details className="story-raw"><summary>Actual repair-phase system prompt · fixed rules + model-written brief</summary><Code value={trial.record.repair_system_prompt}/></details>}
                            <details className="story-raw"><summary>Reviewer-only committed state</summary><Json value={trial.record.committed_effect || {committed:false}}/></details>
                          </> : <Empty title="Only native agent evidence is supported" detail="Select an active LangGraph experiment to inspect the recorded tool trace."/>}
                          {trial.record.error_traceback_redacted && <details className="story-raw"><summary>Redacted exception traceback</summary><Code value={trial.record.error_traceback_redacted}/></details>}
                          <details className="story-raw"><summary>Exact versioned prompt</summary><Code value={trial.record.prompt || 'Prompt not embedded; see hash audit and task source.'}/></details>
                          <details className="story-raw"><summary>All raw provider turn records and token metadata</summary><Json value={trial.record.turns || [trial.record]}/></details>
                          <button className="button" onClick={()=>setAnalysisTab('Summary')}>Back to explanation</button>
                        </div>
                      ) : (
                        <div className="row-gap">
                          <div className="notice"><FileCheck2 size={16}/><span>These checks are recomputed by the FastAPI backend from the saved record. Downloads preserve the original evidence. Semantic correctness of the model's written explanation requires separate human review.</span></div>
                          {selected && isGraphTask(selected.task) && <section className="native-agent-audit">
                            <h3>Native LangGraph execution · observable evidence</h3>
                            <p>Framework: {safe(trial.record.agent_framework)} · Source: published incident / reconstructed sandbox {selected.task} scenario. Model tool requests and observations are replayed independently; no inaccessible private thoughts are claimed.</p>
                            <div className="native-audit-grid">
                              <div><span>Provider responses</span><strong>{Number(trial.record.provider_requests || 0)}</strong></div>
                              <div><span>Accepted sandbox tools</span><strong>{Number(trial.record.tool_calls || 0)}</strong></div>
                              <div><span>Rejected tool requests</span><strong>{Array.isArray(trial.record.protocol_errors) ? trial.record.protocol_errors.length : 0}</strong></div>
                              <div><span>Source replay</span><strong>{trial.audit.prompt_sha_matches && trial.audit.reference_matches ? 'Checked' : 'Unverified'}</strong></div>
                            </div>
                            <details className="story-raw"><summary>Provider-exposed reasoning metadata (if available)</summary><p>Provider summaries are observations, not unrestricted internal reasoning.</p><Json value={Array.isArray(trial.record.turns) ? (trial.record.turns as Array<Record<string,unknown>>).map(t=>({turn:t.turn,reasoning:t.provider_exposed_reasoning || null})).filter(t=>t.reasoning) : []}/></details>
                          </section>}

                          <div className="story-metrics"><div><small>Strict result</small><strong>{selected.pass == null ? 'N/A' : selected.pass?'PASS':'FAIL'}</strong></div><div><small>Partial score</small><strong>{p100(selected.score)}</strong></div><div><small>Automated citations</small><strong>{trial.audit.grade?.evidence_score == null ? 'N/A' : `${trial.audit.grade.evidence_score}/10`}</strong></div><div><small>Human review</small><strong>{trial.human_review?.status || 'Pending'}</strong></div></div>
                          <Integrity label="Prompt SHA-256 matches frozen source" status={trial.audit.prompt_sha_matches===true?'pass':trial.audit.prompt_sha_matches===false?'fail':'warning'}/>
                          <Integrity label="Stored grade matches independent replay" status={trial.audit.stored_grade_matches===true?'pass':trial.audit.stored_grade_matches===false?'fail':'warning'}/>
                          <Integrity label="Reference matches deterministic oracle" status={trial.audit.reference_matches===true?'pass':trial.audit.reference_matches===false?'fail':'warning'}/>
                          {Object.keys(scoring).length > 0 && <section className="story-diff row-gap" aria-label="Independent point breakdown">
                            <h3>Where the points came from</h3>
                            <table className="score-breakdown"><thead><tr><th>Evaluated capability</th><th>Earned</th><th>Maximum</th></tr></thead><tbody>
                              {Object.entries(scoring).map(([key,part])=><tr key={key}><td>{scoreLabels[key] || key}</td><td>{part.earned}</td><td>{part.available}</td></tr>)}
                            </tbody></table>
                            <p className="muted">Root-cause ID and repair outcomes are verified algorithmically. Free-form explanation quality is human-reviewed, never treated as automatically correct by this rubric.</p>
                          </section>}
                          <div className="story-diff"><h3>Rejected tool requests · recorded reasons</h3>{((trial.record.tool_attempts || []) as Array<{tool?:string;provider_turn?:number;rejected_reason?:string}>).filter(a=>a.rejected_reason).map((a,i)=><p key={i}><strong>Turn {a.provider_turn} · {a.tool}</strong>: {a.rejected_reason}</p>)}{!((trial.record.tool_attempts || []) as Array<{rejected_reason?:string}>).some(a=>a.rejected_reason) && <p>No rejected requests recorded.</p>}</div><div className="story-diff"><h3>Grading breakdown</h3><dl className="keyvals"><dt>Initial affected-service F1</dt><dd>{p100(selected.affected_f1)}</dd><dt>Combined root cause</dt><dd>{selected.root_correct==null?'N/A':selected.root_correct?'Correct':'Incorrect'}</dd><dt>Repair selection</dt><dd>{selected.fix_correct==null?'N/A':selected.fix_correct?'Correct':'Incorrect'}</dd><dt>Complete & safe recovery</dt><dd>{trial.audit.grade?.recovery_success === true && trial.audit.grade?.recovery_safe === true ? 'Pass' : trial.audit.grade?.recovery_success === false ? 'Failed' : 'N/A'}</dd><dt>Unsafe committed repair</dt><dd>{trial.audit.grade?.unsafe_commit ? 'Yes' : 'No'}</dd><dt>Rejected tool attempts</dt><dd>{Array.isArray(trial.audit.grade?.protocol_errors) ? trial.audit.grade.protocol_errors.length : 0}</dd><dt>Human semantic evidence review</dt><dd>{trial.human_review?.status || 'Pending — automated provenance is not semantic support'}</dd></dl></div>
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

  );
}
