import { useEffect, useState } from 'react';
import { apiJson, getLiveToken } from './api';

export type PersonalKind = 'ticket' | 'task' | 'opportunity' | 'notification';
type Preference = { item_type: PersonalKind; item_id: string };
type Item = { id: string; title: string; status: string; archived: boolean; eligible: boolean; created_at: string };
export function usePersonalArchive(token: string, kind: PersonalKind) {
  const [ids, setIds] = useState<Set<string>>(new Set());
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const change = () => setRevision(value => value + 1);
    window.addEventListener('tickvendor-archive-changed', change);
    return () => window.removeEventListener('tickvendor-archive-changed', change);
  }, []);
  useEffect(() => {
    let current = true;
    apiJson<Preference[]>('me/archive', {}, getLiveToken() ?? token).then(items => { if (current) { setIds(new Set(items.filter(item => item.item_type === kind).map(item => item.item_id))); setError(''); } }).catch(() => { if (current) setError('Archive preferences could not be loaded; showing available records.'); });
    return () => { current = false; };
  }, [token, kind, revision]);
  return { ids, error, revision };
}
export async function archiveItem(token: string, kind: PersonalKind, id: string, archived: boolean) {
  await apiJson(`me/archive/${kind}/${id}`, { method: archived ? 'POST' : 'DELETE' }, getLiveToken() ?? token);
  window.dispatchEvent(new Event('tickvendor-archive-changed'));
}
export function PersonalHistory({ token, kind, title }: { token: string; kind: PersonalKind; title: string }) {
  const [open, setOpen] = useState(false);
  const [view, setView] = useState('history');
  const [offset, setOffset] = useState(0);
  const [items, setItems] = useState<Item[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const { revision } = usePersonalArchive(token, kind);
  useEffect(() => {
    if (!open) return;
    let current = true;
    apiJson<Item[]>(`me/personal-items/${kind}?offset=${offset}`, {}, getLiveToken() ?? token).then(data => { if (current) { setItems(data); setError(''); } }).catch(cause => { if (current) setError(cause.message); });
    return () => { current = false; };
  }, [token, kind, open, offset, revision]);
  const visible = items.filter(item => view === 'archived' ? item.archived : view === 'current' ? !item.archived && !item.eligible : !item.archived && item.eligible);
  return <details className="panel" onToggle={event => setOpen(event.currentTarget.open)}><summary>{title}</summary><p>Archive changes only your personal view. Evidence and community statistics are retained.</p>
    <nav className="section-tabs" aria-label={`${kind} history filters`}>{[['current', kind === 'opportunity' ? 'My Registrations' : 'Current'], ['history', 'History'], ['archived', 'Archived']].map(([id, label]) => <button key={id} className="secondary" aria-pressed={view === id} onClick={() => setView(id)}>{label}</button>)}</nav>
    {error && <p role="alert" className="error">{error}</p>}<div className="definition-list">{visible.map(item => <article className="definition-card" key={item.id}><div><h3>{item.title}</h3><p>{item.status} · {new Date(item.created_at).toLocaleDateString()}</p></div>{(item.eligible || item.archived) && <button disabled={busy} className="secondary" onClick={async () => { setBusy(true); try { await archiveItem(token, kind, item.id, !item.archived); } catch (cause) { setError(cause instanceof Error ? cause.message : 'Archive action failed.'); } finally { setBusy(false); } }}>{item.archived ? 'Restore to My Space' : 'Archive'}</button>}</article>)}</div>{!visible.length && <p>No records in this view on this page.</p>}
    <div className="form-actions"><button className="secondary" disabled={!offset} onClick={() => setOffset(offset - 50)}>Previous records</button><button className="secondary" disabled={items.length < 50} onClick={() => setOffset(offset + 50)}>Next records</button></div>
  </details>;
}
