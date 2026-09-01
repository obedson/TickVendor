import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

const source = await readFile(new URL('../src/location.ts', import.meta.url), 'utf8');
const runnable = source
  .replace(/export type[^;]+;/g, '')
  .replace(/error: LocationError/g, 'error')
  .replace(/\): string/g, ')');
const moduleUrl = `data:text/javascript,${encodeURIComponent(runnable)}`;
const {locationErrorMessage} = await import(moduleUrl);

assert.match(locationErrorMessage({code: 1}), /permission.*denied/i);
assert.match(locationErrorMessage({code: 2}), /unavailable/i);
assert.match(locationErrorMessage({code: 3}), /timed out/i);
assert.match(locationErrorMessage({code: 99}), /could not be verified/i);

const app = await readFile(new URL('../src/main.tsx', import.meta.url), 'utf8');
assert.match(app, /Location is requested only for this attendance check/);
assert.match(app, /enableHighAccuracy:true/);
assert.match(app, /timeout:10000/);
assert.match(app, /locationErrorMessage/);

console.log('Location permission and fallback handling passed');
