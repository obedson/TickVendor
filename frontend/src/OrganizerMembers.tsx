import { useEffect, useState } from 'react';
import './management.css';
import { GovernanceConfirm } from './GovernanceConfirm';
import { CommunityAccessEditor } from './CommunityAccessEditor';
import { EmptyState } from './AppShell';
import { apiJson, ApiError, getLiveToken } from './api';
import { memberSearchRequest, MIN_SEARCH_LENGTH } from './memberSearch';
import type { CommunityRole } from './managementNav';

type Member = {
  id: string;
  user_id: string;
  username?: string;
  display_name?: string;
  email?: string;
  role: string;
  status: string;
  joined_at?: string;
};

/** One constrained lookup result. `membership_id` is not needed to display or act on a match. */
type MemberMatch = {
  user_id: string;
  membership_id: string;
  display_name: string;
  username: string | null;
  role: string;
  status: string;
  /** Returned only when the Organizer searched by that exact address. */
  email?: string;
};

const ROLE_COLORS: Record<string, string> = { admin: 'chip-blue', organizer: 'chip-teal', member: 'chip-green' };
const STATUS_COLORS: Record<string, string> = { active: 'chip-green', inactive: 'chip-default', invited: 'chip-yellow', pending: 'chip-yellow' };

export function OrganizerMembers({ token, communityId, role }: { token: string; communityId?: string; role?: CommunityRole }) {
  const [members, setMembers] = useState<Member[]>([]);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [showInvite, setShowInvite] = useState(false);
  const [inviteIdentifier, setInviteIdentifier] = useState('');
  const [inviteRole, setInviteRole] = useState('member');
  const [inviting, setInviting] = useState(false);
  const [roleChangeTarget, setRoleChangeTarget] = useState<Member | null>(null);
  const [newRole, setNewRole] = useState('');
  const [viewerId, setViewerId] = useState('');
  const [membershipAction, setMembershipAction] = useState<{ member: Member; action: string } | null>(null);
  // Resolved community membership role. The prop is authoritative; it is only absent when this
  // screen is reached without a workspace selection, in which case we read it back from the API.
  const [resolvedRole, setResolvedRole] = useState<CommunityRole | undefined>(role);
  useEffect(() => { setResolvedRole(role); }, [role]);
  // Organizer lookup state.
  const [query, setQuery] = useState('');
  const [matches, setMatches] = useState<MemberMatch[]>([]);
  const [lookupError, setLookupError] = useState('');
  const [searching, setSearching] = useState(false);
  const [searchRun, setSearchRun] = useState(false);
  useEffect(() => { apiJson<{ id: string }>('auth/me', {}, getLiveToken() ?? token).then(user => setViewerId(user.id)).catch(() => setViewerId('')); }, [token]);
  const liveToken = () => getLiveToken() ?? token;

  const getCommunityId = async (): Promise<string | undefined> => {
    if (communityId) return communityId;
    const memberships = await apiJson<any[]>('communities/me', {}, liveToken());
    const manageable = memberships.filter(item => item.membership?.status === 'active' && item.community?.is_active !== false);
    // Prefer a community this user administers, but an Organizer's community is a valid fallback:
    // the page itself branches on `role`, so the lookup below is the constrained one either way.
    return (manageable.find(item => item.membership?.role === 'admin') ?? manageable.find(item => item.membership?.role === 'organizer'))?.id;
  };

  const isAdmin = resolvedRole === 'admin';

  // Resolve the community role when it was not handed down, so this screen still works on its own.
  useEffect(() => {
    if (role || !communityId) return;
    let cancelled = false;
    apiJson<any[]>('communities/me', {}, liveToken())
      .then(items => {
        if (cancelled) return;
        const match = items.find(item => item.id === communityId);
        setResolvedRole((match?.membership?.role as CommunityRole | undefined) ?? undefined);
      })
      .catch(() => { if (!cancelled) setResolvedRole(undefined); });
    return () => { cancelled = true; };
  }, [role, communityId, token]);

  const canManage = isAdmin;

  const load = async () => {
    setLoading(true); setError('');
    try {
      const id = await getCommunityId();
      if (!id) { setError('No active community selected.'); return; }
      // The full directory is Admin-gated; Organizers use the constrained lookup below instead.
      const data = await apiJson<{ members: Member[] }>(`communities/${id}/members`, {}, liveToken());
      setMembers(data.members);
    } catch (cause) {
      setError(cause instanceof ApiError && cause.status === 403 ? 'Administrator access required.' : 'Unable to load members.');
    } finally { setLoading(false); }
  };

  useEffect(() => { if (isAdmin) load(); else { setLoading(false); setMembers([]); } }, [token, communityId, isAdmin]);

  const runLookup = async (event: React.FormEvent) => {
    event.preventDefault();
    const term = query.trim();
    const target = communityId ?? (await getCommunityId());
    const request = memberSearchRequest(target, term);
    if (!request.ok) { setLookupError(request.reason); return; }
    setSearching(true); setLookupError(''); setSearchRun(false);
    try {
      const data = await apiJson<{ members: MemberMatch[] }>(request.path, {}, liveToken());
      setMatches(data.members);
      setSearchRun(true);
    } catch (cause) {
      setMatches([]); setSearchRun(false);
      setLookupError(cause instanceof ApiError && cause.status === 403
        ? 'Organizer access required.'
        : cause instanceof ApiError ? cause.message : 'Unable to search members.');
    } finally { setSearching(false); }
  };

  const changeRole = async (reason: string) => {
    if (!roleChangeTarget || !newRole) return;
    const id = await getCommunityId();
    await apiJson(`communities/${id}/members/${roleChangeTarget.id}/role`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ role: newRole, reason }),
    }, liveToken());
    setMessage('Membership role updated.'); await load();
  };

  const updateMembership = async (reason: string) => {
    if (!membershipAction) return;
    const { member, action } = membershipAction;
    const id = await getCommunityId();
    const review = ['approved', 'rejected'].includes(action);
    await apiJson(review ? `communities/${id}/membership-requests/${member.id}/${action}` : `communities/${id}/members/${member.id}/status`, {
      method: review ? 'POST' : 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(review ? { reason } : { reason, status: action }),
    }, liveToken());
    setMessage('Membership updated.'); await load();
  };

  const inviteMember = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteIdentifier.trim()) return;
    setInviting(true); setError('');
    try {
      const id = await getCommunityId();
      await apiJson<unknown>(`communities/${id}/members/invite`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ identifier: inviteIdentifier.trim(), role: inviteRole }),
      }, liveToken());
      setMessage(`Invitation sent to ${inviteIdentifier}.`);
      setInviteIdentifier('');
      setInviteRole('member');
      setShowInvite(false);
      await load();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Unable to send invitation.');
    } finally { setInviting(false); }
  };

  const filtered = members.filter(m => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (m.display_name || '').toLowerCase().includes(q) || (m.username || '').toLowerCase().includes(q) || (m.email || '').toLowerCase().includes(q);
  });

  // ── Organizer view: constrained single-member lookup, never the directory ────────────────
  if (!isAdmin) {
    return (
      <div className="management-screen">
        <div className="page-header">
          <div className="page-header-text">
            <p className="eyebrow">Program operations</p>
            <h1>Find a member</h1>
            <p>Look up one community member by exact email address, username, or display name.</p>
          </div>
        </div>
        <div className="panel" style={{ marginBottom: '1.5rem' }}>
          <form onSubmit={runLookup} style={{ display: 'grid', gap: '.75rem' }}>
            <label>
              <span className="label-text">Exact email address, username, or name *</span>
              <input
                required
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder="user@example.com, @username or Ada Lovelace"
                autoComplete="off"
                aria-label="Search a community member by exact email address, username, or display name"
                minLength={MIN_SEARCH_LENGTH}
              />
            </label>
            <div className="form-actions">
              <button type="submit" className="accent sm" disabled={searching || query.trim().length < MIN_SEARCH_LENGTH}>
                {searching ? 'Searching…' : 'Search'}
              </button>
            </div>
          </form>
          {/* Email addresses are only returned for an exact-address search, so say so plainly. */}
          <p className="text-muted" style={{ marginTop: '.75rem', fontSize: '.8rem' }}>
            A name or username search returns identity and membership status only. Search by an exact
            email address to see that member's address.
          </p>
        </div>

        {lookupError && <p role="alert" className="error" style={{ marginBottom: '1rem' }}>{lookupError}</p>}

        {searchRun && !matches.length && !lookupError && (
          <EmptyState
            title="No matching member"
            description="No active member of this community matches that search."
          />
        )}

        {matches.length > 0 && (
          <div className="responsive-table">
            <table className="management-table">
              <caption>Member lookup results</caption>
              <thead>
                <tr>
                  <th>Member</th>
                  <th>Role</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {matches.map(match => (
                  <tr key={match.user_id}>
                    <td data-label="Member">
                      <strong style={{ fontSize: '.875rem' }}>{match.display_name || 'Private member'}</strong>
                      {match.username && <p style={{ margin: 0, fontSize: '.75rem', color: 'var(--tv-muted)' }}>@{match.username}</p>}
                      {match.email && <p style={{ margin: 0, fontSize: '.75rem', color: 'var(--tv-muted)', overflowWrap: 'anywhere' }}>{match.email}</p>}
                    </td>
                    <td data-label="Role"><span className={`chip ${ROLE_COLORS[match.role] || 'chip-default'}`}>{match.role}</span></td>
                    <td data-label="Status"><span className={`chip ${STATUS_COLORS[match.status] || 'chip-default'}`}>{match.status}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    );
  }

  // ── Administrator view: the full community directory and membership management ────────────
  return (
    <div className="management-screen">
      {canManage && communityId && <CommunityAccessEditor token={token} communityId={communityId} />}
      <div className="page-header">
        <div className="page-header-text">
          <p className="eyebrow">Community administration</p>
          <h1>Members</h1>
          <p>Manage community membership and roles.</p>
        </div>
        <div className="page-header-actions">
          <div className="search-input">
            <span className="search-icon" aria-hidden="true">⌕</span>
            <input
              type="search"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search name, username or email…"
              aria-label="Search members by name, username or email"
              className="filter-control"
            />
          </div>
          {canManage && <button className="accent sm" onClick={() => setShowInvite(!showInvite)}>
            {showInvite ? 'Cancel' : '+ Invite member'}
          </button>}
        </div>
      </div>

      {/* Invite form */}
      {canManage && showInvite && (
        <div className="panel" style={{ marginBottom: '1.5rem' }}>
          <h2 style={{ fontSize: '1rem', marginBottom: '1rem' }}>Invite a member</h2>
          <form onSubmit={inviteMember} style={{ display: 'grid', gap: '.75rem' }}>
            <label>
              <span className="label-text">Email address or username *</span>
              <input
                required
                value={inviteIdentifier}
                onChange={e => setInviteIdentifier(e.target.value)}
                placeholder="user@example.com or @username"
                autoComplete="off"
              />
            </label>
            <label>
              <span className="label-text">Role</span>
              <select value={inviteRole} onChange={e => setInviteRole(e.target.value)}>
                <option value="member">Member</option>
                <option value="organizer">Organizer</option>
              </select>
            </label>
            <div className="form-actions">
              <button type="submit" className="accent sm" disabled={inviting}>
                {inviting ? 'Sending…' : 'Send invitation'}
              </button>
              <button type="button" className="secondary sm" onClick={() => { setShowInvite(false); setInviteIdentifier(''); }}>
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {error && <p role="alert" className="error" style={{ marginBottom: '1rem' }}>{error}</p>}
      {message && <p role="status" className="success-msg" style={{ marginBottom: '1rem' }}>{message}</p>}
      {loading && <p role="status" className="text-muted">Loading members…</p>}

      {!loading && !error && !members.length && (
        <EmptyState
          title="No members"
          description="This community has no members yet. Invite someone to get started."
          action={canManage ? "Invite member" : undefined}
          onAction={canManage ? () => setShowInvite(true) : undefined}
        />
      )}

      {!loading && filtered.length === 0 && members.length > 0 && (
        <p className="text-muted">No members match your search.</p>
      )}

      <div className="responsive-table">
        {filtered.length > 0 && (
          <table className="management-table">
            <caption>Community members</caption>
            <thead>
              <tr>
                <th>Member</th>
                <th>Role</th>
                <th>Status</th>
                <th>Joined</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(member => (
                <tr key={member.id}>
                  <td data-label="Member">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '.65rem' }}>
                      <div style={{ width: '2rem', height: '2rem', borderRadius: '50%', background: 'var(--tv-accent-light)', display: 'grid', placeItems: 'center', color: 'var(--tv-accent)', fontWeight: 800, fontSize: '.8rem', flexShrink: 0 }}>
                        {(member.display_name || member.username || '?').slice(0, 1).toUpperCase()}
                      </div>
                      <div>
                        <strong style={{ fontSize: '.875rem' }}>{member.display_name || 'Private member'}</strong>
                        {member.username && <p style={{ margin: 0, fontSize: '.75rem', color: 'var(--tv-muted)' }}>@{member.username}</p>}
                        {/* Only returned on this Admin-gated directory; two similar display names are otherwise indistinguishable. */}
                        {member.email && <p style={{ margin: 0, fontSize: '.75rem', color: 'var(--tv-muted)', overflowWrap: 'anywhere' }}>{member.email}</p>}
                      </div>
                    </div>
                  </td>
                  <td data-label="Role"><span className={`chip ${ROLE_COLORS[member.role] || 'chip-default'}`}>{member.role}</span></td>
                  <td data-label="Status"><span className={`chip ${STATUS_COLORS[member.status] || 'chip-default'}`}>{member.status}</span></td>
                  <td data-label="Joined" style={{ fontSize: '.8rem', color: 'var(--tv-muted)' }}>
                    {member.joined_at ? new Date(member.joined_at).toLocaleDateString() : '—'}
                  </td>
                  <td data-label="Actions">
                    <div style={{ display: 'flex', gap: '.4rem', flexWrap: 'wrap' }}>
                      {canManage && viewerId && member.user_id !== viewerId && member.role !== 'admin' && <>
                        {['active', 'suspended'].includes(member.status) && <><button className="secondary sm" title="Change role" onClick={() => { setRoleChangeTarget(member); setNewRole(member.role); }}>Change role</button>
                        <button className="secondary sm" onClick={() => setMembershipAction({ member, action: member.status === 'active' ? 'suspended' : 'active' })}>{member.status === 'active' ? 'Deactivate' : 'Activate'}</button></>}
                        {member.status === 'pending' && <><button onClick={() => setMembershipAction({ member, action: 'approved' })}>Approve request</button><button className="secondary" onClick={() => setMembershipAction({ member, action: 'rejected' })}>Reject request</button></>}
                      </>}
                      {member.role === 'admin' && <small>Managed by Platform Super Admin</small>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {roleChangeTarget && <GovernanceConfirm title={`Change role for ${roleChangeTarget.display_name || roleChangeTarget.username || 'member'}`} consequence="Changes Member/Organizer authority in this community only." onClose={() => setRoleChangeTarget(null)} onConfirm={changeRole}>
        <label>New role<select value={newRole} onChange={event => setNewRole(event.target.value)}><option value="member">Member</option><option value="organizer">Organizer</option></select></label>
      </GovernanceConfirm>}
      {membershipAction && <GovernanceConfirm title={`${membershipAction.action} — ${membershipAction.member.display_name || membershipAction.member.username || 'member'}`} consequence="Membership access will change; participation and audit history remain." onClose={() => setMembershipAction(null)} onConfirm={updateMembership} />}
    </div>
  );
}
