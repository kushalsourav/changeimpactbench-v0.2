const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const component = fs.readFileSync(path.join(__dirname, '../components/ResearchSynthesis.tsx'),'utf8');
const overview = fs.readFileSync(path.join(__dirname, '../pages/Overview.tsx'),'utf8');

test('Research Lab renders verifier-owned per-episode strict, recovery, partial and cost metrics',()=>{
  assert.match(component,/data\.verified_facts/);
  assert.match(component,/Independent deterministic facts/);
  assert.match(component,/x\.strict_pass/);
  assert.match(component,/episode\.recovery_success/);
  assert.match(component,/x\.partial_score/);
  assert.match(component,/x\.reference_optimal_cost/);
  assert.match(component,/x\.repair_cost_delta/);
  assert.match(component,/x\.strict_failure_reasons/);
});
test('Frontend never derives verdict or repair from model name',()=>{
  assert.doesNotMatch(component,/model.*===.*flint|model.*===.*gemini.*PASS|Math\.random/);
  assert.match(component,/x\.gradeable\?verification\(x\.strict_pass\)/);
  assert.match(overview,/selected\.pass == null \? 'NOT GRADED'/);
});
test('Legacy or inconsistent Gemini prose is explicitly flagged and separate from verified facts',()=>{
  assert.match(component,/blocked_inconsistent/);
  assert.match(component,/consistency check failed/);
  assert.match(component,/The deterministic table above is authoritative/);
  assert.match(component,/chart\.rows\.map/);
});
