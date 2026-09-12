import { useEffect, useState, type ReactNode } from 'react';
import { apiJson, getLiveToken } from './api';
import { GovernanceConfirm } from './GovernanceConfirm';
import './management.css';

type Kind = 'user' | 'community' | 'event' | 'opportunity' | 'task';
type Membership = { membership_id: string; id: string; name: string; community_name: string; role: string; status: string };
type Item = { id: string; name: string; suspended: boolean; role?: string; email?: string; username?: string; is_email_verified?: boolean; member_count?: number; membership_access?: string; is_public?: boolean; community_name?: string; status?: string; owner?: { name: string }; description?: string; membership_offset?: number; memberships_has_more?: boolean; active_admin_count?: number; memberships?: Membership[] };
type History = { id: string; actor: string; action: string; target_type: string; target_name: string; reason: string; community?: string; occurred_at: string; previous?: Record<string, unknown>; result?: Record<string, unknown> };
const base = 'admin/platform/governance';
const labels = { user: 'Users', community: 'Communities', event: 'Events', opportunity: 'Opportunities', task: 'Tasks' };

export function PlatformGovernance({ token, userRole, categories }: { token: string; userRole: string; categories: ReactNode }) {
  const [section, setSection] = useState('overview');
  const [kind, setKind] = useState<Kind>('event');
  const [q, setQ] = useState('');
  const [status, setStatus] = useState('');
  const [suspended, setSuspended] = useState('');
  const [after, setAfter] = useState('');
  const [before, setBefore] = useState('');
  const [community, setCommunity] = useState('');
  const [communityQuery, setCommunityQuery] = useState('');
  const [creator, setCreator] = useState('');
  const [offset, setOffset] = useState(0);
  const [items, setItems] = useState<Item[]>([]);
  const [communities, setCommunities] = useState<Item[]>([]);
  const [users, setUsers] = useState<Item[]>([]);
  const [userQuery, setUserQuery] = useState('');
  const [assignee, setAssignee] = useState('');
  const [selected, setSelected] = useState<Item | null>(null);
  const [historyTarget, setHistoryTarget] = useState('');
  const [history, setHistory] = useState<History[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [pending, setPending] = useState<{ title: string; consequence: string; path: string; method?: string; body: Record<string, unknown> } | null>(null);
  const currentKind: Kind = section === 'users' ? 'user' : section === 'communities' ? 'community' : kind;
  const live = () => getLiveToken() ?? token;
  const load = async () => {
    setError(''); setLoading(true);
    try {
      if (section === 'history') setHistory(await apiJson<History[]>(`${base}/history?offset=${offset}${historyTarget ? `&target_id=${historyTarget}` : ''}`, {}, live()));
      else if (['users', 'communities', 'content'].includes(section)) {
        const query = new URLSearchParams({ q, offset: String(offset) });
        if (suspended) query.set('suspended', suspended);
        if (section === 'content') {
          if (community) query.set('community_id', community);
          if (creator) query.set('creator_id', creator);
          if (status) query.set('status', status);
        }
        if (after) query.set('after', `${after}T00:00:00Z`);
        if (before) query.set('before', `${before}T23:59:59Z`);
        setItems(await apiJson<Item[]>(`${base}/${currentKind}?${query}`, {}, live()));
      }
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to load governance.'); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, [token, section, kind, offset, historyTarget]);
  useEffect(() => {
    if (userRole !== 'super_admin') return;
    apiJson<Item[]>(`${base}/community`, {}, live()).then(setCommunities).catch(() => setCommunities([]));
  }, [token, userRole]);
  const inspect = async (item: Item, membershipOffset = 0) => {
    setError(''); setAssignee('');
    try { setSelected(await apiJson<Item>(`${base}/${currentKind}/${item.id}?membership_offset=${membershipOffset}`, {}, live())); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Inspection failed.'); }
  };
  const searchUsers = async () => {
    setError('');
    try { setUsers(await apiJson<Item[]>(`${base}/user?q=${encodeURIComponent(userQuery)}`, {}, live())); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'User search failed.'); }
  };
  const changeSection = (next: string) => { setSection(next); setSelected(null); setItems([]); setOffset(0); setQ(''); setError(''); setMessage(''); setStatus(''); setSuspended(''); setHistoryTarget(''); setAfter(''); setBefore(''); setCommunity(''); setCreator(''); };
  if (userRole !== 'super_admin') return <p role="alert">Super Admin access required.</p>;
  return <section className="management-screen"><div className="page-header"><div><p className="eyebrow">Platform</p><h1>Platform Administration</h1></div></div>
    <nav className="section-tabs" aria-label="Platform administration sections">{[['overview', 'Overview'], ['users', 'Users'], ['communities', 'Communities'], ['content', 'Content Moderation'], ['categories', 'Categories'], ['history', 'Moderation History']].map(([id, label]) => <button key={id} aria-pressed={section === id} className="secondary" onClick={() => changeSection(id)}>{label}</button>)}</nav>
    {error && <p className="error" role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    {section === 'overview' && <div className="panel"><h2>Governance and oversight</h2><p>Assign community administrators, manage membership authority and apply reversible policy suspensions. Every governance change records a reason and history. Financial and participation evidence is retained.</p></div>}
    {section === 'categories' && categories}
    {['users', 'communities', 'content'].includes(section) && <>
      <form className="panel" onSubmit={event => { event.preventDefault(); if (offset) setOffset(0); else void load(); }}>
        {section === 'content' && <label>Content type<select value={kind} onChange={event => { setKind(event.target.value as Kind); setSelected(null); setStatus(''); setOffset(0); }}><option value="event">Events</option><option value="opportunity">Opportunities</option><option value="task">Tasks</option></select></label>}
        <div className="form-row"><label>Search {labels[currentKind]}<input value={q} onChange={event => setQ(event.target.value)} placeholder={section === 'users' ? 'Email, username or name' : 'Name or title'} /></label><label>Moderation state<select value={suspended} onChange={event => setSuspended(event.target.value)}><option value="">All</option><option value="false">Not suspended</option><option value="true">Suspended</option></select></label></div>
        {section === 'content' && <><div className="form-row"><label>Find community<input value={communityQuery} onChange={event => setCommunityQuery(event.target.value)} /></label><button type="button" className="secondary" onClick={() => { void apiJson<Item[]>(`${base}/community?q=${encodeURIComponent(communityQuery)}`, {}, live()).then(setCommunities).catch(cause => setError(cause.message)); }}>Find community</button><label>Community<select value={community} onChange={event => setCommunity(event.target.value)}><option value="">All communities</option>{communities.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Lifecycle status<select value={status} onChange={event => setStatus(event.target.value)}><option value="">All</option>{(kind === 'event' ? ['draft', 'published', 'cancelled', 'completed'] : kind === 'opportunity' ? ['draft', 'published', 'closed', 'cancelled'] : ['active', 'inactive']).map(value => <option key={value}>{value}</option>)}</select></label></div>
        <label>Find creator by email/username<input value={userQuery} onChange={event => setUserQuery(event.target.value)} /></label><button type="button" className="secondary" onClick={() => void searchUsers()}>Find creator</button><label>Creator<select value={creator} onChange={event => setCreator(event.target.value)}><option value="">All creators</option>{users.map(item => <option key={item.id} value={item.id}>{item.name} — {item.email}</option>)}</select></label></>}
        <div className="form-row"><label>Created after<input type="date" value={after} onChange={event => setAfter(event.target.value)} /></label><label>Created before<input type="date" value={before} onChange={event => setBefore(event.target.value)} /></label></div><button disabled={loading}>Search</button>
      </form>
      {loading ? <p role="status">Loading…</p> : <div className="definition-list">{items.map(item => <article key={item.id} className="definition-card"><div><h2>{item.name}</h2><p>{item.email || item.community_name} {item.owner ? `· ${item.owner.name}` : ''}</p><span className="chip">{item.suspended ? 'Suspended' : 'Not suspended'}</span>{item.status && <span className="chip">{item.status}</span>}</div><button className="secondary" onClick={() => void inspect(item)}>Inspect {item.name}</button></article>)}{!items.length && <p>No matching records.</p>}</div>}
      {selected && <section className="panel"><h2>{selected.name}</h2><p>{selected.description}</p>{selected.email && <p>{selected.email} · @{selected.username} · {selected.role} · Email {selected.is_email_verified ? 'verified' : 'unverified'}</p>}
        {currentKind === 'community' && <p>{selected.is_public ? 'Public' : 'Private'} · {selected.membership_access?.replaceAll('_', ' ')} · {selected.member_count} active members</p>}
        {!(currentKind === 'user' && selected.role === 'super_admin') && <button className="secondary" onClick={() => setPending({ title: `${selected.suspended ? 'Restore' : 'Suspend'} ${selected.name}`, consequence: 'Suspension blocks ordinary access or content use. Existing records remain; restoration is reversible.', path: `${base}/${currentKind}/${selected.id}/moderation`, body: { suspended: !selected.suspended } })}>{selected.suspended ? 'Restore' : 'Suspend'}</button>}
        {selected.memberships && <><h3>Memberships and administrators</h3>{currentKind === 'community' && <p>{selected.active_admin_count} active Community Admins. Removing the final Admin leaves membership approvals and configuration under Super Admin oversight until another Admin is assigned.</p>}<div className="definition-list">{selected.memberships.map(member => <article className="definition-card" key={member.membership_id}><div><strong>{currentKind === 'user' ? member.community_name : member.name}</strong><p>{member.role} · {member.status}</p></div>{currentKind === 'community' && ['active', 'suspended'].includes(member.status) && <div className="form-actions">{(['member', 'organizer', 'admin'] as const).filter(role => role !== member.role).map(role => <button key={role} className="secondary" onClick={() => setPending({ title: `Change ${member.name} to ${role}`, consequence: 'This changes community authority, not the platform role.', path: `${base}/community/${selected.id}/memberships/${member.membership_id}`, method: 'PATCH', body: { action: 'role_changed', role } })}>Make {role}</button>)}<button className="secondary" onClick={() => setPending({ title: `Change membership access for ${member.name}`, consequence: 'History remains; suspended memberships cannot use community authority.', path: `${base}/community/${selected.id}/memberships/${member.membership_id}`, method: 'PATCH', body: { action: member.status === 'active' ? 'deactivated' : 'activated' } })}>{member.status === 'active' ? 'Deactivate' : 'Activate'}</button></div>}</article>)}</div><div className="form-actions"><button className="secondary" disabled={!selected.membership_offset} onClick={() => void inspect(selected, Math.max(0, (selected.membership_offset || 0) - 50))}>Previous memberships</button><button className="secondary" disabled={!selected.memberships_has_more} onClick={() => void inspect(selected, (selected.membership_offset || 0) + 50)}>Next memberships</button></div></>}
        {currentKind === 'community' && <div className="editor-panel"><h3>Assign Community Admin</h3><label>Find an existing user by email/username<input value={userQuery} onChange={event => setUserQuery(event.target.value)} /></label><button className="secondary" onClick={() => void searchUsers()}>Search users</button><label>User<select value={assignee} onChange={event => setAssignee(event.target.value)}><option value="">Select a user</option>{users.filter(item => !item.suspended).map(item => <option key={item.id} value={item.id}>{item.name} — {item.email}</option>)}</select></label><button disabled={!assignee} onClick={() => setPending({ title: `Assign ${users.find(item => item.id === assignee)?.name} as Admin`, consequence: `Grants active administrator authority in ${selected.name}. The platform role does not change.`, path: `${base}/community/${selected.id}/administrators`, body: { user_id: assignee } })}>Assign Community Admin</button></div>}
        <button className="secondary" onClick={() => { changeSection('history'); setHistoryTarget(selected.id); }}>View moderation and membership history</button><button className="secondary" onClick={() => setSelected(null)}>Close inspection</button>
      </section>}
    </>}
    {section === 'history' && <div className="definition-list">{!loading && !history.length && <p>No governance history on this page.</p>}{history.map(item => <article className="card" key={item.id}><h2>{item.action}</h2><p>{item.actor} · {item.community || 'Platform'} · {item.target_type}: {item.target_name}</p><p>{item.reason || 'Legacy action without reason'}</p><time>{new Date(item.occurred_at).toLocaleString()}</time>{item.result && <p>Result: {Object.entries(item.result).map(([key, value]) => `${key.replaceAll('_', ' ')}: ${String(value)}`).join(', ')}</p>}</article>)}</div>}
    {['users', 'communities', 'content', 'history'].includes(section) && <div className="form-actions"><button className="secondary" disabled={!offset || loading} onClick={() => setOffset(Math.max(0, offset - 50))}>Previous</button><button className="secondary" disabled={loading || (section === 'history' ? history : items).length < 50} onClick={() => setOffset(offset + 50)}>Next</button></div>}
    {pending && <GovernanceConfirm title={pending.title} consequence={pending.consequence} onClose={() => setPending(null)} onConfirm={async reason => { await apiJson(pending.path, { method: pending.method || 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...pending.body, reason }) }, live()); setMessage('Governance action recorded.'); await load(); if (selected) await inspect(selected); }} />}
  </section>;
}
