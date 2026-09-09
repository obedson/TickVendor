import { useEffect, useState } from 'react';
import { OrganizerAttendanceConfig } from './OrganizerAttendanceConfig';
import { apiJson, ApiError, apiFetch } from './api';
import { EmptyState } from './AppShell';

type Event = {
  id: string;
  community_id: string;
  title: string;
  description: string;
  status: string;
  starts_at: string;
  ends_at: string;
  category: string;
  online_url?: string | null;
  venue?: {
    name: string;
    address: string;
    city?: string | null;
    region?: string | null;
  } | null;
};
type Community = { id: string; community: { name: string } };
type TicketType = { id: string; name: string; price: string; currency: string; quantity: number; visibility: string; availability: number };

const emptyForm = {
  title: '',
  description: '',
  category: 'community',
  starts_at: '',
  ends_at: '',
  online_url: '',
  venue_name: '',
  venue_address: '',
  venue_city: '',
  venue_region: '',
};

const STATUS_COLORS: Record<string, string> = {
  draft: 'chip-default',
  published: 'chip-green',
  cancelled: 'chip-red',
  completed: 'chip-blue',
};

export function OrganizerEvents({ token, communityId }: { token: string; communityId?: string }) {
  const [events, setEvents] = useState<Event[]>([]);
  const [communities, setCommunities] = useState<Community[]>([]);
  const [form, setForm] = useState(emptyForm);
  const [editing, setEditing] = useState<Event | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [types, setTypes] = useState<TicketType[]>([]);
  const [configEvent, setConfigEvent] = useState<Event | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const headers = { Authorization: `Bearer ${token}` };

  const load = async () => {
    setLoading(true); setError('');
    try { setEvents(await apiJson<Event[]>('communities/organizer/events', {}, token)); }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : 'Unable to load events'); }
    finally { setLoading(false); }
  };

  useEffect(() => {
    load();
    apiFetch('communities/me', { headers })
      .then(r => r.ok ? r.json() : [])
      .then(setCommunities)
      .catch(() => setCommunities([]));
  }, [token]);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    const community = communities.find(item => item.id === communityId) || communities[0];
    if (!community) { setError('Join an active community before creating an event.'); return; }
    setSaving(true); setError(''); setMessage('');
    try {
      const response = await apiFetch('events', {
        method: 'POST',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({
  title: form.title,
  description: form.description,
  category: form.category,
  community_id: community.id,
  starts_at: new Date(form.starts_at).toISOString(),
  ends_at: new Date(form.ends_at).toISOString(),
  location_type: form.online_url ? 'online' : 'physical',
  ...(form.online_url
    ? { online_url: form.online_url }
    : {
        venue: {
          name: form.venue_name,
          address: form.venue_address,
          ...(form.venue_city ? { city: form.venue_city } : {}),
          ...(form.venue_region ? { region: form.venue_region } : {}),
          country_code: 'NG',
        },
      }),
}),
      });
      const data = await response.json();
      if (!response.ok) throw Error(data.detail?.[0]?.msg || data.detail || 'Unable to create event');
      setMessage(`Event "${data.title}" created.`);
      setForm(emptyForm);
      setShowForm(false);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to create event');
    } finally { setSaving(false); }
  };

  const update = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editing) return;
    setSaving(true); setError('');
    try {
      const response = await apiFetch(`events/${editing.id}`, {
        method: 'PATCH',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: form.title,
          description: form.description,
          starts_at: new Date(form.starts_at).toISOString(),
          ends_at: new Date(form.ends_at).toISOString(),
        }),
      });
      const data = await response.json();
      if (!response.ok) throw Error(data.detail || 'Unable to update event');
      setMessage(`Event "${data.title}" updated.`);
      setEditing(null);
      setShowForm(false);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to update event');
    } finally { setSaving(false); }
  };

  const publish = async (event: Event) => {
    setError('');
    const response = await apiFetch(`events/${event.id}/publish`, { method: 'POST', headers });
    if (!response.ok) { const data = await response.json(); setError(data.detail || 'Unable to publish event'); return; }
    setMessage(`"${event.title}" is now published.`);
    await load();
  };

  const loadTypes = async (event: Event) => {
    const response = await apiFetch(`events/${event.id}/ticket-types`, { headers });
    if (!response.ok) { setError('Unable to load ticket types'); return; }
    setTypes(await response.json());
  };

  const beginEdit = (event: Event) => {
    setEditing(event);
setForm({
  title: event.title,
  description: event.description,
  category: event.category,
  starts_at: event.starts_at.slice(0, 16),
  ends_at: event.ends_at.slice(0, 16),
  online_url: event.online_url ?? '',
  venue_name: event.venue?.name ?? '',
  venue_address: event.venue?.address ?? '',
  venue_city: event.venue?.city ?? '',
  venue_region: event.venue?.region ?? '',
});
    setShowForm(true);
    setConfigEvent(null);
  };

  const cancelForm = () => { setEditing(null); setShowForm(false); setForm(emptyForm); setError(''); };

  return (
    <div>
      <div className="page-header">
        <div className="page-header-text">
          <p className="eyebrow">Operations</p>
          <h1>Events</h1>
          <p>Create and manage events for your community.</p>
        </div>
        <div className="page-header-actions">
          {!showForm && (
            <button className="accent" onClick={() => { setShowForm(true); setEditing(null); setForm(emptyForm); }}>
              + Create event
            </button>
          )}
        </div>
      </div>

      {message && <p role="status" className="success-msg" style={{ marginBottom: '1rem' }}>{message}</p>}
      {error && <p role="alert" className="error" style={{ marginBottom: '1rem' }}>{error} <button className="link" onClick={load}>Retry</button></p>}

      {/* Create/Edit form */}
      {showForm && (
        <div className="panel" style={{ marginBottom: '1.5rem' }}>
          <h2 style={{ fontSize: '1.1rem', marginBottom: '1.25rem' }}>{editing ? `Edit: ${editing.title}` : 'Create new event'}</h2>
          <form onSubmit={editing ? update : create}>
            <label>
              <span className="label-text">Event title</span>
              <input required minLength={3} value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="e.g. Community Volunteer Day" />
            </label>
            <label>
              <span className="label-text">Description</span>
              <textarea required minLength={10} value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} rows={4} placeholder="Describe the event, what participants can expect…" />
            </label>
            <div className="form-row">
              <label>
                <span className="label-text">Start date &amp; time</span>
                <input required type="datetime-local" value={form.starts_at} onChange={e => setForm({ ...form, starts_at: e.target.value })} />
              </label>
              <label>
                <span className="label-text">End date &amp; time</span>
                <input required type="datetime-local" value={form.ends_at} onChange={e => setForm({ ...form, ends_at: e.target.value })} />
              </label>
            </div>
            {!editing && (
  <>
    <label>
      <span className="label-text">Online URL (leave blank for in-person)</span>
      <input
        type="url"
        value={form.online_url}
        onChange={e => setForm({ ...form, online_url: e.target.value })}
        placeholder="https://meet.example.com/event"
      />
    </label>

    {!form.online_url && (
      <>
        <label>
          <span className="label-text">Venue name</span>
          <input
            required
            value={form.venue_name}
            onChange={e => setForm({ ...form, venue_name: e.target.value })}
            placeholder="e.g. Cafe One Enugu"
          />
        </label>

        <label>
          <span className="label-text">Venue address</span>
          <input
            required
            value={form.venue_address}
            onChange={e => setForm({ ...form, venue_address: e.target.value })}
            placeholder="Street address"
          />
        </label>

        <div className="form-row">
          <label>
            <span className="label-text">City</span>
            <input
              value={form.venue_city}
              onChange={e => setForm({ ...form, venue_city: e.target.value })}
              placeholder="e.g. Enugu"
            />
          </label>

          <label>
            <span className="label-text">State / Region</span>
            <input
              value={form.venue_region}
              onChange={e => setForm({ ...form, venue_region: e.target.value })}
              placeholder="e.g. Enugu"
            />
          </label>
        </div>
      </>
    )}
  </>
)}
            <div className="form-actions">
              <button type="submit" className="accent" disabled={saving}>
                {saving ? 'Saving…' : editing ? 'Save changes' : 'Create event'}
              </button>
              <button type="button" className="secondary" onClick={cancelForm}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      {loading && <p role="status" className="text-muted">Loading events…</p>}
      {!loading && !error && !events.length && (
        <EmptyState
          title="No events yet"
          description="Create your first event to start managing attendance and ticket sales."
          action="Create event"
          onAction={() => setShowForm(true)}
        />
      )}

      <div className="stack">
        {events.map(event => (
          <article key={event.id} className="card" style={{ display: 'grid', gap: '.75rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', flexWrap: 'wrap' }}>
              <div>
                <h3 style={{ margin: '0 0 .35rem' }}>{event.title}</h3>
                <div style={{ display: 'flex', gap: '.5rem', flexWrap: 'wrap' }}>
                  <span className={`chip ${STATUS_COLORS[event.status] || 'chip-default'}`}>{event.status}</span>
                  <span className="chip chip-default">{event.category}</span>
                </div>
              </div>
              <div style={{ display: 'flex', gap: '.5rem', flexWrap: 'wrap', flexShrink: 0 }}>
                <button className="secondary sm" onClick={() => beginEdit(event)}>Edit</button>
                {event.status === 'draft' && (
                  <button className="accent sm" onClick={() => publish(event)}>Publish</button>
                )}
                <button className="secondary sm" onClick={() => { setConfigEvent(configEvent?.id === event.id ? null : event); loadTypes(event); }}>
                  {configEvent?.id === event.id ? 'Close config' : 'Configure'}
                </button>
              </div>
            </div>
            <div style={{ display: 'flex', gap: '1.5rem', fontSize: '.875rem', color: 'var(--tv-muted)', flexWrap: 'wrap' }}>
              <span>📅 {new Date(event.starts_at).toLocaleString()} – {new Date(event.ends_at).toLocaleString()}</span>
              <span>📍 {event.venue?.name || 'Online'}{event.venue?.city ? `, ${event.venue.city}` : ''}</span>
            </div>

            {/* Inline config panel */}
            {configEvent?.id === event.id && (
              <div style={{ borderTop: '1px solid var(--tv-border)', paddingTop: '1rem', display: 'grid', gap: '1rem' }}>
                <OrganizerAttendanceConfig token={token} communityId={event.community_id} eventId={event.id} />
                <div>
                  <h4 style={{ marginBottom: '.75rem' }}>Ticket types</h4>
                  {!types.length ? (
                    <p className="empty">No ticket types configured for this event.</p>
                  ) : (
                    <div className="stack">
                      {types.map(type => (
                        <div key={type.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '.65rem .85rem', background: 'var(--tv-surface-sunken)', borderRadius: 'var(--tv-radius-md)', fontSize: '.875rem', gap: '.5rem', flexWrap: 'wrap' }}>
                          <strong>{type.name}</strong>
                          <div style={{ display: 'flex', gap: '.5rem', alignItems: 'center' }}>
                            <span>{Number(type.price) === 0 ? 'Free' : `${type.currency} ${type.price}`}</span>
                            <span className={`chip ${type.availability > 0 ? 'chip-green' : 'chip-red'}`}>{type.availability} left</span>
                            <span className="chip chip-default">{type.visibility}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </article>
        ))}
      </div>
    </div>
  );
}
