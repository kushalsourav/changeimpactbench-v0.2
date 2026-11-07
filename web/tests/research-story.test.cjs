const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const get = (p) => fs.readFileSync(path.join(__dirname, '..', p), 'utf8');
const overview = get('pages/Overview.tsx');
const lab = get('pages/IncidentLab.tsx');
const analysis = get('pages/ExecutionAnalysis.tsx');
const state = get('hooks/useWorkbench.tsx');
const ui = get('components/ui/index.tsx');
const css = get('app/globals.css');

test('First screen describes the research objective before metrics',()=>{
 assert.match(overview,/Can an AI fix an outage and explain what failed\?/);
 assert.match(overview,/RECORDED EPISODE/);
 assert.match(overview,/independent Python grader/i);
 assert.match(overview,/Inspect the evidence/);
});
test('Before-and-after cells rely on actual sandbox outcomes, not invented numbers',()=>{
 assert.match(ui,/function IncidentStateStrip/);
 assert.match(overview,/storyServices\.length > 0 && storyAfterDown/);
 assert.match(overview,/actualEffect\?\.action_id/);
 assert.match(overview,/explanation\.missing\.length \+ explanation\.extra\.length/);
 assert.match(overview,/trial\.human_review\?\.status/);
 assert.doesNotMatch(overview,/const exampleData|Math\.random/);
});
test('One trial is identified as a case study, not a model performance rate',()=>{
 assert.match(overview,/crossRun && crossRunCompleted >= 2/);
 assert.match(overview,/One completed episode is a case study, not a comparison/);
 assert.match(overview,/same task version and settings|task version and settings/i);
});
test('Actual repair and simulated what-if are never confused',()=>{
 assert.match(state,/const actionId = labMode === 'actual' \? labCommittedAction : \(previewActionId \|\| ''\)/);
 assert.match(lab,/Actual agent execution/);
 assert.match(lab,/Hypothetical repair · not executed by the agent/);
 assert.match(lab,/Counterfactual preview only/);
 assert.match(state,/setLabMode\('actual'\)/);
 assert.match(state,/setRepairState\('before'\)/);
});
test('Evidence links are direct and human review does not rewrite deterministic score',()=>{
 assert.match(overview,/setExpandedEvent\(step\.eventId\);setPage\('analysis'\)/);
 assert.match(analysis,/values=\{\['Summary','Tool trace','Integrity checks'\]\}/);
 assert.match(css,/\.research-service-cells/);
 assert.match(css,/\.research-journey-link/);
 assert.doesNotMatch(css.slice(css.indexOf('/* v0.9.4')),/linear-gradient|@keyframes/);
});
