const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const read = p => fs.readFileSync(path.join(__dirname, '..', p), 'utf8');
const runTS = p => {
  const exports = {};
  const js = ts.transpileModule(read(p), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  vm.runInNewContext(js, { exports, require: () => ({}), Object, Array, Number, String, Date, JSON, Math }, { filename:p });
  return exports;
};

test('human-first names are centralized and retain frozen IDs', () => {
  const { incidentLabel, runLabel, benchmarkLabel } = runTS('lib/presentation.tsx');
  assert.equal(incidentLabel('RW01V3'), 'GitHub 2018 · MySQL failover (RW01V3)');
  assert.equal(incidentLabel('RW03V3'), 'Cloudflare 2019 · WAF regex outage (RW03V3)');
  assert.match(benchmarkLabel('publicincident-rw01-v1-langgraph-v1'), /LangGraph v1/);
  const label = runLabel({name:'ui_secretfilename.jsonl',updated_utc:'2026-11-06T06:30:00Z',tasks:['RW01V3'],models:['nvidia/nemotron-3-ultra:free'],records:1});
  assert.match(label, /GitHub 2018/);
  assert.match(label, /Nemotron/);
  assert.doesNotMatch(label, /ui_secretfilename|\.jsonl/);
});

test('activity parsing shows only observed tool events and preserves warnings', () => {
  const { parseLiveActivity } = runTS('lib/live-activity.ts');
  const log = `turn=1/48 · provider request ...\n    EV001 scan_service_health → {"statuses":{"a":"unavailable","b":"healthy"}}\nturn=2/48 · provider request ...\n    EV002 simulate_repair → {"action_id":"A03","restored_count":1,"unavailable_after_count":0,"newly_unavailable_count":0}\nturn=3/48 · provider failed (HTTPError)`;
  const parsed = parseLiveActivity(log);
  assert.equal(parsed.length, 3);
  assert.match(parsed[0].detail,/1 unavailable \/ 2 checked/);
  assert.match(parsed[1].detail,/1 restored · 0 remain · 0 newly unavailable/);
  assert.equal(parsed[2].kind,'problem');
});

test('truncated live logs never invent repair outcomes', () => {
  const { summarizeTool } = runTS('lib/live-activity.ts');
  assert.match(summarizeTool('simulate_repair', '{"action_id":"A03"'), /Observation recorded/);
});

test('trace evidence summaries distinguish counterfactual and actual commitment', () => {
  const { observedEventSummary } = runTS('lib/trace-summary.ts');
  const event = tool => ({tool,arguments:{action_id:'A03'},observation:{result:{restored_count:14,unavailable_after_count:0,newly_unavailable_count:0}}});
  assert.match(observedEventSummary(event('simulate_repair')), /Counterfactual only/);
  assert.match(observedEventSummary(event('apply_repair')), /Committed to synthetic sandbox/);
});

test('Control Room shows only incident, model, approval and collapses advanced settings', () => {
  const control = read('pages/ControlRoom.tsx');
  assert.match(control, /Compare incident responders/);
  assert.match(control, /incident\.alert/);
  assert.match(control, /<details className="agent-settings">/);
  assert.match(control, /parseLiveActivity\(job\.log/);
  assert.doesNotMatch(control, /04 · Observable agent execution/);
});

test('Evidence trace has human summaries and original observations available', () => {
  const analysis = read('pages/ExecutionAnalysis.tsx');
  assert.match(analysis, /observedEventSummary\(step\.event\)/);
  assert.match(analysis, /Model's actual tool request/);
  assert.match(analysis, /Sandbox observation/);
  assert.match(analysis, /trace-submission-verdict/);
  assert.match(analysis, /Sandbox safety violation recorded/);
});

test('Research methodology is not ahead of the featured case and comparison requires >=2 completed', () => {
  const overview = read('pages/Overview.tsx');
  assert.ok(overview.indexOf('OBSERVED EPISODE') < 0 || overview.indexOf('OBSERVED EPISODE') < overview.indexOf('research-methodology'));
  assert.ok(overview.indexOf('RECORDED EPISODE') < overview.indexOf('research-methodology'));
  assert.match(overview, /crossRun && crossRunCompleted >= 2/);
});
