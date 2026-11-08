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
  assert.match(source, /completedKeys\.has/);
  assert.match(source, /nextTrialHasStarted/);
});
