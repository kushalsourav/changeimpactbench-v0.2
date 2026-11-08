'use client';
import {
  BarChart,
  Bar,
  ResponsiveContainer,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend
} from 'recharts';
import { ArrowRight, Check, Info, Play } from 'lucide-react';
import { API } from '../lib/api';
import {
  CHART_FONT,
  p100,
  modelDisplay,
  isAgenticTask,
  incidentLabel,
  incidentName,
  statusLabel,
  safe
} from '../lib/presentation';
import { Panel, Empty, IncidentStateStrip, Field } from '../components/ui';
import { ResearchSynthesis } from '../components/ResearchSynthesis';
import { useWorkbenchState } from '../store/WorkbenchContext';
export function Overview() {
  const { setPage, run, tasks, task, setNodeId, setRepairState, setLabMode, setLabSideView, trial, setAnalysisTab, setExpandedEvent, error, filter, models, comparisonTask, setComparisonTask, crossRun, temperature, openSavedEvidence, launch, summaries, completed, incomplete, tokens, comparison, selected, agentEvents, repairs, repair, selectedTrialReady, explanation, storyServices, actualEffect, storyInitialDown, storyAfterDown, crossRunCompleted, crossRunChart, counts } = useWorkbenchState();
  return (
            <>
              <section className="research-hero" aria-label="Research question">
                <div className="research-eyebrow">CHANGEIMPACTBENCH / AI RELIABILITY RESEARCH</div>
                <h1>Can an AI fix an outage and explain what failed?</h1>
                <p>Six fully synthetic V6 counterfactual incidents are inspired by published GitHub and Cloudflare postmortems. Agents investigate through bounded tools; an independent Python oracle verifies the diagnosis and sandbox repair. The original incident names appear for reviewer attribution only—not in agent prompts or actual production telemetry.</p>
                <div className="research-hero-actions">
                  <button className="button primary" onClick={() => setPage('lab')}>Explore the incident <ArrowRight size={15}/></button>
                  <button className="button" onClick={() => setPage('control')}>Run an AI experiment <Play size={14}/></button>
                  <span>Public-source inspiration · Synthetic sandbox · Verified outcomes</span>
                </div>
              </section>
              {selected && selectedTrialReady && trial ? (
                <section className="research-feature" aria-label="Featured observed experiment">
                  <div className="research-feature-header">
                    <div><div className="research-eyebrow">RECORDED EPISODE · {incidentName(selected.task)} ({selected.task}) · TRIAL {selected.trial}</div><h2>{explanation?.title || (selected.status !== 'completed' ? 'No gradeable model result' : selected.pass ? 'The model met the strict criteria' : 'The response differs from the verified reference')}</h2><p>{modelDisplay(selected.model)} · {selected.status === 'completed' ? 'Completed provider episode' : statusLabel(selected.status)}</p></div>
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
                            <div className="research-journey-item"><span className="research-journey-index">01</span><div><strong>Investigated the outage</strong><p>{agentEvents.filter(e=>['read_alert','scan_service_health','inspect_config','inspect_dependencies','inspect_logs','inspect_metrics'].includes(e.tool)).length} recorded investigation tool calls; the task's reference answer was hidden from the agent.</p></div></div>
                            {explanation.steps.map((step, i) => (
                              <button key={step.eventId} className="research-journey-item research-journey-link" onClick={() => {setAnalysisTab('Tool trace');setExpandedEvent(step.eventId);setPage('analysis');}}>
                                <span className="research-journey-index">{String(i+2).padStart(2,'0')}</span><div><strong>{step.label === 'Simulated' ? `Tested repair ${step.action}` : `Committed repair ${step.action}`}</strong><p>{step.remaining == null ? 'Effect unavailable in this record' : `${step.remaining} services remain down`} · {step.newOutages ?? '?'} new outages · turn {step.turn} / {step.eventId}</p></div><ArrowRight size={14}/>
                              </button>
                            ))}
                            <div className="research-journey-item"><span className="research-journey-index">{String(explanation.steps.length+2).padStart(2,'0')}</span><div><strong>Submitted the incident report</strong><p>{explanation.missing.length + explanation.extra.length ? `${explanation.missing.length + explanation.extra.length} service classification errors in the original outage inventory.` : explanation.strictlyPassed ? 'Exact initial impact and diagnosis verified.' : 'Check the strict criterion differences in Episode evidence.'}</p></div></div>
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

                          <button className="button primary" onClick={() => {setAnalysisTab('Summary');setPage('analysis');}}>Inspect the evidence <ArrowRight size={14}/></button>
                        </div>
                      </div>
                    </>
                  ) : (
                    <div className="research-sample-note"><Info size={18}/><span>Incomplete or non-gradeable attempts cannot be presented as successful recoveries. Open its original evidence for details.</span></div>
                  )}
                </section>
              ) : <section className="research-feature research-empty-feature"><h2>No saved AI investigation yet</h2><p>Start a real investigation to see the agent’s decisions, the recorded repair, and independent verification here. We never fabricate demo scores.</p><button className="button primary" onClick={()=>setPage('control')}>Configure an experiment <ArrowRight size={14}/></button></section>}
              {run && <ResearchSynthesis run={run} models={models}/>}
              <details className="research-methodology"><summary>How is the result evaluated?</summary>
              <section className="research-method" aria-label="Evaluation method and evidence limits">
                <div><strong>1 · Investigate</strong><span>LangChain create_agent on LangGraph investigates a postmortem-grounded reconstructed sandbox.</span></div>
                <div><strong>2 · Verify</strong><span>Deterministic Python independently replays tool requests, repair state and submitted facts.</span></div>
                <div><strong>3 · Review</strong><span>Visible tool evidence and provider-exposed summaries can be reviewed; hidden model thoughts are not available.</span></div>
              </section>
              <p className="muted">Only V6 counterfactual tasks appear in active research results; old snapshots cannot be regraded using a different source hash.</p>
              </details>
              <div className="research-comparison-heading"><div><span className="research-eyebrow">ACROSS EXPERIMENTS</span><h2>Does this behavior repeat across models?</h2><p>Every chart below uses real saved episodes. Different versions and generation settings are never pooled.</p></div></div>
              <Panel title="Model comparison · observed evidence" description="Same task version and model settings only. Real completed episodes are the denominator; provider errors are excluded.">
                <div className="row-gap">
                  <div className="toolbar">
                    <Field label="Benchmark task version">
                      <select aria-label="Compare agentic task version" value={comparisonTask} onChange={(e) => setComparisonTask(e.target.value)}>
                        {tasks.filter((t) => isAgenticTask(t.id)).map((t) => <option key={t.id} value={t.id}>{incidentLabel(t.id)} · {t.services} services</option>)}
                      </select>
                    </Field>
                    <div className="grow" />
                    <span className="muted">{crossRun?.groups.reduce((n, g) => n + g.completed, 0) ?? 0} completed · {crossRun?.groups.length ?? 0} model/settings groups</span>
                  </div>
                  {crossRun && crossRunCompleted >= 2 ? (
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
                              {incidentName(comparisonTask)} · episode {e.index + 1} · {e.status} <ArrowRight size={12}/>
                            </button>
                          )))}
                        </div>
                      </div>
                    </>
                  ) : (
                    <div className="research-sample-note"><Info size={17}/><div><strong>{crossRunCompleted === 1 ? 'One completed episode is a case study, not a comparison.' : 'No model comparison yet.'}</strong><p>{crossRunCompleted === 1 ? 'Complete at least one additional episode with the same frozen incident and generation settings to compare results. The saved episode remains visible above.' : 'Run real episodes in Control Room. No example scores or projected rates are shown.'}</p></div></div>
                  )}
                  <p className="muted">{crossRun?.scope || 'Loading version-specific comparison from FastAPI.'} A single episode does not establish repeatability; use at least three trials per model and task when possible.</p>
                </div>
              </Panel>
            </>

  );
}
