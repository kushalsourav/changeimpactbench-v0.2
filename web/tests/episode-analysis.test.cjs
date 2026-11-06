/** Offline deterministic analysis-layer tests; no provider requests. */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const source = fs.readFileSync(path.join(__dirname, '../lib/episode-analysis.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } });
const testExports = {};
vm.runInNewContext(compiled.outputText, { exports: testExports, Object, Array, Number, String }, { filename: 'episode-analysis.js' });
const { explainEpisode } = testExports;
const basic = {status:'completed',pass:false,root_correct:true,fix_correct:true,affected_f1:0.92857};
const trial = {
  audit:{grade:{strict_pass:false,root_correct:true,fix_correct:true,affected_f1:.92857,recovery_safe:true,recovery_success:true}},
  diagnosis:{expected:{failed_services:['audit-west','api-west'],root_cause:'H04',fix_id:'A03'},
    predicted:{failed_services:['front-door','api-west'],root_cause:'H04',fix_id:'A03'},
    missed_services:['audit-west'],extra_services:['front-door']},
  record:{final_diagnosis:{evidence_ids:['EV003']},trajectory:[
    {tool:'simulate_repair',arguments:{action_id:'A02'},provider_turn:1,observation:{event_id:'EV001',result:{restored_count:1,unavailable_after_count:1,newly_unavailable_count:0,cost:2}}},
    {tool:'apply_repair',arguments:{action_id:'A03'},provider_turn:2,observation:{event_id:'EV002',result:{restored_count:2,unavailable_after_count:0,newly_unavailable_count:0}}},
    {tool:'inspect_config',arguments:{service:'gateway-north'},provider_turn:3,observation:{event_id:'EV003',result:{configured_local_check:true}}},
  ],committed_effect:{restored:['audit-west','api-west'],unavailable_after:[],newly_unavailable:[]}},
};
test('complete recovery and wrong initial set are distinct, with traceable evidence',()=>{
  const v=explainEpisode(basic,trial);
  assert.equal(v.title,'Complete recovery, incomplete impact diagnosis');
  assert.equal(v.restored,2);assert.equal(v.remaining,0);assert.equal(v.newOutages,0);
  assert.deepEqual([...v.missing],['audit-west']);assert.deepEqual([...v.extra],['front-door']);
  assert.deepEqual([...v.postCommitCitations],['EV003']);
  assert.equal(v.steps[0].action,'A02');assert.equal(v.steps[1].action,'A03');
});
test('a safe but incomplete committed repair is not labelled unsafe',()=>{
  const partial=structuredClone(trial);
  partial.audit.grade={strict_pass:false,root_correct:false,recovery_safe:true,recovery_success:false};
  partial.record.trajectory[1].observation.result={restored_count:1,unavailable_after_count:1,newly_unavailable_count:0};
  const v=explainEpisode({...basic,root_correct:false},partial);
  assert.equal(v.title,'Safe but incomplete recovery');assert.equal(v.remaining,1);
});
test('provider error is never reported as a reasoning fail',()=>{
  const v=explainEpisode({...basic,status:'api_error',pass:null},trial);
  assert.equal(v.title,'No complete, gradeable episode');assert.equal(v.strictlyPassed,null);
});
test('false numerical rationale claim is flagged without altering official score',()=>{
  const example=structuredClone(trial);
  example.record.final_diagnosis.rationale='issuer_epoch=8 > trusted_through_epoch=8';
  const v=explainEpisode(basic,example);
  assert.equal(v.semanticWarnings.length,1);
  assert.match(v.semanticWarnings[0],/false numeric claim/);
  assert.equal(v.strictlyPassed,false);
});
