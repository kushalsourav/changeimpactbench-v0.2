const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const root = join(__dirname, '..');
const source = (name) => readFileSync(join(root, name), 'utf8');

test('frontend exposes only V6 counterfactual task IDs', () => {
  const text = source('lib/presentation.tsx');
  const ids = [...text.matchAll(/RW\d{2}V6CF/g)].map(x=>x[0]);
  assert.equal(new Set(ids).size, 6);
  assert.ok(!/RW\d{2}V(?:4|5|6N)/.test(text));
  assert.match(text, /Cloudflare/);
  assert.match(text, /GitHub/);
});

test('Control Room uses backend current dataset catalogue and original names', () => {
  const text = source('pages/ControlRoom.tsx');
  assert.match(text, /tasks\.map\(/);
  assert.match(text, /original_source_name/);
  assert.ok(!/preserved V5|preserved V4|V6 neutral/.test(text));
});

test('Incident Lab and overview use catalog data, not old task lists', () => {
  assert.match(source('pages/IncidentLab.tsx'), /tasks\.map/);
  assert.match(source('pages/Overview.tsx'), /comparisonTask/);
  assert.doesNotMatch(source('pages/Overview.tsx'), /api\/archive\/runs/);
});
