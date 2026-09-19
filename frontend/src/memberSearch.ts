/**
 * The constrained member-lookup contract shared by the Organizer member screen.
 *
 * Organizers resolve one member at a time; the community directory itself is Admin-only. Keeping
 * the request shape in a pure function means the rule that matters — *a real query, and never a
 * directory path* — is unit-testable without a DOM, and cannot drift from the screen that uses it.
 */

/** Matches the backend floor: `Query(min_length=2)` on `/members/search`. */
export const MIN_SEARCH_LENGTH = 2;
/** Matches the backend cap on a single lookup. Informational: the server is authoritative. */
export const MEMBER_SEARCH_LIMIT = 10;

export type MemberSearchRequest =
  | { ok: true; path: string }
  | { ok: false; reason: string };

/**
 * Build the constrained lookup request, or explain why no request should be made.
 *
 * The returned path is always the query-bound `/members/search` route: this function has no way to
 * express the Admin directory (`/members`), so an Organizer screen built on it cannot page through
 * the community even by accident.
 */
export function memberSearchRequest(communityId: string | undefined, rawQuery: string): MemberSearchRequest {
  if (!communityId) return { ok: false, reason: 'No active community selected.' };
  const term = rawQuery.trim();
  if (term.length < MIN_SEARCH_LENGTH) {
    return { ok: false, reason: `Enter at least ${MIN_SEARCH_LENGTH} characters to search.` };
  }
  return { ok: true, path: `communities/${communityId}/members/search?q=${encodeURIComponent(term)}` };
}
