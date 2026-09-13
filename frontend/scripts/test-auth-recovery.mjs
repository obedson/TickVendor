import assert from 'node:assert/strict';
import { webcrypto } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

const require = createRequire(import.meta.url);
const read = file => readFileSync(new URL(`../src/${file}`, import.meta.url), 'utf8');
function harness(file, hash = '') {
  const states = []; let cursor = 0; let requested; let redirected; let cleared = false;
  const storage = new Map();
  const exports = {};
  const react = { ...require('react'), useId: () => 'password-control', useEffect: () => {},
    useState(initial) { const index = cursor++; if (!(index in states)) states[index] = typeof initial === 'function' ? initial() : initial;
      return [states[index], next => { states[index] = typeof next === 'function' ? next(states[index]) : next; }]; } };
  let response = { ok: true, status: 202, json: async () => ({}) };
  const context = { exports, URLSearchParams, TextEncoder, Uint8Array, Date, AbortController, crypto: webcrypto,
    btoa: value => Buffer.from(value, 'binary').toString('base64'),
    sessionStorage: { setItem: (k, v) => storage.set(k, v), getItem: k => storage.get(k), removeItem: k => storage.delete(k) },
    window: { location: { hash, search: '', assign: url => { redirected = url; } }, history: { replaceState() {} }, setTimeout, clearTimeout },
    fetch: async (url, options) => { requested = { url, ...options }; return response; },
    require: id => id === 'react' ? react : id.endsWith('.css') ? {} : id === './api' ? { API_BASE: 'https://backend.example/api/v1', clearSession: () => { cleared = true; } }
      : id === './RevealFocus' ? { useRevealFocus() {} } : id === './PasswordInput' ? { PasswordInput: 'password-control' } : require(id) };
  vm.runInNewContext(ts.transpileModule(read(file), { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText, context);
  return { exports, storage, render: (name, props = {}) => { cursor = 0; return exports[name](props); },
    get requested() { return requested; }, get redirected() { return redirected; }, get cleared() { return cleared; }, setResponse: value => { response = value; } };
}
function find(tree, predicate) {
  if (!tree || typeof tree !== 'object') return null;
  if (Array.isArray(tree)) { for (const child of tree) { const result = find(child, predicate); if (result) return result; } return null; }
  return predicate(tree) ? tree : find(tree.props?.children, predicate);
}
const text = tree => typeof tree === 'string' ? tree : Array.isArray(tree) ? tree.map(text).join(' ') : tree?.props ? text(tree.props.children) : '';
const submit = tree => find(tree, e => e.type === 'form').props.onSubmit({ preventDefault() {} });

test('password is masked, toggles both ways without losing controlled value or autocomplete', () => {
  const h = harness('PasswordInput.tsx'); const props = { label: 'New password', value: 'unchanged-secret', autoComplete: 'new-password', required: true };
  let tree = h.render('PasswordInput', props);
  assert.equal(find(tree, e => e.type === 'input').props.type, 'password');
  assert.equal(find(tree, e => e.type === 'label').props.htmlFor, 'password-control');
  let toggle = find(tree, e => e.type === 'button');
  assert.equal(toggle.props.type, 'button'); assert.equal(toggle.props['aria-label'], 'Show new password');
  toggle.props.onClick(); tree = h.render('PasswordInput', props);
  const input = find(tree, e => e.type === 'input');
  assert.equal(input.props.type, 'text'); assert.equal(input.props.value, props.value); assert.equal(input.props.autoComplete, 'new-password'); assert.equal(input.props.required, true);
  toggle = find(tree, e => e.type === 'button'); assert.equal(toggle.props['aria-pressed'], true); assert.equal(toggle.props['aria-label'], 'Hide new password');
  toggle.props.onClick(); assert.equal(find(h.render('PasswordInput', props), e => e.type === 'input').props.type, 'password');
});

test('forgot flow sends only email and renders generic confirmation', async () => {
  const h = harness('AuthRecovery.tsx'); let tree = h.render('PasswordRecovery');
  find(tree, e => e.type === 'input').props.onChange({ target: { value: 'someone@example.com' } });
  await submit(h.render('PasswordRecovery')); tree = h.render('PasswordRecovery');
  assert.match(text(tree), /If an account exists/); assert.deepEqual(JSON.parse(h.requested.body), { email: 'someone@example.com' });
  assert.equal(h.storage.size, 0);
});

test('reset rejects mismatched confirmation locally then clears session after success', async () => {
  const h = harness('AuthRecovery.tsx', '#token=reset-proof');
  let tree = h.render('PasswordRecovery', { reset: true });
  find(tree, e => e.props?.label === 'New password').props.onChange({ target: { value: 'new-password-123' } });
  await submit(h.render('PasswordRecovery', { reset: true }));
  assert.match(text(h.render('PasswordRecovery', { reset: true })), /Passwords do not match/); assert.equal(h.requested, undefined);
  tree = h.render('PasswordRecovery', { reset: true });
  find(tree, e => e.props?.label === 'Confirm new password').props.onChange({ target: { value: 'new-password-123' } });
  h.setResponse({ ok: true, status: 204 });
  await submit(h.render('PasswordRecovery', { reset: true }));
  assert.equal(h.cleared, true); assert.match(text(h.render('PasswordRecovery', { reset: true })), /Password reset successfully/);
  assert.deepEqual(JSON.parse(h.requested.body), { token: 'reset-proof', new_password: 'new-password-123' }); assert.equal(h.storage.size, 0);
});

test('invalid/expired reset link offers recovery and missing token disables submit', async () => {
  const missing = harness('AuthRecovery.tsx'); const tree = missing.render('PasswordRecovery', { reset: true });
  assert.match(text(tree), /invalid or has expired/); assert.equal(find(tree, e => e.type === 'button').props.disabled, true);
  const h = harness('AuthRecovery.tsx', '#token=expired'); h.render('PasswordRecovery', { reset: true });
  h.setResponse({ ok: false, status: 400, json: async () => ({ detail: 'Invalid or expired reset token' }) });
  await submit(h.render('PasswordRecovery', { reset: true }));
  assert.match(text(h.render('PasswordRecovery', { reset: true })), /Invalid or expired reset token/);
});

test('Google start stores only ephemeral proof and redirects with its SHA-256 challenge', async () => {
  const h = harness('AuthRecovery.tsx'); await h.exports.googleStart();
  const proof = JSON.parse(h.storage.get('tickvendor.google-proof'));
  assert.deepEqual(Object.keys(proof).sort(), ['at', 'verifier']); assert.equal(proof.verifier.length, 43);
  const url = new URL(h.redirected); assert.equal(url.pathname, '/api/v1/auth/google/start');
  const expected = Buffer.from(await webcrypto.subtle.digest('SHA-256', new TextEncoder().encode(proof.verifier))).toString('base64url');
  assert.equal(url.searchParams.get('handoff_challenge'), expected); assert.ok(!h.redirected.includes(proof.verifier));
});

test('Google cancellation is safe and arbitrary provider error is not echoed', () => {
  assert.match(text(harness('AuthRecovery.tsx', '#error=cancelled').render('GoogleReturn')), /was cancelled/);
  assert.doesNotMatch(text(harness('AuthRecovery.tsx', '#error=private-provider-secret').render('GoogleReturn')), /private-provider-secret/);
});

test('Google existing-account proof and suspended response remain participant-safe', async () => {
  const h = harness('AuthRecovery.tsx', '#grant=opaque-grant'); h.storage.set('tickvendor.google-proof', JSON.stringify({ verifier: 'a'.repeat(64), at: Date.now() }));
  h.setResponse({ ok: false, status: 409, json: async () => ({ detail: 'Confirm your existing TickVendor password to link Google.' }) });
  await submit(h.render('GoogleReturn')); let tree = h.render('GoogleReturn');
  assert.ok(find(tree, e => e.props?.autoComplete === 'current-password'));
  h.setResponse({ ok: false, status: 403, json: async () => ({ detail: 'Your account is suspended. Contact platform support for assistance.' }) });
  await submit(tree); tree = h.render('GoogleReturn'); assert.match(text(tree), /account is suspended/);
  assert.equal(h.storage.size, 1); assert.ok(![...h.storage.values()][0].includes('password'));
});

test('Sign In/Register use shared controls and recovery routes precede session gate', () => {
  const source = read('main.tsx');
  assert.match(source, /href="\/forgot-password"/); assert.match(source, /<GoogleButton/); assert.match(source, /<PasswordInput/);
  assert.doesNotMatch(source, /type="password"/);
  const route = source.indexOf("if (location.pathname === '/reset-password') return <PasswordRecovery reset />;");
  assert.ok(route > 0 && route < source.indexOf('if (!session) {'));
  assert.doesNotMatch(read('AuthRecovery.tsx'), /GOOGLE_CLIENT_SECRET|localStorage\.setItem|console\.log/);
});
