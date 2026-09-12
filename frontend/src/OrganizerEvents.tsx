import { useEffect, useState } from 'react';
import './management.css';
import { OrganizerAttendanceConfig } from './OrganizerAttendanceConfig';
import { apiJson, ApiError, getLiveToken } from './api';
import { EmptyState } from './AppShell';
import { EventCover } from './EventCover';
import { EventCoverEditor } from './EventCoverEditor';

type Event = {
  id: string;
  community_id: string;
  title: string;
  description: string;
  status: string;
  starts_at: string;
  ends_at: string;
  category: string;
  cover_image_url?: string | null;
  online_url?: string | null;
  venue?: {
    name: string;
    address: string;
    city?: string | null;
    region?: string | null;
  } | null;
};
type Community = { id: string; community?: { name: string }; name?: string };
type TicketType = { id: string; name: string; price: string; currency: string; quantity: number; visibility: string; availability: number };
type EventCategory = { id: string; slug: string; name: string; is_active: boolean };

const emptyForm = {
  title: '',
  description: '',
  category: '',
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

const emptyTicketForm = { name: '', description: '', price: '0', currency: 'NGN', quantity: '100', max_per_user: '1', visibility: 'public' };

export function OrganizerEvents({ token, communityId }: { token: string; communityId?: string }) {
  const [events, setEvents] = useState<Event[]>([]);
  const [communities, setCommunities] = useState<Community[]>([]);
  const [categories, setCategories] = useState<EventCategory[]>([]);
  const [form, setForm] = useState(emptyForm);
  const [editing, setEditing] = useState<Event | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [types, setTypes] = useState<TicketType[]>([]);
  const [ticketForm, setTicketForm] = useState(emptyTicketForm);
  const [showTicketForm, setShowTicketForm] = useState(false);
  const [savingTicket, setSavingTicket] = useState(false);
  const [configEvent, setConfigEvent] = useState<Event | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const liveToken = () => getLiveToken() ?? token;

  const load = async () => {
    setLoading(true); setError('');
    try { setEvents((await apiJson<Event[]>('communities/organizer/events', {}, liveToken())).filter(event => event.community_id === communityId)); }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : 'Unable to load events'); }
    finally { setLoading(false); }
  };

  const [categoriesLoading, setCategoriesLoading] = useState(true);
  const [categoriesError, setCategoriesError] = useState('');

  const loadCategories = () => {
    setCategoriesLoading(true);
    setCategoriesError('');
    // Use the public /events/categories endpoint (non-admin route per spec conventions).
    apiJson<EventCategory[]>('events/categories', {}, liveToken())
      .then(cats => {
        setCategories(cats);
        // Set default category to first active one if form is blank.
        setForm(prev => prev.category ? prev : { ...prev, category: cats[0]?.slug ?? '' });
      })
      .catch((e: Error) => setCategoriesError(e.message))
      .finally(() => setCategoriesLoading(false));
  };

  useEffect(() => {
    load();
    apiJson<Community[]>('communities/me', {}, liveToken())
      .then(setCommunities)
      .catch(() => setCommunities([]));
    loadCategories();
  }, [token, communityId]);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    const community = communities.find(item => item.id === communityId);
    if (!community) { setError('Join an active community before creating an event.'); return; }
    setSaving(true); setError(''); setMessage('');
    try {
      const data = await apiJson<Event>('events', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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
      }, liveToken());
      setMessage(`Event "${data.title}" created.`);
      setForm(emptyForm);
      setShowForm(false);
      await load();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : cause instanceof Error ? cause.message : 'Unable to create event');
    } finally { setSaving(false); }
  };

  const update = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editing) return;
    setSaving(true); setError('');
    try {
      const data = await apiJson<Event>(`events/${editing.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: form.title,
          description: form.description,
          starts_at: new Date(form.starts_at).toISOString(),
          ends_at: new Date(form.ends_at).toISOString(),
        }),
      }, liveToken());
      setMessage(`Event "${data.title}" updated.`);
      setEditing(null);
      setShowForm(false);
      await load();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : cause instanceof Error ? cause.message : 'Unable to update event');
    } finally { setSaving(false); }
  };

  const publish = async (event: Event) => {
    setError('');
    try {
      await apiJson<unknown>(`events/${event.id}/publish`, { method: 'POST' }, liveToken());
      setMessage(`"${event.title}" is now published.`);
      await load();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Unable to publish event');
    }
  };

  const loadTypes = async (event: Event) => {
    try {
      setTypes(await apiJson<TicketType[]>(`events/${event.id}/ticket-types`, {}, liveToken()));
    } catch { setError('Unable to load ticket types'); }
  };

  const createTicketType = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!configEvent) return;
    setSavingTicket(true); setError('');
    try {
      await apiJson<TicketType>(`events/${configEvent.id}/ticket-types`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: ticketForm.name,
          description: ticketForm.description || undefined,
          price: Number(ticketForm.price),
          currency: ticketForm.currency,
          quantity: Number(ticketForm.quantity),
          max_per_user: Number(ticketForm.max_per_user),
          visibility: ticketForm.visibility,
        }),
      }, liveToken());
      setMessage('Ticket type created.');
      setTicketForm(emptyTicketForm);
      setShowTicketForm(false);
      await loadTypes(configEvent);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Unable to create ticket type');
    } finally { setSavingTicket(false); }
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
    <div className="management-screen">
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
            <label>
              <span className="label-text">Event category</span>
              {categoriesLoading ? (
                <p role="status" className="text-muted text-sm" style={{ margin: '.25rem 0' }}>Loading categories…</p>
              ) : categoriesError ? (
                <p role="alert" className="error" style={{ margin: '.25rem 0' }}>
                  {categoriesError}{' '}
                  <button type="button" className="link" onClick={loadCategories}>Retry</button>
                </p>
              ) : categories.length === 0 ? (
                <p role="alert" className="error" style={{ margin: '.25rem 0' }}>
                  No active event categories are configured. A Platform Administrator must create at least one category before events can be created.
                </p>
              ) : (
                <select
                  required
                  value={form.category}
                  onChange={e => setForm({ ...form, category: e.target.value })}
                  disabled={categories.length === 0}
                >
                  <option value="" disabled>Select a category…</option>
                  {categories.map(cat => (
                    <option key={cat.slug} value={cat.slug}>{cat.name}</option>
                  ))}
                </select>
              )}
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
              <button type="submit" className="accent" disabled={saving || (!editing && (categoriesLoading || categories.length === 0))}>
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

            <EventCover url={event.cover_image_url} title={event.title} category={event.category} />
            <details><summary>Manage event cover</summary><EventCoverEditor eventId={event.id} token={liveToken()} hasCover={Boolean(event.cover_image_url)} onSaved={load} /></details>
            {/* Inline config panel */}
            {configEvent?.id === event.id && (
              <div style={{ borderTop: '1px solid var(--tv-border)', paddingTop: '1rem', display: 'grid', gap: '1.25rem' }}>
                <OrganizerAttendanceConfig token={token} communityId={event.community_id} eventId={event.id} />
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '.75rem' }}>
                    <h4 style={{ margin: 0 }}>Ticket types</h4>
                    <button className="accent sm" onClick={() => setShowTicketForm(!showTicketForm)}>
                      {showTicketForm ? 'Cancel' : '+ Add ticket type'}
                    </button>
                  </div>
                  {showTicketForm && (
                    <form onSubmit={createTicketType} style={{ background: 'var(--tv-surface-sunken)', padding: '1rem', borderRadius: 'var(--tv-radius-md)', marginBottom: '1rem', display: 'grid', gap: '.75rem' }}>
                      <div className="form-row">
                        <label>
                          <span className="label-text">Name</span>
                          <input required value={ticketForm.name} onChange={e => setTicketForm({ ...ticketForm, name: e.target.value })} placeholder="e.g. General Admission" />
                        </label>
                        <label>
                          <span className="label-text">Price (0 = Free)</span>
                          <input required type="number" min="0" step="0.01" value={ticketForm.price} onChange={e => setTicketForm({ ...ticketForm, price: e.target.value })} />
                        </label>
                      </div>
                      <label>
                        <span className="label-text">Description (optional)</span>
                        <input value={ticketForm.description} onChange={e => setTicketForm({ ...ticketForm, description: e.target.value })} placeholder="What's included…" />
                      </label>
                      <div className="form-row">
                        <label>
                          <span className="label-text">Quantity</span>
                          <input required type="number" min="1" value={ticketForm.quantity} onChange={e => setTicketForm({ ...ticketForm, quantity: e.target.value })} />
                        </label>
                        <label>
                          <span className="label-text">Max per user</span>
                          <input required type="number" min="1" value={ticketForm.max_per_user} onChange={e => setTicketForm({ ...ticketForm, max_per_user: e.target.value })} />
                        </label>
                        <label>
                          <span className="label-text">Visibility</span>
                          <select value={ticketForm.visibility} onChange={e => setTicketForm({ ...ticketForm, visibility: e.target.value })}>
                            <option value="public">Public</option>
                            <option value="hidden">Hidden (not listed publicly)</option>
                            <option value="invite_only">Invite only</option>
                          </select>
                        </label>
                      </div>
                      <div className="form-actions">
                        <button type="submit" className="accent sm" disabled={savingTicket}>{savingTicket ? 'Saving…' : 'Create ticket type'}</button>
                      </div>
                    </form>
                  )}
                  {!types.length ? (
                    <p className="empty">No ticket types configured for this event.</p>
                  ) : (
                    <div className="stack">
                      {types.map(type => (
                        <div key={type.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '.65rem .85rem', background: 'var(--tv-surface-sunken)', borderRadius: 'var(--tv-radius-md)', fontSize: '.875rem', gap: '.5rem', flexWrap: 'wrap' }}>
                          <strong>{type.name}</strong>
                          <div style={{ display: 'flex', gap: '.5rem', alignItems: 'center' }}>
                            <span>{Number(type.price) === 0 ? 'Free' : `${type.currency} ${Number(type.price).toLocaleString()}`}</span>
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
