import { useEffect, useState } from 'react';
import { EmptyState } from './AppShell';
import { apiJson, ApiError, getLiveToken } from './api';

type Member = {
  id: string;
  user_id: string;
  username?: string;
  display_name?: string;
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
  const liveToken = () => getLiveToken() ?? token;

  const getCommunityId = async (): Promise<string | undefined> => {
    if (communityId) return communityId;
    const memberships = await apiJson<any[]>('communities/me', {}, liveToken());
    return memberships[0]?.id;
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

  const updateStatus = async (member: Member, status: string) => {
    try {
      const id = await getCommunityId();
      await apiJson<unknown>(`communities/${id}/members/${member.id}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      }, liveToken());
      setMessage(`${member.display_name || member.username || 'Member'} ${status === 'active' ? 'activated' : 'deactivated'}.`);
      await load();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Unable to update membership.');
    }
  };

  const changeRole = async () => {
    if (!roleChangeTarget || !newRole) return;
    try {
      const id = await getCommunityId();
      await apiJson<unknown>(`communities/${id}/members/${roleChangeTarget.id}/role`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: newRole }),
      }, liveToken());
      setMessage(`${roleChangeTarget.display_name || roleChangeTarget.username || 'Member'}'s role changed to ${newRole}.`);
      setRoleChangeTarget(null);
      setNewRole('');
      await load();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Unable to change role.');
    }
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
    return (m.display_name || '').toLowerCase().includes(q) || (m.username || '').toLowerCase().includes(q);
  });

  return (
    <div>
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
              placeholder="Search members…"
              aria-label="Search members"
              style={{ width: '16rem' }}
            />
          </div>
          <button className="accent sm" onClick={() => setShowInvite(!showInvite)}>
            {showInvite ? 'Cancel' : '+ Invite member'}
          </button>
        </div>
      </div>

      {/* Invite form */}
      {showInvite && (
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
          action="Invite member"
          onAction={() => setShowInvite(true)}
        />
      )}

      {!loading && filtered.length === 0 && members.length > 0 && (
        <p className="text-muted">No members match your search.</p>
      )}

      <div className="responsive-table">
        {filtered.length > 0 && (
          <table>
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
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '.65rem' }}>
                      <div style={{ width: '2rem', height: '2rem', borderRadius: '50%', background: 'var(--tv-accent-light)', display: 'grid', placeItems: 'center', color: 'var(--tv-accent)', fontWeight: 800, fontSize: '.8rem', flexShrink: 0 }}>
                        {(member.display_name || member.username || '?').slice(0, 1).toUpperCase()}
                      </div>
                      <div>
                        <strong style={{ fontSize: '.875rem' }}>{member.display_name || 'Private member'}</strong>
                        {member.username && <p style={{ margin: 0, fontSize: '.75rem', color: 'var(--tv-muted)' }}>@{member.username}</p>}
                      </div>
                    </div>
                  </td>
                  <td><span className={`chip ${ROLE_COLORS[member.role] || 'chip-default'}`}>{member.role}</span></td>
                  <td><span className={`chip ${STATUS_COLORS[member.status] || 'chip-default'}`}>{member.status}</span></td>
                  <td style={{ fontSize: '.8rem', color: 'var(--tv-muted)' }}>
                    {member.joined_at ? new Date(member.joined_at).toLocaleDateString() : '—'}
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: '.4rem', flexWrap: 'wrap' }}>
                      <button
                        className="secondary sm"
                        onClick={() => { setRoleChangeTarget(member); setNewRole(member.role); }}
                        title="Change role"
                      >
                        Change role
                      </button>
                      {member.status === 'active' ? (
                        <button className="secondary sm" onClick={() => updateStatus(member, 'inactive')}>Deactivate</button>
                      ) : member.status === 'inactive' ? (
                        <button className="accent sm" onClick={() => updateStatus(member, 'active')}>Activate</button>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Role change confirmation modal */}
      {roleChangeTarget && (
        <div
          style={{ position: 'fixed', inset: 0, background: 'rgba(15,23,42,.5)', zIndex: 300, display: 'grid', placeItems: 'center', padding: '1rem' }}
          onClick={() => setRoleChangeTarget(null)}
        >
          <div className="panel" style={{ width: 'min(100%, 28rem)' }} onClick={e => e.stopPropagation()}>
            <h2 style={{ fontSize: '1.1rem', marginBottom: '1rem' }}>Change role</h2>
            <p style={{ color: 'var(--tv-muted)', marginBottom: '1rem' }}>
              Change role for <strong>{roleChangeTarget.display_name || roleChangeTarget.username || 'this member'}</strong>
            </p>
            <label>
              <span className="label-text">New role</span>
              <select value={newRole} onChange={e => setNewRole(e.target.value)}>
                <option value="member">Member</option>
                <option value="organizer">Organizer</option>
              </select>
            </label>
            <div className="form-actions" style={{ marginTop: '1rem' }}>
              <button className="accent" onClick={changeRole} disabled={newRole === roleChangeTarget.role}>
                Confirm role change
              </button>
              <button className="secondary" onClick={() => setRoleChangeTarget(null)}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
