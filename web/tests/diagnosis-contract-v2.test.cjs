/** Frontend contract: exact hypothesis ID and protocol penalties are separate. */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.join(__dirname,'..');
const source=p=>fs.readFileSync(path.join(root,p),'utf8');
test('Episode evidence distinguishes machine-scored ID from human-reviewed explanation',()=>{
  const evidence=source('pages/ExecutionAnalysis.tsx');
  assert.match(evidence,/Agent's hypothesis ID/);
  assert.match(evidence,/Agent's causal explanation/);
  assert.match(evidence,/Pending human evidence review/);
  assert.match(evidence,/Why strict evaluation failed/);
  assert.match(evidence,/Where the points came from/);
  assert.match(evidence,/rejected tool call does not mean the committed repair was unsafe/);
});
test('User sees only prospective v2 tasks and no historical pooled scores',()=>{
  const labels=source('lib/presentation.tsx');
  const defaults=source('hooks/useWorkbench.tsx');
  assert.match(labels,/RW01V3', 'RW02V3', 'RW03V3'/);
  assert.match(defaults,/useState\(\['RW01V4'\]\)/);
  assert.match(defaults,/useState\('RW01V4'\)/);
});
