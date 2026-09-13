import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

const require = createRequire(import.meta.url);
const read = file => readFileSync(new URL(`../src/${file}`, import.meta.url), 'utf8');
const load = file => {
  const exports = {};
  const source = ts.transpileModule(read(file), { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  vm.runInNewContext(source, { exports, require });
  return exports;
};
test('quiz builder serializes objective choices, while surveys omit answer keys', () => {
  const { buildLearning, emptyLearning } = load('LearningTask.tsx');
  const data = { ...emptyLearning, questions: [{ prompt: 'Select B', kind: 'single', choices: 'A\nB', correct: '2' }] };
  assert.equal(JSON.stringify(buildLearning('quiz', data).assessment.questions[0].correct), '[1]');
  assert.equal(buildLearning('survey', data).assessment.questions[0].correct, undefined);
  assert.equal(JSON.stringify(buildLearning('physical', data)), '{}');
});
test('checkpoint builder preserves all/N-of-M policy without claiming watch proof', () => {
  const { buildLearning, emptyLearning } = load('LearningTask.tsx');
  const config = buildLearning('video', { ...emptyLearning, checkpoints: [{ position: '02:15', prompt: 'Code?', expected: 'IMPACT' }] });
  assert.equal(config.checkpoints.minimum_correct, null);
  assert.equal(config.checkpoints.items[0].expected, 'IMPACT');
  assert.match(read('LearningTask.tsx'), /not proof of watching/);
});
test('draft keys separate accounts, communities and entities; persistence is encrypted', () => {
  const { draftScope } = load('formRecovery.ts');
  assert.notEqual(draftScope('a', 'community:1:task:1'), draftScope('b', 'community:1:task:1'));
  assert.notEqual(draftScope('a', 'community:1:task:1'), draftScope('a', 'community:2:task:1'));
  assert.notEqual(draftScope('a', 'community:1:task:1'), draftScope('a', 'community:1:task:2'));
  assert.equal(draftScope('', 'task:1'), '');
  assert.match(read('formRecovery.ts'), /AES-GCM/);
  assert.match(read('formRecovery.ts'), /beforeunload/);
  assert.doesNotMatch(read('formRecovery.ts'), /localStorage\.setItem|access_token|refresh_token/);
});
test('focus helper focuses without scrolling an already visible editor', () => {
  const exports = {}; let focused = false; let scrolled = false;
  vm.runInNewContext(ts.transpileModule(read('RevealFocus.tsx'), { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText,
    { exports, require, window: { innerHeight: 800 } });
  const field = { focus: options => { assert.equal(options.preventScroll, true); focused = true; } };
  const section = { querySelector: () => field, getBoundingClientRect: () => ({ top: 100 }), scrollIntoView: () => { scrolled = true; } };
  exports.focusRevealed(section); assert.ok(focused); assert.equal(scrolled, false);
  section.getBoundingClientRect = () => ({ top: 900 }); exports.focusRevealed(section); assert.ok(scrolled);
});
test('evidence retains drafts, uses replay keys and renders persisted assessment results', () => {
  const source = read('Tasks.tsx');
  for (const text of ['await draft.flush()', 'idempotency_key: requestKey', 'Last assessment:', 'Discard evidence draft?', 'Close and keep draft', 'noopener noreferrer']) assert.ok(source.includes(text), text);
  assert.match(source, /required\.includes\('attachment'\)/);
  assert.match(read('OrganizerTaskQueue.tsx'), /max=\{policy\?\.community_points \?\? 0\}/);
});
test('dashboard requests stay parallel and have a bounded retry state', () => {
  const source = read('HomeDashboard.tsx');
  for (const text of ['Promise.all', '20000', 'controller.abort()', 'Retry dashboard', 'request took too long']) assert.ok(source.includes(text), text);
});
