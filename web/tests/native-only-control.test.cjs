const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const get = (p) => fs.readFileSync(path.join(__dirname, '..', p), 'utf8');
const presentation = get('lib/presentation.tsx');
const workbench = get('hooks/useWorkbench.tsx');
const control = get('pages/ControlRoom.tsx');
const api = get('lib/api.ts');

test('Control Room exposes one LangGraph agent track and three public incident cases', () => {
  assert.match(presentation, /RW01V3', 'RW02V3', 'RW03V3'/);
  assert.match(control, /CHANGEIMPACTBENCH \/ NATIVE AGENT EXPERIMENT/);
  assert.doesNotMatch(control, /single-turn/i);
  assert.doesNotMatch(api, /single-turn/);
});

test('48 real requests require exact budget and explicit approval', () => {
  assert.match(workbench, /const plan = selectedModels.length \* selectedTasks.length \* trialCount \* 48;/);
  assert.match(workbench, /plan <= 1200/);
  assert.match(control, /I approve up to <strong>\{48 \* selectedModels.length \* trialCount\} real provider requests<\/strong>/);
  assert.match(control, /Start investigation/);
  assert.doesNotMatch(workbench, /plan <= 45/);
});

test('Control Room shows meaningful incident names and live evidence', () => {
  assert.match(control, /Select agentic incident/);
  assert.match(control, /incidentLabel\(t\.id\)/);
  assert.match(control, /Live investigation/);
  assert.match(control, /role="log"/);
  assert.match(control, /Saved episodes/);
});
