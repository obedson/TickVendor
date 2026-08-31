import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';

const source = await readFile(new URL('../public/sw.js', import.meta.url), 'utf8');
const listeners = new Map();
const deleted = [];
const stored = [];
const cachedResponses = new Map();

const caches = {
  async open() {
    return {
      async addAll() {},
      async put(request) { stored.push(new URL(request.url).pathname); },
    };
  },
  async keys() { return ['tickeven-shell-v1', 'other-application-cache']; },
  async delete(key) { deleted.push(key); },
  async match(request) { return cachedResponses.get(typeof request === 'string' ? request : request.url); },
};
const self = {
  location: {origin: 'https://tickeven.test'},
  clients: {async claim() {}},
  skipWaiting() {},
  addEventListener(type, handler) { listeners.set(type, handler); },
};
const response = {ok: true, clone() { return this; }};
const context = {self, caches, URL, Promise, fetch: async () => response};
vm.runInNewContext(source, context);

async function dispatch(type, request) {
  let pending;
  listeners.get(type)({
    request,
    respondWith(value) { pending = value; },
    waitUntil(value) { pending = value; },
  });
  return pending;
}

await dispatch('activate');
assert.deepEqual(deleted, ['tickeven-shell-v1'], 'activation must preserve caches owned by other applications');

await dispatch('fetch', {method: 'GET', url: 'https://tickeven.test/api/v1/events?search=tech'});
await new Promise(resolve => setTimeout(resolve, 0));
assert.deepEqual(stored, ['/api/v1/events'], 'public event data should be cached');

await dispatch('fetch', {method: 'GET', url: 'https://tickeven.test/api/v1/tickets/me'});
await new Promise(resolve => setTimeout(resolve, 0));
assert.deepEqual(stored, ['/api/v1/events'], 'private ticket data must not be cached by the shared service-worker cache');

console.log('service-worker cache policy passed');
