import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = name => readFileSync(new URL(`../src/${name}`, import.meta.url), 'utf8');
const screens = ['AdminLeaderboards', 'AdminPointRules', 'AdminContributionBands', 'AdminNotificationRules', 'AdminAuditLogs', 'AdminImpactAdjustment', 'AdminAnalytics', 'OrganizerDashboard', 'OrganizerAttendanceOperations', 'OrganizerAttendanceReview', 'OrganizerAttendanceConfig', 'OrganizerMembers', 'OrganizerTaskQueue', 'OrganizerOpportunities'];

for (const screen of screens) {
  test(`${screen}: management overflow boundary and scoped styles`, () => {
    const source = read(`${screen}.tsx`);
    assert.match(source, /import '\.\/management\.css'/);
    assert.match(source, /className="[^"]*management-screen/);
    assert.doesNotMatch(source, /gridTemplateColumns: 'minmax\(0,1fr\) minmax\(0,320px\)'/);
    assert.doesNotMatch(source, /style=\{\{ width: '(16|18)rem' \}\}/);
  });
}

test('check-in uses the shared stacking aside contract', () => {
  assert.match(read('OrganizerAttendanceOperations.tsx'), /className="content-with-aside"/);
});

for (const [screen, labels] of [['OrganizerMembers', ['Member', 'Role', 'Status', 'Joined', 'Actions']], ['OrganizerAttendanceOperations', ['Participant', 'Ticket', 'Attendance', 'Verification']]]) {
  test(`${screen}: table retains labels and mobile card semantics`, () => {
    const source = read(`${screen}.tsx`);
    assert.match(source, /className="[^"]*management-table/);
    assert.match(source, /<caption/);
    for (const label of labels) assert.ok(source.includes(`data-label="${label}"`), `Missing ${label} cell label`);
  });
}

test('responsive management CSS stacks cards without clipping controls', () => {
  const css = read('management.css');
  assert.match(css, /min-width:\s*0/);
  assert.match(css, /overflow-wrap:\s*anywhere/);
  assert.match(css, /@media\s*\(max-width:\s*640px\)/);
  assert.match(css, /content:\s*attr\(data-label\)/);
  assert.match(css, /overflow-x:\s*auto/);
  assert.match(css, /minmax\(min\(100%,\s*12rem\),\s*1fr\)/);
});

test('scanner retains camera, hardware/manual and server validation paths', () => {
  const source = read('OrganizerAttendanceOperations.tsx');
  for (const marker of ['BarcodeDetector', 'getUserMedia', 'detector.detect(video)', 'acceptingScanRef', 'detectingRef', 'activeStream.getTracks()', 'window.clearInterval(timer)', 'qr_token: value', 'await validateToken(qr)', 'void validateToken(scanResult.rawValue)', 'await loadRoster()', 'hardware scanner', 'events/${eventId}/attendance/roster', 'events/${eventId}/tickets/validate']) assert.ok(source.includes(marker), marker);
});

test('attendance enabled methods remain separate from required methods', () => {
  const source = read('OrganizerAttendanceConfig.tsx');
  for (const marker of ['qr_attendance_enabled', 'geofence_enabled', 'organizer_verification_enabled', 'peer_confirmation_enabled', 'disabled={!enabled}', 'current.required_verification_methods.filter', 'toggleRequired(method)', 'JSON.stringify(config)']) assert.ok(source.includes(marker), marker);
  assert.doesNotMatch(source, /description="Require participants to be within/);
});

test('participant asides stack and wallet keeps a full-width mobile column', () => {
  for (const screen of ['Attendance', 'ProfileEditor', 'Opportunities']) {
    assert.match(read(`${screen}.tsx`), /className="content-with-aside"/);
    assert.doesNotMatch(read(`${screen}.tsx`), /gridTemplateColumns:.*(?:280|300|320)px/);
  }
  assert.match(read('management.css'), /max-width: 1024px.*content-with-aside.*minmax\(0, 1fr\)/);
  assert.match(read('management.css'), /ticket-wallet \{ grid-template-columns: minmax\(0, 1fr\)/);
});

test('recognition uses focused sections and exact condition contracts', () => {
  const source = read('AdminRecognition.tsx');
  for (const marker of ['section-tabs', 'editor &&', 'Advanced configuration', 'serializeRequirements(section, conditions)', 'validateRequirements(section, value)', 'nameRef.current?.focus()', "event.key === 'Escape'"]) assert.ok(source.includes(marker), marker);
  assert.doesNotMatch(source, /communities\/me/);
});

test('recognition serializer and advanced validation match backend contracts', async () => {
  const ts = await import('typescript');
  const { outputText } = ts.transpileModule(read('recognitionForm.ts'), { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } });
  const { serializeRequirements, validateRequirements } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
  const conditions = [{ metric: 'attendance_count', operator: '>=', threshold: 1 }];
  const leaf = { metric: 'attendance_count', operator: '>=', value: 1 };
  for (const section of ['achievement-rules', 'badges']) {
    assert.deepEqual(serializeRequirements(section, conditions), leaf);
    assert.deepEqual(serializeRequirements(section, [...conditions, ...conditions]), { operator: 'AND', conditions: [leaf, leaf] });
    assert.doesNotThrow(() => validateRequirements(section, leaf));
    assert.doesNotThrow(() => validateRequirements(section, { operator: 'OR', conditions: [leaf] }));
    assert.throws(() => validateRequirements(section, conditions[0]));
    assert.throws(() => validateRequirements(section, { ...leaf, metric: 'invented_metric' }));
  }
  assert.deepEqual(serializeRequirements('milestones', conditions), conditions);
  assert.deepEqual(serializeRequirements('ranks', conditions), [{ requirement_type: 'attendance_count', threshold: 1 }]);
  assert.doesNotThrow(() => validateRequirements('ranks', []));
  assert.throws(() => validateRequirements('milestones', []));
  assert.throws(() => validateRequirements('ranks', [{ requirement_type: 'badge', threshold: 1 }]));
  assert.throws(() => validateRequirements('milestones', [{ ...conditions[0], threshold: -1 }]));
});

test('workspace changes remount forms and attendance requires explicit scoped event', () => {
  assert.match(read('main.tsx'), /key=\{`\$\{workspace\}:\$\{selectedCommunityId\}`\}/);
  assert.doesNotMatch(read('main.tsx'), /eventId=\{events\[0\]/);
  assert.match(read('ManagedEventSelector.tsx'), /item.community_id === communityId/);
  assert.match(read('ManagedEventSelector.tsx'), /Select an event/);
});

test('media uses authenticated multipart and rejects browser-incompatible identities', () => {
  for (const marker of ['FormData', 'apiFetchAuth', "method: 'DELETE'"]) assert.ok(read('EventCoverEditor.tsx').includes(marker), marker);
  assert.match(read('EventCover.tsx'), /https\?/);
  assert.match(read('main.tsx'), /<EventCover/);
  assert.match(read('OrganizerEvents.tsx'), /<EventCoverEditor/);
});

test('sponsored slots are absent from critical journeys and empty without campaigns', () => {
  for (const screen of ['Attendance', 'OrganizerAttendanceOperations', 'PaymentReturn', 'PlatformAdmin']) assert.doesNotMatch(read(`${screen}.tsx`), /SponsoredPlacement/);
  for (const screen of ['HomeDashboard', 'Opportunities', 'main']) assert.match(read(`${screen}.tsx`), /SponsoredPlacement/);
  assert.match(read('SponsoredPlacement.tsx'), /return null/);
  assert.match(read('EventSupport.tsx'), /return null/);
});
