import { useEffect, useState } from 'react';
import { apiJson, ApiError } from './api';

type Opportunity = { id: string; community_id: string; title: string; description: string; activity_type: string; dimension: string; starts_at: string; ends_at: string; location?: string | null; capacity?: number | null; members_only: boolean; status: string };

export function Opportunities({ token }: { token: string }) {
  const [items, setItems] = useState<Opportunity[]>([]);
  const [selected, setSelected] = useState<Opportunity | null>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  useEffect(() => { apiJson<Opportunity[]>('activity-opportunities', {}, token).then(setItems).catch(cause => setError(cause instanceof ApiError ? cause.message : 'Unable to load opportunities.')); }, [token]);
  const join = async () => { if (!selected) return; setError(''); setMessage(''); try { await apiJson(`activity-opportunities/${selected.id}/join`, { method: 'POST' }, token); setMessage('You are registered for this opportunity.'); } catch (cause) { setError(cause instanceof ApiError ? cause.message : 'Unable to register.'); } };
  if (selected) return <section className="panel" aria-labelledby="opportunity-title"><button className="link" onClick={() => setSelected(null)}>Back to Discover</button><p className="eyebrow">{selected.activity_type} · {selected.dimension}</p><h2 id="opportunity-title">{selected.title}</h2><p>{selected.description}</p><p><strong>{new Date(selected.starts_at).toLocaleString()}</strong> – {new Date(selected.ends_at).toLocaleString()}</p>{selected.location && <p>Location: {selected.location}</p>}{selected.capacity && <p>Capacity: {selected.capacity}</p>}{error && <p role="alert" className="error">{error}</p>}{message && <p role="status">{message}</p>}<button onClick={join} disabled={!!message}>Join opportunity</button></section>;
  return <section className="panel" aria-labelledby="opportunities-title"><p className="eyebrow">Discover</p><h2 id="opportunities-title">Community opportunities</h2><p>Find ways to participate with your communities.</p>{error && <p role="alert" className="error">{error}</p>}{!error && !items.length && <p className="empty">No community opportunities are open right now.</p>}<div className="grid">{items.map(item => <article className="card panel" key={item.id}><p className="eyebrow">{item.activity_type}</p><h3>{item.title}</h3><p>{item.description}</p><time>{new Date(item.starts_at).toLocaleString()}</time>{item.location && <p>{item.location}</p>}<button onClick={() => setSelected(item)}>View opportunity</button></article>)}</div></section>;
}
