import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = file => readFileSync(new URL(`../src/${file}`, import.meta.url), 'utf8');
test('community lifecycle exposes join/request/invitation/withdraw/leave without admin escalation', () => {
  const source = read('CommunityLifecycle.tsx');
  for (const text of ['Join Community', 'Request to Join', 'Accept invitation', 'Decline invitation', 'Withdraw request', 'Leave Community', 'Invitations', 'Pending Requests', 'Past Memberships', 'tickvendor-memberships-changed']) assert.ok(source.includes(text), text);
  assert.doesNotMatch(source, /role: ['"]admin['"]/);
  assert.match(source, /membership_access === 'open'/);
  assert.match(source, /membership\/\$\{action\}/);
});
test('ordinary member management never offers Admin role or admin-row mutations', () => {
  const source = read('OrganizerMembers.tsx');
  assert.doesNotMatch(source, /<option value="admin"/);
  assert.match(source, /member.role !== 'admin'/);
  assert.match(source, /member.user_id !== viewerId/);
  for (const text of ['Approve request', 'Reject request', 'GovernanceConfirm', 'reason', 'suspended', 'CommunityAccessEditor']) assert.ok(source.includes(text), text);
  assert.doesNotMatch(source, /updateStatus\(member, 'inactive'\)/);
});
test('platform workflow includes inspection, administrator assignment and moderation with reasons', () => {
  const source = read('PlatformGovernance.tsx');
  for (const text of ['Assign Community Admin', 'Content Moderation', 'Moderation History', 'Super Admin access required', 'role_changed', 'administrators', 'moderation', 'reason', 'GovernanceConfirm', 'Find creator', 'Created after', 'Created before']) assert.ok(source.includes(text), text);
  assert.match(source, /userRole !== 'super_admin'/);
  assert.match(source, /view|section/);
  assert.doesNotMatch(source, /window.confirm|alert\(/);
});
test('community creation separates reviewed applications from organization-scoped expansion', () => {
  const lifecycle = read('CommunityLifecycle.tsx');
  const creation = read('CreateCommunity.tsx');
  const platform = read('PlatformGovernance.tsx');
  for (const text of ['Create or apply for community', 'Save server draft', 'Submit for Platform review', 'pending_review', 'organization_id', 'Platform review']) assert.ok(`${lifecycle}${creation}`.includes(text), text);
  for (const text of ['Review application', 'Approve application', 'Reject application', 'initial_admin_user_id', 'verified initial Community Admin']) assert.ok(platform.includes(text), text);
  assert.match(platform, /lifecycle_status === 'pending_review'/);
});
test('confirmation uses native modal focus, Escape, reason validation and restoration', () => {
  const source = read('GovernanceConfirm.tsx');
  for (const text of ['showModal()', 'previous?.focus()', 'onCancel', 'aria-labelledby', 'minLength={3}', 'reason.trim().length < 3', 'onConfirm']) assert.ok(source.includes(text), text);
  assert.match(read('management.css'), /governance-dialog.*max-height: calc\(100dvh/);
});
test('archives are server-backed, typed and separated from QR/domain state', () => {
  const source = read('PersonalHistory.tsx');
  for (const text of ['me/archive', 'me/personal-items', 'Restore to My Space', 'Archive changes only your personal view', 'item_type', 'History', 'Archived', 'My Registrations']) assert.ok(source.includes(text), text);
  assert.match(read('main.tsx'), /archiveItem\(token, 'ticket'/);
  assert.match(read('main.tsx'), /<TicketQr ticket=\{ticket\}/);
  assert.match(read('Tasks.tsx'), /archive.ids.has\(assignment.id\)/);
  assert.match(read('Notifications.tsx'), /!archive.ids.has\(item.id\)/);
  assert.match(read('Opportunities.tsx'), /kind="opportunity"/);
  assert.doesNotMatch(source, /method: 'DELETE'.*(payments|attendance|tickets)/);
});
test('access policy and public discoverability are independent controls', () => {
  const source = read('CommunityAccessEditor.tsx');
  for (const text of ['value="open"', 'value="approval_required"', 'value="invite_only"', 'Publicly discoverable', 'membership_access: access', 'is_public: visible']) assert.ok(source.includes(text), text);
});
