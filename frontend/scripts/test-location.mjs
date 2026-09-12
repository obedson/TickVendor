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

const app = await readFile(new URL('../src/Attendance.tsx', import.meta.url), 'utf8');
assert.match(app, /Location is requested only for GPS-verified events/);
assert.match(app, /enableHighAccuracy:\s*true/);
assert.match(app, /timeout:\s*8000/);
assert.match(app, /locationErrorMessage/);

console.log('Location permission and fallback handling passed');
