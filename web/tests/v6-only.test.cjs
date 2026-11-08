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
  assert.match(text, /setMaxInputTokens/);
  assert.match(text, /Max input tokens per trial/);
  assert.match(text, /setEffort/);
  assert.match(text, /Max output tokens per response/);
  assert.match(text, /last request may cross it/);
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
  assert.match(text, /observedHealth=\{observedHealth\}/);
  assert.doesNotMatch(text, /progress\s*\}/);
  const graph = source('components/Topology.tsx');
  assert.match(graph, /observation === 'healthy'/);
  assert.match(graph, /Observed unavailable/);
});

test('Results remain connected to saved trials and evidence', () => {
  const text = source('pages/Overview.tsx');
  assert.match(text, /info\?\.rows\.map/);
  assert.match(text, /openSavedEvidence/);
  assert.match(text, /setRecordIndex\(index\)/);
  assert.match(text, /comparisonTask/);
  assert.match(text, /crossRun/);
});

test('compact white UI excludes mock playback, theme toggle, and long launch introduction', () => {
  const shell = source('components/ResearchShell.tsx');
  const control = source('pages/ControlRoom.tsx');
  const stylesheet = source('app/cib-light.css');
  assert.doesNotMatch(control, /Test an AI incident responder|Choose an incident and a model to begin/);
  assert.doesNotMatch(shell, /Toggle theme|Moon|Sun|Play.*Restart|Load run file/);
  assert.match(stylesheet, /--desk:#fff/);
  assert.match(control, /currentEpisodeLog/);
  assert.match(control, /healthFromLog/);
  assert.match(source('pages/Overview.tsx'), /savedRunFacts/);
});


test('input token budget is wired from the Run page to backend request and saved results', () => {
  assert.match(source('hooks/useWorkbench.tsx'), /max_input_tokens: maxInputTokens/);
  assert.match(source('pages/Overview.tsx'), /selected\.max_input_tokens/);
  assert.match(source('lib/saved-run-facts.ts'), /input_token_budget/);
});
