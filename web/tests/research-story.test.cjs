const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const page = fs.readFileSync(path.join(__dirname,'../app/page.tsx'),'utf8');
const css = fs.readFileSync(path.join(__dirname,'../app/globals.css'),'utf8');
const overview = page.slice(page.indexOf("{page === 'overview' && ("),page.indexOf("{page === 'lab' && ("));
const lab = page.slice(page.indexOf("{page === 'lab' && ("),page.indexOf("{page === 'analysis' && ("));
test('First screen explains research objective before specialist metrics',()=>{
 assert.match(overview,/Can an AI fix an outage and explain what failed\?/);
 assert.match(overview,/real saved episode|OBSERVED EPISODE/i);
 assert.match(overview,/independent Python evaluator/i);
 assert.match(overview,/Inspect the evidence/);
 assert.match(page,/page !== 'lab' && page !== 'overview'/);
});
test('Before-after tiles display actual frozen incident evidence, no invented numbers',()=>{
 assert.match(page,/function IncidentStateStrip/);
 assert.match(overview,/storyServices\.length > 0 && storyAfterDown/);
 assert.match(overview,/actualEffect\?\.action_id/);
 assert.match(overview,/explanation\.missing\.length \+ explanation\.extra\.length/);
 assert.match(overview,/trial\.human_review\?\.status/);
 assert.doesNotMatch(overview,/const exampleData|Math\.random/);
});
test('One trial does not render misleading percentage comparison chart',()=>{
 assert.match(overview,/crossRunCompleted > 1 \? <div className="chart-panels">/);
 assert.match(overview,/One completed episode is a case study, not a performance estimate/);
 assert.match(overview,/same task version and settings|task version and settings/i);
});
test('Actual repair is isolated from optional counterfactual preview',()=>{
 assert.match(page,/const actionId = labMode === 'actual' \? labCommittedAction : \(previewActionId \|\| ''\)/);
 assert.match(lab,/Actual agent execution/);
 assert.match(lab,/Explore alternative repairs/);
 assert.match(lab,/Hypothetical repair · not executed by the agent/);
 assert.match(lab,/Counterfactual preview only/);
 assert.match(page,/setLabMode\('actual'\)/);
 assert.match(page,/setRepairState\('before'\)/);
 assert.match(lab,/Before outage/);
});
test('Research story preserves raw evidence access and restrained static styling',()=>{
 assert.match(page,/setExpandedEvent\(step\.eventId\);setPage\('analysis'\)/);
 assert.match(page,/values=\{\['Explanation','Full timeline','Verification'\]\}/);
 assert.match(css,/\.research-service-cells/);
 assert.match(css,/\.research-journey-link/);
 assert.doesNotMatch(css.slice(css.indexOf('/* v0.9.4')),/linear-gradient|@keyframes/);
});
