import { useEffect, useState } from 'react';
import { OrganizerAttendanceConfig } from './OrganizerAttendanceConfig';

type Event = { id: string; community_id: string; title: string; description: string; status: string; starts_at: string; ends_at: string; category: string; venue?: { name: string; city?: string } | null };
type Community = { id: string; community: { name: string } };

const emptyForm = { title: '', description: '', category: 'community', starts_at: '', ends_at: '', online_url: 'https://example.test/event' };

export function OrganizerEvents({ token }: { token: string }) {
  const [events, setEvents] = useState<Event[]>([]);
  const [communities, setCommunities] = useState<Community[]>([]);
  const [form, setForm] = useState(emptyForm);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState(''); const [configEvent, setConfigEvent] = useState<Event | null>(null);
  const headers = { Authorization: `Bearer ${token}` };
  const load = async () => {
    setLoading(true); setError('');
    try {
      const response = await fetch('/api/v1/communities/organizer/events', { headers });
      if (!response.ok) throw Error(response.status === 403 ? 'Organizer access required' : 'Unable to load events');
      setEvents(await response.json());
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to load events'); }
    finally { setLoading(false); }
  };
  useEffect(() => {
    load();
    fetch('/api/v1/communities/me', { headers }).then(response => response.ok ? response.json() : []).then(setCommunities).catch(() => setCommunities([]));
  }, [token]);
  const create = async (event: React.FormEvent) => {
    event.preventDefault();
    const community = communities[0];
    if (!community) { setError('Join an active community before creating an event.'); return; }
    setCreating(true); setError(''); setMessage('');
    try {
      const response = await fetch('/api/v1/events', { method: 'POST', headers: { ...headers, 'Content-Type': 'application/json' }, body: JSON.stringify({
        ...form, community_id: community.id, starts_at: new Date(form.starts_at).toISOString(), ends_at: new Date(form.ends_at).toISOString(), location_type: 'online',
      }) });
      const data = await response.json();
      if (!response.ok) throw Error(data.detail?.[0]?.msg || data.detail || 'Unable to create event');
      setMessage(`Created ${data.title}.`); setForm(emptyForm); await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to create event'); }
    finally { setCreating(false); }
  };
  return <section aria-labelledby="organizer-events-title"><p className="eyebrow">Operations</p><h2 id="organizer-events-title">Events</h2>
    <form className="panel" onSubmit={create}><h3>Create event</h3><label>Title<input required minLength={3} value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} /></label><label>Description<textarea required minLength={10} value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} /></label><label>Start<input required type="datetime-local" value={form.starts_at} onChange={e => setForm({ ...form, starts_at: e.target.value })} /></label><label>End<input required type="datetime-local" value={form.ends_at} onChange={e => setForm({ ...form, ends_at: e.target.value })} /></label><label>Online URL<input required type="url" value={form.online_url} onChange={e => setForm({ ...form, online_url: e.target.value })} /></label><button disabled={creating}>{creating ? 'Creating…' : 'Create event'}</button></form>
    {message && <p role="status">{message}</p>}{loading && <p role="status">Loading events…</p>}{error && <p role="alert" className="error">{error} <button className="link" onClick={load}>Retry</button></p>}{!loading && !error && !events.length && <p className="empty">No events to manage.</p>}<div className="grid">{events.map(event => <article className="panel card" key={event.id}><h3>{event.title}</h3><p>Status: {event.status}</p><time>{new Date(event.starts_at).toLocaleString()} – {new Date(event.ends_at).toLocaleString()}</time><p>{event.venue?.name || 'Online event'}{event.venue?.city ? `, ${event.venue.city}` : ''}</p><button onClick={() => setConfigEvent(event)}>Attendance settings</button></article>)}</div>{configEvent && <OrganizerAttendanceConfig token={token} communityId={configEvent.community_id} eventId={configEvent.id}/>}</section>;
}
