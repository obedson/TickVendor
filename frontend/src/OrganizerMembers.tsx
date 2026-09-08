import { useEffect, useState } from 'react';
import { EmptyState } from './AppShell';

type Member = { id: string; user_id: string; username?: string; display_name?: string; role: string; status: string; joined_at?: string };

const ROLE_COLORS: Record<string, string> = { admin: 'chip-blue', organizer: 'chip-teal', member: 'chip-green' };
const STATUS_COLORS: Record<string, string> = { active: 'chip-green', inactive: 'chip-default', pending: 'chip-yellow' };

export function OrganizerMembers({ token, communityId }: { token: string; communityId?: string }) {
  const [members, setMembers] = useState<Member[]>([]);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const headers = { Authorization: `Bearer ${token}` };

  const load = async () => {
    setLoading(true);
    try {
      let id = communityId;
      if (!id) {
        const memberships = await fetch('/api/v1/communities/me', { headers });
        if (!memberships.ok) { setError('Unable to load communities.'); return; }
        id = (await memberships.json())[0]?.id;
      }
      if (!id) { setError('No active community selected.'); return; }
      const response = await fetch(`/api/v1/communities/${id}/members`, { headers });
      if (!response.ok) { setError(response.status === 403 ? 'Administrator access required.' : 'Unable to load members.'); return; }
      setMembers((await response.json()).members);
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [token, communityId]);

  const updateStatus = async (member: Member, status: string) => {
    let id = communityId;
    if (!id) {
      const memberships = await fetch('/api/v1/communities/me', { headers });
      id = (await memberships.json())[0]?.id;
    }
    const response = await fetch(`/api/v1/communities/${id}/members/${member.id}/status`, {
      method: 'PATCH',
      headers: { ...headers, 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    });
    if (!response.ok) { setError('Unable to update membership.'); return; }
    setMessage(`${member.display_name || member.username || 'Member'} ${status === 'active' ? 'activated' : 'deactivated'}.`);
    await load();
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
              style={{ width: '18rem' }}
            />
          </div>
        </div>
      </div>

      {error && <p role="alert" className="error" style={{ marginBottom: '1rem' }}>{error}</p>}
      {message && <p role="status" className="success-msg" style={{ marginBottom: '1rem' }}>{message}</p>}
      {loading && <p role="status" className="text-muted">Loading members…</p>}

      {!loading && !error && !members.length && (
        <EmptyState title="No members" description="This community has no members yet." />
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
                    {member.status === 'active' ? (
                      <button className="secondary sm" onClick={() => updateStatus(member, 'inactive')}>Deactivate</button>
                    ) : (
                      <button className="accent sm" onClick={() => updateStatus(member, 'active')}>Activate</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
