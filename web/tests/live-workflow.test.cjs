const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const source = readFileSync(join(__dirname, '..', 'lib/live-activity.ts'), 'utf8');

test('workflow parser maps only known tool types to recorded stages', () => {
  for (const tool of ['prepare_repair', 'simulate_repair', 'apply_repair', 'submit_diagnosis']) {
    assert.ok(source.includes(`tools: ['${tool}']`), `missing stage for ${tool}`);
  }
  assert.match(source, /parseLiveActivity\(segment\)/);
  assert.match(source, /observedStages/);
  assert.match(source, /nextTrialHasStarted/);
});

test('live workflow accepts every provider adapter and terminal-log prefixes', () => {
  for (const provider of ['provider', 'Anthropic', 'Gemini']) assert.ok(source.includes(provider));
  assert.match(source, /ChangeImpactBench agent pid/);
  assert.match(source, /\(\?:→\|->\)/);
});

test('launch response immediately identifies the active run before the first poll', () => {
  const workbench = readFileSync(join(__dirname, '..', 'hooks/useWorkbench.tsx'), 'utf8');
  for (const field of ['id: r.id', 'task_id: r.task_id', 'models: r.models', 'trials: r.trials'])
    assert.ok(workbench.includes(field), `missing launch field ${field}`);
  assert.match(workbench, /s\.status === 'idle'/);
});

test('disk-restored run status reconnects the Run page to saved results', () => {
  const workbench = readFileSync(join(__dirname, '..', 'hooks/useWorkbench.tsx'), 'utf8');
  const control = readFileSync(join(__dirname, '..', 'pages/ControlRoom.tsx'), 'utf8');
  const api = readFileSync(join(__dirname, '..', 'lib/api.ts'), 'utf8');
  assert.match(api, /restored_from_disk\?: boolean/);
  assert.match(control, /Recovered from results folder/);
  assert.match(workbench, /getJSON<RunStatus>\('\/api\/experiment\/status'\)/);
});

test('workflow keeps the currently observed stage active like the demo', () => {
  assert.match(source, /i < reached\s*\? 'done'/);
  assert.match(source, /i === reached\s*\? 'current'/);
  assert.match(source, /Unverified, no completed grade/);
});

test('live repair observations retain zero-outage outcomes and action details', () => {
  const observations = readFileSync(join(__dirname, '..', 'lib/live-observations.ts'), 'utf8');
  assert.match(observations, /newly_unavailable_count/);
  assert.match(observations, /unavailable_after_count/);
  assert.match(observations, /committed_in_sandbox/);
  assert.match(observations, /Raw configuration inspected/);
  assert.match(source, /newOutages != null/);
});
