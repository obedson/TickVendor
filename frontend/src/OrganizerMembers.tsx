import { useEffect, useState } from 'react';
import './management.css';
import { GovernanceConfirm } from './GovernanceConfirm';
import { CommunityAccessEditor } from './CommunityAccessEditor';
import { EmptyState } from './AppShell';
import { apiJson, ApiError, getLiveToken } from './api';

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

const ROLE_COLORS: Record<string, string> = { admin: 'chip-blue', organizer: 'chip-teal', member: 'chip-green' };
const STATUS_COLORS: Record<string, string> = { active: 'chip-green', inactive: 'chip-default', invited: 'chip-yellow', pending: 'chip-yellow' };

export function OrganizerMembers({ token, communityId }: { token: string; communityId?: string }) {
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
  useEffect(() => { apiJson<{ id: string }>('auth/me', {}, getLiveToken() ?? token).then(user => setViewerId(user.id)).catch(() => setViewerId('')); }, [token]);
  const canManage = members.some(member => member.user_id === viewerId && member.role === 'admin' && member.status === 'active');
  const liveToken = () => getLiveToken() ?? token;

  const getCommunityId = async (): Promise<string | undefined> => {
    if (communityId) return communityId;
    const memberships = await apiJson<any[]>('communities/me', {}, liveToken());
    return memberships.find(item => item.membership?.status === 'active' && item.community?.is_active && item.membership?.role === 'admin')?.id;
  };

  const load = async () => {
    setLoading(true); setError('');
    try {
      const id = await getCommunityId();
      if (!id) { setError('No active community selected.'); return; }
      const data = await apiJson<{ members: Member[] }>(`communities/${id}/members`, {}, liveToken());
      setMembers(data.members);
    } catch (cause) {
      setError(cause instanceof ApiError && cause.status === 403 ? 'Administrator access required.' : 'Unable to load members.');
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [token, communityId]);

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
                        {/* Only returned to organizers/administrators of this community; two similar display names are otherwise indistinguishable. */}
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
