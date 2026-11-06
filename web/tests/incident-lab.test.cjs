const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const page = fs.readFileSync(path.join(__dirname, '../app/page.tsx'), 'utf8');
const css = fs.readFileSync(path.join(__dirname, '../app/globals.css'), 'utf8');
const topology = fs.readFileSync(path.join(__dirname, '../components/Topology.tsx'), 'utf8');
const lab = page.slice(page.indexOf("{page === 'lab' && ("), page.indexOf("{page === 'analysis' && ("));

test('Incident Lab only follows header experiment and active saved trial', () => {
  assert.match(page, /const taskId = info\?\.run === run \? info\.rows\[recordIndex\]\?\.task \|\| '' : ''/);
  assert.match(page, /task\?\.case\.id === activeLabTaskId \? task : null/);
  assert.doesNotMatch(page, /setTaskId/);
  assert.match(lab, /key=\{activeLabTaskId\}/);
  assert.match(lab, /nodes=\{labTask\.case\.facts\.topology\}/);
  assert.match(lab, /info \|\| !activeLabTaskId/);
  assert.match(page, /setLabSideView\('service'\);\s*\}, \[run, recordIndex\]\);/);
});

test('No task catalog, redundant incident banner or duplicate report heading', () => {
  assert.doesNotMatch(lab, /title="Benchmark tasks"|incident-lab-provenance|Formal failure rules/);
  assert.doesNotMatch(lab, /labRecordIndex|labTrial|labTab/);
  assert.match(page, /\{page !== 'lab' && page !== 'overview' && \(\s*<div className="page-heading"/);
  assert.match(page, /ChangeImpactBench \/ \{NAV\.find\(\(item\) => item\.id === page\)\?\.label\}/);
  assert.match(lab, /rows\.length > 1/);
  assert.match(lab, /setRecordIndex\(Number\(e\.target\.value\)\)/);
});

test('Graph-first layout keeps interactive repair preview and node selection', () => {
  assert.match(lab, /className="incident-lab-layout"/);
  assert.match(lab, /aria-label="Displayed repair: agent commitment or manual counterfactual"/);
  assert.match(lab, /onSelect=\{\(id\) => \{ setNodeId\(id\); setLabSideView\('service'\); \}\}/);
  assert.match(lab, /aria-label="Incident inspector"/);
  assert.match(lab, />\s*Reviewer view\s*</);
  assert.match(lab, /labSideView === 'reviewer'/);
  assert.match(lab, /role="tabpanel"/);
  assert.match(lab, /<Code value=\{labTask\.prompt\}/);
  assert.match(lab, /<Json value=\{labTask\.case\.facts\}/);
});

test('Incident Lab fills the screen and isolates scrolling to graph and reviewer', () => {
  assert.match(page, /page === 'lab' \? 'shell--incident-lab' : ''/);
  assert.match(page, /page === 'lab' \? 'page--incident-lab' : ''/);
  assert.match(css, /\.shell--incident-lab\s*\{[\s\S]*?height: 100dvh;[\s\S]*?overflow: hidden;/);
  assert.match(css, /\.shell--incident-lab \.page--incident-lab\s*\{[\s\S]*?overflow: hidden;/);
  assert.match(css, /\.page--incident-lab \.incident-lab-layout \.topology-shell\s*\{[\s\S]*?flex: 1 1 auto;[\s\S]*?min-height: 0;/);
  assert.match(css, /\.page--incident-lab \.incident-inspector-scroll\s*\{[\s\S]*?overflow: auto;/);
  assert.match(topology, /panOnScroll/);
  assert.match(topology, /zoomOnScroll=\{false\}/);
  assert.match(topology, /onNodeClick=\{\(_, node\) => onSelect\?\.\(node\.id\)\}/);
});

test('Four tabs and all trace / reproducibility functionality remain', () => {
  assert.match(page, /id: 'overview'/);
  assert.match(page, /id: 'lab'/);
  assert.match(page, /id: 'control'/);
  assert.match(page, /id: 'analysis'/);
  assert.match(page, /values=\{\['Explanation','Full timeline','Verification'\]\}/);
  assert.match(page, /\/bundle\.zip/);
});
test('Incident Lab defaults after-state to recorded agent commit, clearly labels alternative previews',()=>{
  assert.match(page,/trial\?\.record\?\.committed_effect as \{ action_id\?: string \}/);
  assert.match(page,/const actionId = labMode === 'actual' \? labCommittedAction/);
  assert.match(lab,/Recorded model action: \$\{labCommittedAction\}/);
  assert.match(lab,/Actual agent execution/);
  assert.match(lab,/Counterfactual preview only/);
  assert.doesNotMatch(lab,/Preview an oracle repair/);
});
