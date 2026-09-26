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
assert.match(app, /currentPosition\(/);
assert.match(app, /targetAccuracy: settings.geofence_max_accuracy_meters/);

const config = await readFile(new URL('../src/OrganizerAttendanceConfig.tsx', import.meta.url), 'utf8');
const picker = await readFile(new URL('../src/MapboxVenuePicker.tsx', import.meta.url), 'utf8');
const ticket = await readFile(new URL('../src/TicketDetail.tsx', import.meta.url), 'utf8');
const operations = await readFile(new URL('../src/OrganizerAttendanceOperations.tsx', import.meta.url), 'utf8');
const api = await readFile(new URL('../src/api.ts', import.meta.url), 'utf8');
assert.match(config, /Allowed distance from venue/);
assert.match(config, /Maximum device accuracy for automatic verification/);
assert.match(config, /MapboxVenuePicker/);
assert.match(picker, /VITE_MAPBOX_ACCESS_TOKEN/);
assert.match(picker, /draggable: true/);
assert.match(picker, /instance\.on\('click'/);
assert.match(ticket, /My Space → Attendance/);
assert.match(ticket, /pending_review/);
assert.match(operations, /organizer-review/);
assert.match(operations, />Verify</);
assert.match(operations, />Reject</);
assert.match(api, /body\?\.error\?\.message/);

console.log('Location permission and fallback handling passed');
