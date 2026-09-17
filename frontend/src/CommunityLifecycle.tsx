import { CommunityMember } from './CommunityMember';
import { CreateCommunity } from './CreateCommunity';
import { SponsoredPlacement } from './SponsoredPlacement';
import { useEffect, useState } from 'react';
import { apiJson, getLiveToken } from './api';
import { GovernanceConfirm } from './GovernanceConfirm';

type Community = { id: string; name: string; description?: string; logo_url?: string; is_active: boolean; is_public: boolean; membership_access: 'open' | 'approval_required' | 'invite_only' };
type Membership = { id: string; role: string; status: string };
type Mine = { id: string; community: Community; membership: Membership };
type Found = Community & { membership?: Membership | null };
export function CommunityLifecycle({ token, isSuperAdmin = false }: { token: string; isSuperAdmin?: boolean }) {
  const [opened, setOpened] = useState<Community | null>(null);
  const [creating, setCreating] = useState(false);
  const [message, setMessage] = useState('');
  const [mine, setMine] = useState<Mine[]>([]);
  const [found, setFound] = useState<Found[]>([]);
  const [view, setView] = useState('active');
  const [query, setQuery] = useState('');
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState('');
  const [pending, setPending] = useState<{ item: Community; action: string } | null>(null);
  const live = () => getLiveToken() ?? token;
  // Membership buttons are disabled globally while any transition is in flight, but only the clicked
  // one reports progress, so a slow join is visibly working instead of looking like a dead button.
  const working = (id: string, action: string) => busy === `${id}:${action}`;
  const load = async () => {
    setLoading(true); setError('');
    try { const [memberships, discover] = await Promise.all([apiJson<Mine[]>('communities/me', {}, live()), apiJson<Found[]>(`communities/discover?q=${encodeURIComponent(query)}&offset=${offset}`, {}, live())]); setMine(memberships); setFound(discover); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to load communities.'); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, [token, offset]);
  const act = async (item: Community, action: string) => {
    setBusy(`${item.id}:${action}`); setMessage('');
    try { const membership = await apiJson<Membership>(`communities/${item.id}/membership/${action}`, { method: 'POST' }, live());
      setMine(rows => [...rows.filter(row => row.id !== item.id), { id: item.id, community: item, membership }]);
      setFound(rows => rows.map(row => row.id === item.id ? { ...row, membership } : row));
      setMessage(membership.status === 'active' ? `${item.name}: you are now an active member. Open the member space to see its tasks and opportunities.`
        : membership.status === 'pending' ? `${item.name}: your request is pending a community administrator's approval. You are not a member yet.`
        : `${item.name}: membership is now ${membership.status}.`);
      setError('');
      window.dispatchEvent(new Event('tickvendor-memberships-changed'));
    }
    finally { setBusy(''); }
  };
  const direct = (item: Community, action: string) => { void act(item, action).catch(cause => setError(cause instanceof Error ? cause.message : 'Membership action failed.')); };
  const rows: Found[] = view === 'discover' ? found : mine.filter(item => view === 'past' ? ['left', 'declined', 'suspended'].includes(item.membership.status) : item.membership.status === view).map(item => ({ ...item.community, membership: item.membership }));
  if (opened) return <CommunityMember token={token} community={opened} onClose={() => setOpened(null)} />;
  return <section className="management-screen"><h1>Communities</h1><p>Find your community, manage invitations and keep your participation history.</p>
    {(isSuperAdmin || mine.some(item => item.membership.role === 'admin' && item.membership.status === 'active' && item.community.is_active)) && <button onClick={() => setCreating(true)}>Create community</button>}
    {message && <p role="status">{message}</p>}
    <SponsoredPlacement surface="communities" />
    <nav className="section-tabs" aria-label="Community views">{[['active', 'My Communities'], ['discover', 'Discover Communities'], ['pending', 'Pending Requests'], ['invited', 'Invitations'], ['past', 'Past Memberships']].map(([id, label]) => <button className="secondary" aria-pressed={view === id} key={id} onClick={() => setView(id)}>{label}</button>)}</nav>
    {view === 'discover' && <form onSubmit={event => { event.preventDefault(); if (offset) setOffset(0); else void load(); }}><label>Search communities<input value={query} onChange={event => setQuery(event.target.value)} /></label><button disabled={loading}>Search</button></form>}
    {error && <p role="alert" className="error">{error}</p>}{loading && <p role="status">Loading communities…</p>}
    <div className="grid">{rows.map(item => <article className="card" key={item.id}>
      {item.logo_url && <img src={item.logo_url} width="48" height="48" alt="" />}<h2>{item.name}</h2><p>{item.description}</p><p>{item.membership_access.replaceAll('_', ' ')} membership · {item.is_public ? 'Public' : 'Private'}</p>
      {item.membership && <p><span className="chip">{item.membership.role}</span> <span className="chip">{item.membership.status}</span></p>}
      {!item.is_active ? <p>Community suspended. Your history is retained.</p> : <div className="form-actions">
        {(!item.membership || ['left', 'declined'].includes(item.membership.status)) && (item.membership_access === 'invite_only' ? <p>An invitation is required.</p> : <button disabled={!!busy} onClick={() => direct(item, 'join')}>{working(item.id, 'join') ? (item.membership_access === 'open' ? 'Joining…' : 'Sending request…') : item.membership_access === 'open' ? 'Join Community' : 'Request to Join'}</button>)}
        {item.membership?.status === 'invited' && <><button disabled={!!busy} onClick={() => direct(item, 'accept')}>{working(item.id, 'accept') ? 'Accepting…' : 'Accept invitation'}</button><button className="secondary" disabled={!!busy} onClick={() => direct(item, 'decline')}>{working(item.id, 'decline') ? 'Declining…' : 'Decline invitation'}</button></>}
      </div>}
      {item.membership?.status === 'pending' && <><p>Awaiting administrator approval — you are not a member yet.</p><button className="secondary" disabled={!!busy} onClick={() => direct(item, 'withdraw')}>{working(item.id, 'withdraw') ? 'Withdrawing…' : 'Withdraw request'}</button></>}
      {item.membership?.status === 'active' && item.is_active && <button onClick={() => setOpened(item)}>Open member space</button>}
      {item.membership?.status === 'active' && (item.membership.role === 'admin' ? <p>A Super Admin must change your administrator role before you can leave.</p> : <button className="secondary" disabled={!!busy} onClick={() => setPending({ item, action: 'leave' })}>Leave Community</button>)}
    </article>)}</div>{!loading && !rows.length && <p>No communities in this view.</p>}
    {view === 'discover' && <div className="form-actions"><button className="secondary" disabled={!offset} onClick={() => setOffset(offset - 50)}>Previous</button><button className="secondary" disabled={found.length < 50} onClick={() => setOffset(offset + 50)}>Next</button></div>}
    {creating && <CreateCommunity token={token} onClose={() => setCreating(false)} onCreated={() => { void load(); window.dispatchEvent(new Event('tickvendor-memberships-changed')); }} />}
    {pending && <GovernanceConfirm title={`Leave ${pending.item.name}`} consequence="Community access will end. Tickets, attendance, Impact Points and recognition history remain." requireReason={false} onClose={() => setPending(null)} onConfirm={() => act(pending.item, pending.action)} />}
  </section>;
}
