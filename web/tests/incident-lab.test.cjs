const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const read = (p) => fs.readFileSync(path.join(__dirname, '..', p), 'utf8');
const lab = read('pages/IncidentLab.tsx');
const workbench = read('hooks/useWorkbench.tsx');
const shell = read('components/ResearchShell.tsx');
const css = read('app/globals.css');
const topology = read('components/Topology.tsx');

test('Incident Lab is a standalone screen, driven by frozen synthetic dataset', () => {
  assert.match(lab, /export function IncidentLab/);
  assert.match(workbench, /const activeLabTaskId = taskId \|\| labDataset/);
  assert.match(workbench, /task\?\.case\.id === activeLabTaskId \? task : null/);
  assert.match(lab, /aria-label="Explore incident dataset"/);
  assert.match(lab, /reviewer-only reference graph, not an observation revealed to an AI agent/);
  assert.match(lab, /key=\{activeLabTaskId\}/);
  assert.match(lab, /nodes=\{labTask\.case\.facts\.topology\}/);
});

test('Incident Lab visually separates real agent commitment from hypothetical repair', () => {
  assert.match(workbench, /trial\?\.record\?\.committed_effect as \{ action_id\?: string \}/);
  assert.match(workbench, /const actionId = labMode === 'actual' \? labCommittedAction/);
  assert.match(lab, /Actual agent execution/);
  assert.match(lab, /Try a repair in the sandbox/);
  assert.match(lab, /Hypothetical repair · not executed by the agent/);
  assert.match(lab, /Counterfactual preview only/);
  assert.match(lab, /Recorded model action: \$\{labCommittedAction\}/);
});

test('Independent reference and service graph remain inspectable without result files', () => {
  assert.match(lab, /labTask\.case\.facts/);
  assert.match(lab, /labTask\.reference\.root_cause/);
  assert.match(lab, /labTask\.reference\.fix_id/);
  assert.match(lab, /Select a dataset above to explore its service graph/);
  assert.match(lab, /onSelect=\{\(id\) => \{ setNodeId\(id\); setLabSideView\('service'\); \}\}/);
});

test('Fullscreen topology and reviewer inspector remain interactive', () => {
  assert.match(shell, /page === 'lab' \? 'shell--incident-lab' : ''/);
  assert.match(lab, /incident-lab-layout/);
  assert.match(lab, /aria-label="Incident inspector"/);
  assert.match(css, /\.shell--incident-lab\s*\{[\s\S]*?height: 100dvh;[\s\S]*?overflow: hidden;/);
  assert.match(css, /\.page--incident-lab \.incident-inspector-scroll\s*\{[\s\S]*?overflow: auto;/);
  assert.match(topology, /panOnScroll/);
  assert.match(topology, /zoomOnScroll=\{false\}/);
});
