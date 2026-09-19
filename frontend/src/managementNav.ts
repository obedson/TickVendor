/**
 * Role-aware management navigation.
 *
 * Organizers operate programs; Admins govern the community. Both enter the management workspace,
 * so the navigation must be derived from the *selected community membership role* — never from the
 * platform role — otherwise an Organizer is offered governance pages the backend answers with 403.
 *
 * This is presentation only. Backend authorization stays authoritative: the split exists so the UI
 * stops advertising actions the caller cannot take, not to enforce anything.
 */

/**
 * The shape the catalogue below is checked against.
 *
 * It spells its own fields out instead of reusing :type:`NavItem`, because `NavItem.id` is
 * :type:`ManagementViewId` and that union is derived *from* the catalogue — a `satisfies` clause
 * naming it would be checking the list against itself.
 */
type NavCatalogueEntry = {
  id: string;
  label: string;
  icon: string;
  minimumRole: 'organizer' | 'admin';
};

/**
 * Every management destination, with the lowest community membership role the backend accepts for
 * it. Keep this list in step with authorization.py — a page listed too low here is a page that
 * returns 403 after the user clicks it.
 *
 * `organizer-members` is intentionally `organizer`: the page itself is operational, but an
 * Organizer's view of it is the constrained single-member lookup, not the Admin directory.
 * `organizer-opportunities` is Admin-only because opportunity create/verify/registration endpoints
 * all require a community Admin.
 *
 * `as const` is what makes this list the source of truth for destination *names*: every `id` stays
 * a string literal, and :type:`ManagementViewId` is read straight off them.
 */
export const managementNavItems = [
  { id: 'organizer-dashboard', label: 'Dashboard', icon: '⌂', minimumRole: 'organizer' },
  { id: 'organizer-events', label: 'Events', icon: '◈', minimumRole: 'organizer' },
  { id: 'organizer-opportunities', label: 'Opportunities', icon: '◇', minimumRole: 'admin' },
  { id: 'organizer-tasks', label: 'Tasks', icon: '✓', minimumRole: 'organizer' },
  { id: 'organizer-members', label: 'Members', icon: '♧', minimumRole: 'organizer' },
  { id: 'organizer-review', label: 'Attendance review', icon: '◎', minimumRole: 'organizer' },
  { id: 'organizer-attendance', label: 'Check-in', icon: '▣', minimumRole: 'organizer' },
  { id: 'organizer-redemption', label: 'Benefit validation', icon: '▦', minimumRole: 'organizer' },
  { id: 'admin-rules', label: 'Point rules', icon: '◆', minimumRole: 'admin' },
  { id: 'admin-bands', label: 'Contribution Tiers', icon: '◫', minimumRole: 'admin' },
  { id: 'admin-leaderboards', label: 'Leaderboard', icon: '▥', minimumRole: 'admin' },
  { id: 'admin-adjustments', label: 'Adjustments', icon: '±', minimumRole: 'admin' },
  { id: 'admin-recognition', label: 'Recognition', icon: '★', minimumRole: 'admin' },
  { id: 'admin-notifications', label: 'Notifications', icon: '◌', minimumRole: 'admin' },
  { id: 'admin-analytics', label: 'Analytics', icon: '▤', minimumRole: 'admin' },
  { id: 'admin-audit', label: 'Audit log', icon: '≡', minimumRole: 'admin' },
] as const satisfies readonly NavCatalogueEntry[];

/**
 * Every destination name the management workspace can be on — the view-id union the shell accepts.
 *
 * Read off the catalogue, so a destination is in this union the moment it is in the list, and one
 * that is dropped from the list stops being assignable to the shell's `view` state. `platform-admin`
 * is the single name with no catalogue entry of its own: it belongs to the platform workspace and is
 * added to the nav for a Super Admin only.
 */
export type ManagementViewId = (typeof managementNavItems)[number]['id'] | 'platform-admin';

export type NavItem = { id: ManagementViewId; label: string; icon: string };
export type ManagementNavItem = NavItem & { minimumRole: 'organizer' | 'admin' };
export type CommunityRole = 'member' | 'organizer' | 'admin';

const ROLE_RANK: Record<CommunityRole, number> = { member: 1, organizer: 2, admin: 3 };

/** Identifiers an Organizer must never be offered in the management workspace. */
export const adminOnlyNavIds: ManagementViewId[] = managementNavItems
  .filter(item => item.minimumRole === 'admin')
  .map(item => item.id);

/** Identifiers an Organizer is still entitled to, in the order the sidebar shows them. */
export const organizerNavIds: ManagementViewId[] = managementNavItems
  .filter(item => item.minimumRole === 'organizer')
  .map(item => item.id);

/**
 * The management navigation for one community.
 *
 * `role` is the membership role in the community currently selected in the workspace selector. A
 * Super Admin who holds an Organizer membership in that community gets the Organizer view there:
 * platform authority belongs to the platform workspace, not to a community's pages.
 */
export function managementNav(role: CommunityRole | undefined, isSuperAdmin: boolean): NavItem[] {
  const rank = ROLE_RANK[role ?? 'member'] ?? ROLE_RANK.member;
  const items: NavItem[] = managementNavItems
    .filter(item => rank >= ROLE_RANK[item.minimumRole])
    .map(({ id, label, icon }) => ({ id, label, icon }));
  // Super Admin only — platform-wide administration, not community governance.
  const platformItems: NavItem[] = isSuperAdmin
    ? [{ id: 'platform-admin', label: 'Platform Admin', icon: '⚙' }]
    : [];
  return [...items, ...platformItems];
}

/** True when the selected community's membership grants community governance authority. */
export function isCommunityAdmin(role: CommunityRole | undefined): boolean {
  return role === 'admin';
}

/**
 * The management destination a role is allowed to be on.
 *
 * The render guards are what actually refuse to mount an Admin screen for an Organizer, so a
 * hand-set or stale view name is not a way in. What it *would* do is leave the workspace pointed
 * at a destination this membership no longer offers — after a demotion, or a switch to a
 * community where the caller is only an Organizer — which presents as an unexplained blank page.
 * Resolving the view back to a permitted destination is what closes that.
 *
 * `view` stays a plain `string` on purpose: it can arrive from persisted state or a hand edit, so
 * it genuinely is untrusted. The return is the other end of that — the union of names the
 * catalogue actually offers — which is what lets the shell hand the result to `setView` with no
 * cast and no widening to `string`.
 *
 * Returns `undefined` only when the role has no management destinations at all.
 */
export function permittedManagementView(
  view: string,
  items: readonly NavItem[],
): ManagementViewId | undefined {
  // Matching a string against the offered items is itself the narrowing: what comes back is an id
  // from the catalogue, not the string that was passed in.
  const offered = items.find(item => item.id === view);
  if (offered) return offered.id;
  return items[0]?.id;
}
