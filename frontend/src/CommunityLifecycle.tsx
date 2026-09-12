import { useEffect, useState } from 'react';
import { apiJson, getLiveToken } from './api';
import { GovernanceConfirm } from './GovernanceConfirm';

type Community = { id: string; name: string; description?: string; logo_url?: string; is_active: boolean; is_public: boolean; membership_access: 'open' | 'approval_required' | 'invite_only' };
type Membership = { id: string; role: string; status: string };
type Mine = { id: string; community: Community; membership: Membership };
type Found = Community & { membership?: Membership | null };
export function CommunityLifecycle({ token }: { token: string }) {
  const [mine, setMine] = useState<Mine[]>([]);
  const [found, setFound] = useState<Found[]>([]);
  const [view, setView] = useState('active');
  const [query, setQuery] = useState('');
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<{ item: Community; action: string } | null>(null);
  const live = () => getLiveToken() ?? token;
  const load = async () => {
    setLoading(true); setError('');
    try { const [memberships, discover] = await Promise.all([apiJson<Mine[]>('communities/me', {}, live()), apiJson<Found[]>(`communities/discover?q=${encodeURIComponent(query)}&offset=${offset}`, {}, live())]); setMine(memberships); setFound(discover); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to load communities.'); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, [token, offset]);
  const act = async (item: Community, action: string) => {
    setBusy(true);
    try { await apiJson(`communities/${item.id}/membership/${action}`, { method: 'POST' }, live()); await load(); window.dispatchEvent(new Event('tickvendor-memberships-changed')); }
    finally { setBusy(false); }
  };
  const direct = (item: Community, action: string) => { void act(item, action).catch(cause => setError(cause instanceof Error ? cause.message : 'Membership action failed.')); };
  const rows: Found[] = view === 'discover' ? found : mine.filter(item => view === 'past' ? ['left', 'declined', 'suspended'].includes(item.membership.status) : item.membership.status === view).map(item => ({ ...item.community, membership: item.membership }));
  return <section className="management-screen"><h1>Communities</h1><p>Find your community, manage invitations and keep your participation history.</p>
    <nav className="section-tabs" aria-label="Community views">{[['active', 'My Communities'], ['discover', 'Discover Communities'], ['pending', 'Pending Requests'], ['invited', 'Invitations'], ['past', 'Past Memberships']].map(([id, label]) => <button className="secondary" aria-pressed={view === id} key={id} onClick={() => setView(id)}>{label}</button>)}</nav>
    {view === 'discover' && <form onSubmit={event => { event.preventDefault(); if (offset) setOffset(0); else void load(); }}><label>Search communities<input value={query} onChange={event => setQuery(event.target.value)} /></label><button disabled={loading}>Search</button></form>}
    {error && <p role="alert" className="error">{error}</p>}{loading && <p role="status">Loading communities…</p>}
    <div className="grid">{rows.map(item => <article className="card" key={item.id}>
      {item.logo_url && <img src={item.logo_url} width="48" height="48" alt="" />}<h2>{item.name}</h2><p>{item.description}</p><p>{item.membership_access.replaceAll('_', ' ')} membership · {item.is_public ? 'Public' : 'Private'}</p>
      {item.membership && <p><span className="chip">{item.membership.role}</span> <span className="chip">{item.membership.status}</span></p>}
      {!item.is_active ? <p>Community suspended. Your history is retained.</p> : <div className="form-actions">
        {(!item.membership || ['left', 'declined'].includes(item.membership.status)) && (item.membership_access === 'invite_only' ? <p>An invitation is required.</p> : <button disabled={busy} onClick={() => direct(item, 'join')}>{item.membership_access === 'open' ? 'Join Community' : 'Request to Join'}</button>)}
        {item.membership?.status === 'invited' && <><button disabled={busy} onClick={() => direct(item, 'accept')}>Accept invitation</button><button className="secondary" disabled={busy} onClick={() => direct(item, 'decline')}>Decline invitation</button></>}
      </div>}
      {item.membership?.status === 'pending' && <button className="secondary" disabled={busy} onClick={() => direct(item, 'withdraw')}>Withdraw request</button>}
      {item.membership?.status === 'active' && (item.membership.role === 'admin' ? <p>A Super Admin must change your administrator role before you can leave.</p> : <button className="secondary" disabled={busy} onClick={() => setPending({ item, action: 'leave' })}>Leave Community</button>)}
    </article>)}</div>{!loading && !rows.length && <p>No communities in this view.</p>}
    {view === 'discover' && <div className="form-actions"><button className="secondary" disabled={!offset} onClick={() => setOffset(offset - 50)}>Previous</button><button className="secondary" disabled={found.length < 50} onClick={() => setOffset(offset + 50)}>Next</button></div>}
    {pending && <GovernanceConfirm title={`Leave ${pending.item.name}`} consequence="Community access will end. Tickets, attendance, Impact Points and recognition history remain." requireReason={false} onClose={() => setPending(null)} onConfirm={() => act(pending.item, pending.action)} />}
  </section>;
}
