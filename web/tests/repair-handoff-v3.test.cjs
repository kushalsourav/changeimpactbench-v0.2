const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const source=p=>fs.readFileSync(path.join(__dirname,'..',p),'utf8');
test('active scenario selector and typed shared state use v3 only',()=>{
  assert.match(source('lib/presentation.tsx'),/RW01V3', 'RW02V3', 'RW03V3'/);
  assert.match(source('hooks/useWorkbench.tsx'),/useState\(\['RW01V6N'\]\)/);
});
test('episode shows recorded agent-written repair brief and prompt hash',()=>{
  const page=source('pages/ExecutionAnalysis.tsx');
  assert.match(page,/Investigation → repair · the agent's own plan/);
  assert.match(page,/repair_brief/);
  assert.match(page,/repair_system_prompt_sha256/);
  assert.match(page,/repair_system_prompt/);
  assert.match(page,/error_traceback_redacted/);
});
test('tool trace treats handoff as observed action and rejected attempts as actual evidence',()=>{
  assert.match(source('lib/trace-summary.ts'),/prepare_repair/);
  assert.match(source('lib/trace-summary.ts'),/simulations_remaining/);
  const history=source('lib/presentation.tsx');
  assert.match(history,/record\.tool_attempts/);
  assert.match(history,/rejected_reason/);
});
