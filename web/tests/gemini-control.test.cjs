const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const read = p => fs.readFileSync(path.join(__dirname, '..', p), 'utf8');

test('Google UI provider explicitly visible with quota and temperature caveats', () => {
  const control = read('pages/ControlRoom.tsx');
  assert.match(control, /google-ai-studio\//);
  assert.match(control, /quota|rate limits/i);
  assert.match(control, /temperature may be ignored/i);
  assert.match(control, /GOOGLE_API_KEY/);
});
test('Google activity monitoring recognizes Gemini provider requests', () => {
  assert.match(read('lib/live-activity.ts'), /provider\|Gemini/);
});
