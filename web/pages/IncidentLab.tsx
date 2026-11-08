'use client';
import { ArrowRight } from 'lucide-react';
import { Topology } from '../components/Topology';
import { short, incidentName, incidentLabel } from '../lib/presentation';
import {
  Status,
  Panel,
  Empty,
  Json,
  Code
} from '../components/ui';
import { useWorkbenchState } from '../store/WorkbenchContext';
export function IncidentLab() {
  const { info, task, nodeId, setNodeId, previewActionId, setPreviewActionId, repairState, setRepairState, labMode, setLabMode, labSideView, setLabSideView, recordIndex, setRecordIndex, trial, reviewer, chooseTrial, launch, rows, completed, incomplete, selected, activeLabTaskId, labCommittedAction, actionId, recordedPreview, labTask, affected, repairs, repair, shownDown, directFailures, labDataset, setLabDataset, tasks, run } = useWorkbenchState();
  return (
            <>
              {!run && <div className="incident-public-chooser"><strong>Explore a V6 synthetic counterfactual incident</strong><select aria-label="Explore incident dataset" value={labDataset} onChange={(e) => setLabDataset(e.target.value)}>{tasks.map((t) => <option key={t.id} value={t.id}>{incidentLabel(t.id)}</option>)}</select><small>This is a reviewer-only reference graph, not an observation revealed to an AI agent.</small></div>}
              {!labTask || !activeLabTaskId ? (
                <Panel title="Loading incident reconstruction" description="Incident Lab can be explored before any model evaluation.">
                  <Empty title="Loading reconstructed incident topology" detail="Select a dataset above to explore its service graph without any saved model run." />
                </Panel>
              ) : (
                <>
                  <div className="incident-lab-layout">
                  {labTask?.case.provenance?.source_url && <div className="incident-source-note"><strong>Public incident inspiration; synthetic simulator:</strong> <a href={String(labTask.case.provenance.source_url)} target="_blank" rel="noopener noreferrer">Original postmortem</a> · The topology and candidate repairs are models, not captured production internals.</div>}
                    <Panel
                      title={incidentName(activeLabTaskId)}
                      description={labTask ? `${incidentLabel(activeLabTaskId)} · ${labTask.case.facts.topology.length} services · ${affected.length} initially unavailable · reviewer-only reference` : `Loading ${activeLabTaskId} topology`}
                      side={
                        <div className="chipbar" aria-label="Incident repair state">
                          <button className={`button ${repairState === 'before' ? 'primary' : ''}`} onClick={() => setRepairState('before')}>Initial outage</button>
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
                            <button type="button" className={`button ${labMode === 'whatif' ? 'primary' : ''}`} aria-pressed={labMode === 'whatif'} onClick={() => { setLabMode('whatif'); setPreviewActionId(labTask.case.actions[0]?.id || ''); setRepairState('after'); }}>Try a repair in the sandbox</button>
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
                                  <dt>Fault classification</dt>
                                  <dd>{shownDown.includes(node.id) ? directFailures.includes(node.id) ? 'Local check failed (direct fault)' : 'Unavailable due to upstream dependencies' : 'Healthy'}</dd>
                                  <dt>Initial state</dt><dd>{affected.includes(node.id) ? 'Unavailable' : 'Healthy'}</dd>
                                  <dt>Displayed state</dt><dd>{shownDown.includes(node.id) ? 'Unavailable' : 'Healthy'}</dd>
                                </dl>
                                {(() => {
                                  const localRules = labTask.case.facts.local_rules;
                                  const rules = Array.isArray(localRules) ? localRules as Array<{service:string;when:unknown}> : [];
                                  const local = rules.find(r=>r.service===node.id);
                                  return local ? <details className="story-raw"><summary>Exact synthetic local check</summary><p className="muted">Reviewer-only failure rule. The agent must obtain this evidence through its own inspect_config tool.</p><Json value={local.when}/></details> : null;
                                })()}
                              </div>
                            ) : <Empty title="Service not found" detail="Select a valid node from the current incident." />;
                          })()
                        ) : (
                          <div className="incident-intro-inspector">
                            <h3>Understand the outage</h3>
                            <p>This reconstruction contains {labTask?.case.facts.topology.length || '?'}-service system. {affected.length} services were unavailable initially, caused by local failures and dependency cascades.</p>
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

  );
}
