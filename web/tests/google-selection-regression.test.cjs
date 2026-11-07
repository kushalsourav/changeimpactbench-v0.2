const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const control = fs.readFileSync(path.join(__dirname, '../pages/ControlRoom.tsx'), 'utf8');
const hook = fs.readFileSync(path.join(__dirname, '../hooks/useWorkbench.tsx'), 'utf8');

test('Control Room restricts selections to OpenRouter; legacy Google backend remains compatible', () => {
  assert.match(control, /selectedModels\.length < 5/);
  assert.match(control, /setSelectedModels\(\[\.\.\.selectedModels, modelId\]\)/);
  assert.match(control, /selectedModels\.length >= 5/);
  assert.match(control, /Select up to five OpenRouter models/);
  assert.doesNotMatch(control, /setSelectedModels\(\[modelId\]\)/);
  assert.match(control, /models\.filter\(m => !m\.id\.startsWith\('google-ai-studio\/'\)\)/);
  assert.match(hook, /!selectedModels\.some\(x => x\.startsWith\('google-ai-studio\/'\)\)/);
  assert.match(hook, /!selectedModels\.some\(x => !x\.startsWith\('google-ai-studio\/'\)\)/);
});
test('start button explains missing key or approval, and refresh reloads backend health', () => {
  assert.match(control, /launchBlocker && <p role="alert"/);
  assert.match(control, /Google API key is not loaded by FastAPI/);
  assert.match(control, /Tick the provider-request approval checkbox/);
  assert.match(hook, /const \[catalog, freshHealth\] = await Promise\.all/);
  assert.match(hook, /setHealth\(freshHealth\)/);
});
