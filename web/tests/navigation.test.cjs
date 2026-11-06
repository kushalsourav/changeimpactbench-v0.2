const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname,'../app/page.tsx'),'utf8');
const nav = source.match(/const NAV:[\s\S]*?= \[([\s\S]*?)\];/);
test('exactly four active research sections',()=>{
  assert.ok(nav, 'NAV declaration found');
  const ids=[...nav[1].matchAll(/id: '([^']+)'/g)].map(x=>x[1]);
  assert.deepEqual(ids,['overview','lab','control','analysis']);
});
test('Execution Analysis exposes exactly the three requested views',()=>{
  assert.match(source,/values=\{\['Explanation','Full timeline','Verification'\]\}/);
  assert.match(source,/page === 'analysis'/);
  assert.doesNotMatch(source,/page === 'evidence'|page === 'results'|page === 'traces'/);
  assert.match(source,/openSavedEvidence\(e\.run, e\.index\)/);
});
test('full trace and reproducibility exports are available in the four-tab interface',()=>{
  assert.match(source,/agentTraceItems\(trial\.record\)/);
  assert.match(source,/\/raw\.jsonl/);
  assert.match(source,/\/bundle\.zip/);
  assert.match(source,/Review status|Human semantic review/);
});
