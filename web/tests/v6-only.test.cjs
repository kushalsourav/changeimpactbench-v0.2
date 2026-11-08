const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync, existsSync } = require('node:fs');
const { join } = require('node:path');
const root = join(__dirname, '..');
const source = name => readFileSync(join(root, name), 'utf8');

test('frontend exposes only V6 counterfactual task IDs', () => {
  const text = source('lib/presentation.tsx');
  const ids = [...text.matchAll(/RW\d{2}V6CF/g)].map(x => x[0]);
  assert.equal(new Set(ids).size, 6);
  assert.ok(!/RW\d{2}V(?:4|5|6N)/.test(text));
  assert.match(text, /Cloudflare/);
  assert.match(text, /GitHub/);
});

test('Run a Test uses server tasks and retains editable output token and reasoning controls', () => {
  const text = source('pages/ControlRoom.tsx');
  assert.match(text, /tasks\.map\(/);
  assert.match(text, /original_source_name/);
  assert.match(text, /setMaxTokens/);
  assert.match(text, /setEffort/);
  assert.match(text, /Max output tokens per response/);
  assert.match(text, /not input context/);
  assert.match(text, /Approve up to/);
  assert.doesNotMatch(text, /NATIVE AGENT EXPERIMENT|A saved episode can be non-gradeable/);
});

test('Incident Lab page is removed, with only Run a Test and Results in navigation', () => {
  assert.equal(existsSync(join(root, 'pages/IncidentLab.tsx')), false);
  const nav = source('lib/presentation.tsx');
  assert.doesNotMatch(nav, /'lab'|Incident lab/i);
  assert.match(nav, /Run a Test/);
  assert.match(nav, /Results/);
  const shell = source('components/ResearchShell.tsx');
  assert.doesNotMatch(shell, /IncidentLab|page === 'lab'|page !== 'lab'/);
});

test('Live UI shows actual workflow and neutral dependency graph', () => {
  const text = source('pages/ControlRoom.tsx');
  assert.match(text, /parseLiveWorkflow\(job\.log/);
  assert.match(text, /workflow\.steps\.map/);
  assert.match(text, /topology\.case\.facts\.topology/);
  assert.match(text, /failed=\{\[\]\} unknown/);
  assert.doesNotMatch(text, /progress\s*\}/);
  const graph = source('components/Topology.tsx');
  assert.match(graph, /unknown \? 'unknown'/);
  assert.match(graph, /Status not shown during investigation/);
});

test('Results remain connected to saved trials and evidence', () => {
  const text = source('pages/Overview.tsx');
  assert.match(text, /info\.rows\.map/);
  assert.match(text, /openSavedEvidence/);
  assert.match(text, /comparisonTask/);
  assert.match(text, /crossRun/);
});
