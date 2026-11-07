const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const get = (p) => fs.readFileSync(path.join(__dirname, '..', p), 'utf8');
const presentation = get('lib/presentation.tsx');
const app = get('app/page.tsx');
const shell = get('components/ResearchShell.tsx');
const analysis = get('pages/ExecutionAnalysis.tsx');
const state = get('hooks/useWorkbench.tsx');

test('Exactly four research screens are registered', () => {
  const match = presentation.match(/export const NAV:[\s\S]*?= \[([\s\S]*?)\];/);
  assert.ok(match);
  assert.deepEqual([...match[1].matchAll(/id: '([^']+)'/g)].map(x => x[1]),
    ['overview','lab','control','analysis']);
  assert.match(shell, /<Overview \/>/);
  assert.match(shell, /<IncidentLab \/>/);
  assert.match(shell, /<ControlRoom \/>/);
  assert.match(shell, /<ExecutionAnalysis \/>/);
});

test('Next.js route contains only typed application composition', () => {
  assert.match(app, /WorkbenchContext.Provider/);
  assert.match(app, /useWorkbench\(\)/);
  assert.ok(app.split('\n').length < 40);
  assert.doesNotMatch(app, /const \[selectedModels/);
});

test('Analysis contains explanation, complete timeline and verification in one screen', () => {
  assert.match(analysis,/values=\{\['Summary','Tool trace','Integrity checks'\]\}/);
  assert.match(analysis,/agentTraceItems\(trial\.record\)/);
  assert.match(analysis,/\/raw\.jsonl/);
  assert.match(analysis,/\/bundle\.zip/);
  assert.match(analysis,/Human semantic review/);
  assert.match(analysis,/Sandbox safety violation recorded/);
  assert.match(analysis,/trace-timeline/);
});

test('Saved run selection resets stale record and evidence references', () => {
  assert.match(state,/setRecordIndex\(0\);/);
  assert.match(state,/setTrial\(null\);/);
  assert.match(state,/list\.length === 0/);
  assert.match(state,/runFetchSequence\.current/);
  assert.match(state,/recordFetchSequence\.current/);
});
