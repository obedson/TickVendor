/**
 * Role-aware management navigation tests.
 *
 * Organizers operate programs; Admins govern the community. Both enter the management workspace,
 * so the control that matters is that the navigation is derived from the *selected community
 * membership role* — never the platform role — and that no governance destination survives for an
 * Organizer. These are pure-module tests: no DOM, no network.
 *
 * Framework: vitest (not currently a dependency of this package).
 * To run:  npm install --no-save --no-package-lock vitest && npx vitest run src/__tests__/managementNav.test.ts
 */

import { describe, it, expect } from 'vitest';
import {
  adminOnlyNavIds,
  isCommunityAdmin,
  managementNav,
  managementNavItems,
  organizerNavIds,
  permittedManagementView,
} from '../managementNav';
import { memberSearchRequest, MIN_SEARCH_LENGTH } from '../memberSearch';

const ids = (items: { id: string }[]) => items.map(item => item.id);

describe('managementNav — Organizer view', () => {
  it('offers operational destinations and not one governance destination', () => {
    const nav = ids(managementNav('organizer', false));
    expect(nav).toContain('organizer-events');
    expect(nav).toContain('organizer-tasks');
    expect(nav).toContain('organizer-members');
    expect(nav).toContain('organizer-review');
    expect(nav).toContain('organizer-attendance');
    expect(nav).toContain('organizer-redemption');
    // Every Admin-only destination is absent, including the one whose id looks operational.
    for (const governance of adminOnlyNavIds) expect(nav).not.toContain(governance);
    expect(nav).not.toContain('organizer-opportunities');
    expect(nav).not.toContain('platform-admin');
    expect(nav.sort()).toEqual([...organizerNavIds].sort());
  });
});

describe('managementNav — community Admin view', () => {
  it('adds community governance on top of the operational destinations', () => {
    const nav = ids(managementNav('admin', false));
    for (const governance of adminOnlyNavIds) expect(nav).toContain(governance);
    for (const operational of organizerNavIds) expect(nav).toContain(operational);
    expect(nav).toHaveLength(managementNavItems.length);
    // Community governance is not platform governance.
    expect(nav).not.toContain('platform-admin');
  });

  it('keeps platform administration separate and adds it only for a Super Admin', () => {
    expect(ids(managementNav('admin', true))).toContain('platform-admin');
    expect(ids(managementNav('organizer', true))).toContain('platform-admin');
    expect(ids(managementNav('organizer', true))).not.toContain('admin-audit');
  });
});

describe('managementNav — the selected community membership role decides', () => {
  it('gives a plain member no management destinations at all', () => {
    expect(managementNav('member', false)).toEqual([]);
    expect(managementNav(undefined, false)).toEqual([]);
    expect(isCommunityAdmin(undefined)).toBe(false);
  });

  it('partitions the catalogue: no destination is both governance and operational', () => {
    const overlap = organizerNavIds.filter(id => adminOnlyNavIds.includes(id));
    expect(overlap).toEqual([]);
    expect(organizerNavIds.length + adminOnlyNavIds.length).toBe(managementNavItems.length);
  });
});

describe('member lookup — constrained search, never the directory', () => {
  it('refuses a query shorter than two characters, like the backend does', () => {
    const short = memberSearchRequest('community-1', ' a ');
    expect(short.ok).toBe(false);
    expect(memberSearchRequest('community-1', '')).toEqual({
      ok: false, reason: `Enter at least ${MIN_SEARCH_LENGTH} characters to search.`,
    });
  });

  it('requires a community and always targets the query-bound search route', () => {
    expect(memberSearchRequest(undefined, 'ada@example.com').ok).toBe(false);
    const request = memberSearchRequest('community-1', '  ada@example.com  ');
    expect(request).toEqual({ ok: true, path: 'communities/community-1/members/search?q=ada%40example.com' });
    if (!request.ok) throw new Error('expected a search request');
    // The one path this contract can produce is the constrained lookup: the Admin directory route
    // (`communities/<id>/members`) is not reachable from an Organizer screen built on it.
    expect(request.path.startsWith('communities/community-1/members/search?q=')).toBe(true);
    expect(request.path).not.toBe('communities/community-1/members');
    // A wildcard cannot be smuggled through as a directory dump.
    const wildcard = memberSearchRequest('community-1', '%%');
    expect(wildcard.ok && wildcard.path).toBe('communities/community-1/members/search?q=%25%25');
  });
});

describe('permittedManagementView — a stale or hand-set view resolves to a permitted one', () => {
  it('leaves a destination the current role is offered untouched', () => {
    const organizer = managementNav('organizer', false);
    expect(permittedManagementView('organizer-tasks', organizer)).toBe('organizer-tasks');
    const admin = managementNav('admin', false);
    expect(permittedManagementView('admin-audit', admin)).toBe('admin-audit');
  });

  it('refuses every governance destination to an Organizer and falls back to the first item', () => {
    const organizer = managementNav('organizer', false);
    // Setting the view name by hand is not a way in: each Admin-only name resolves elsewhere.
    for (const governance of adminOnlyNavIds) {
      const resolved = permittedManagementView(governance, organizer);
      expect(resolved).toBe('organizer-dashboard');
      expect(adminOnlyNavIds).not.toContain(resolved);
    }
    expect(permittedManagementView('organizer-opportunities', organizer)).toBe('organizer-dashboard');
    expect(permittedManagementView('platform-admin', organizer)).toBe('organizer-dashboard');
  });

  it('drops a Super Admin back to the Organizer view of a community they only organize', () => {
    // The platform role adds `platform-admin` but does not substitute for the membership role.
    const superAdminOrganizer = managementNav('organizer', true);
    expect(superAdminOrganizer.map(item => item.id)).toContain('platform-admin');
    expect(permittedManagementView('admin-rules', superAdminOrganizer)).toBe('organizer-dashboard');
    expect(permittedManagementView('platform-admin', superAdminOrganizer)).toBe('platform-admin');
  });

  it('lets a demoted Admin keep working on the Organizer surface instead of a blank page', () => {
    const afterDemotion = managementNav('organizer', false);
    expect(permittedManagementView('admin-analytics', afterDemotion)).toBe('organizer-dashboard');
  });

  it('has nowhere to send a role with no management destinations', () => {
    expect(permittedManagementView('admin-audit', managementNav('member', false))).toBeUndefined();
    expect(permittedManagementView('admin-audit', managementNav(undefined, false))).toBeUndefined();
  });
});
