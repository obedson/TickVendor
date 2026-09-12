import { useEffect, useState, type ReactNode } from 'react';
import { apiJson, getLiveToken } from './api';

/** Choose explicitly from the existing authorized organizer listing. */
export function ManagedEventSelector({ token, communityId, children }: { token: string; communityId: string; children: (eventId: string) => ReactNode }) {
  const [events, setEvents] = useState<{ id: string; title: string; community_id: string }[]>([]);
  const [selected, setSelected] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let current = true;
    setSelected(''); setEvents([]); setError(''); setLoading(true);
    apiJson<typeof events>('communities/organizer/events', {}, getLiveToken() ?? token)
      .then(items => { if (current) setEvents(items.filter(item => item.community_id === communityId)); })
      .catch(cause => { if (current) setError(cause instanceof Error ? cause.message : 'Unable to load events.'); })
      .finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, [token, communityId]);
  return <><section className="panel management-screen"><label>Event<select value={selected} onChange={event => setSelected(event.target.value)} disabled={loading}><option value="">Select an event</option>{events.map(event => <option key={event.id} value={event.id}>{event.title}</option>)}</select></label>{error && <p role="alert" className="error">{error}</p>}{loading ? <p role="status">Loading events…</p> : !events.length && !error && <p>No events available in this community.</p>}</section>{selected && <div key={selected}>{children(selected)}</div>}</>;
}
