import { useDraftState } from './formRecovery';
import { GovernanceConfirm } from './GovernanceConfirm';
import { NigeriaLocation } from './NigeriaLocation';
import { useRevealFocus } from './RevealFocus';
import { useEffect, useState } from 'react';
import './management.css';
import { OrganizerAttendanceConfig } from './OrganizerAttendanceConfig';
import { OrganizerEntitlements } from './OrganizerEntitlements';
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
    lga?: string | null; country_code?: string; latitude?: number | null; longitude?: number | null;
  } | null;
};
type Community = { id: string; community?: { name: string }; name?: string };
type TicketType = {
  id: string; name: string; description?: string | null; price: string; currency: string;
  quantity: number; visibility: string; availability: number; sold?: number;
  max_per_user: number; max_per_order: number;
  sales_start?: string | null; sales_end?: string | null;
};
type EventCategory = { id: string; slug: string; name: string; is_active: boolean };

function localInput(value: string) { const date = new Date(value); return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16); }

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
  venue_region: '', venue_lga: '', venue_latitude: '', venue_longitude: '',
};

const STATUS_COLORS: Record<string, string> = {
  draft: 'chip-default',
  published: 'chip-green',
  cancelled: 'chip-red',
  completed: 'chip-blue',
};

const emptyTicketForm = { name: '', description: '', price: '0', currency: 'NGN', quantity: '100', max_per_user: '1', max_per_order: '4', visibility: 'public', sales_start: '', sales_end: '' };

/**
 * A ticket type's maintainable fields, minus `event_id`: a type never moves between events.
 *
 * `locked` omits price and currency rather than resending them. The backend reads a field that is
 * present in the payload as a claim about that field, so restating an unchanged price on a type
 * that has already sold would be refused as an attempt to change it. Omitting the two says the
 * only true thing: this edit is not about them.
 */
function ticketTypePayload(form: typeof emptyTicketForm, locked = false) {
  const starts = form.sales_start ? new Date(form.sales_start) : null;
  const ends = form.sales_end ? new Date(form.sales_end) : null;
  if (starts && ends && ends <= starts) throw new Error('Sales must end after they start.');
  return {
    name: form.name.trim(),
    description: form.description.trim() || null,
    ...(locked ? {} : { price: Number(form.price), currency: form.currency }),
    quantity: Number(form.quantity),
    max_per_user: Number(form.max_per_user),
    max_per_order: Number(form.max_per_order),
    visibility: form.visibility,
    sales_start: starts ? starts.toISOString() : null,
    sales_end: ends ? ends.toISOString() : null,
  };
}

/**
 * The editable surface of a ticket type, shared by the create and edit forms so the two can
 * never drift apart.
 *
 * `lockPrice` reflects the backend's own rule: the price and currency a buyer already paid are
 * snapshotted on the order, so once tickets are issued those two fields stop being maintainable
 * and a new price belongs on a new ticket type.
 */
function TicketTypeFields({ form, setForm, lockPrice = false }: {
  form: typeof emptyTicketForm;
  setForm: (next: typeof emptyTicketForm) => void;
  lockPrice?: boolean;
}) {
  return (
    <>
      <div className="form-row">
        <label>
          <span className="label-text">Name</span>
          <input required value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="e.g. General Admission" />
        </label>
        <label>
          <span className="label-text">Price (0 = Free)</span>
          <input required type="number" min="0" step="0.01" value={form.price} disabled={lockPrice} onChange={e => setForm({ ...form, price: e.target.value })} />
        </label>
      </div>
      {lockPrice && <p className="text-sm text-muted">Price and currency are fixed once tickets have been sold. Create a new ticket type for a new price.</p>}
      <label>
        <span className="label-text">Description (optional)</span>
        <input value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} placeholder="What's included…" />
      </label>
      <div className="form-row">
        <label>
          <span className="label-text">Quantity</span>
          <input required type="number" min="1" value={form.quantity} onChange={e => setForm({ ...form, quantity: e.target.value })} />
        </label>
        <label>
          <span className="label-text">Max per user</span>
          <input required type="number" min="1" max="100" value={form.max_per_user} onChange={e => setForm({ ...form, max_per_user: e.target.value })} />
        </label>
        <label>
          <span className="label-text">Max per order</span>
          <input required type="number" min="1" max="100" value={form.max_per_order} onChange={e => setForm({ ...form, max_per_order: e.target.value })} />
        </label>
        <label>
          <span className="label-text">Visibility</span>
          <select value={form.visibility} onChange={e => setForm({ ...form, visibility: e.target.value })}>
            <option value="public">Public</option>
            <option value="hidden">Hidden (not listed publicly)</option>
            <option value="invite_only">Invite only</option>
          </select>
        </label>
      </div>
      <div className="form-row">
        <label>
          <span className="label-text">Sales open (optional)</span>
          <input type="datetime-local" value={form.sales_start} onChange={e => setForm({ ...form, sales_start: e.target.value })} />
        </label>
        <label>
          <span className="label-text">Sales close (optional)</span>
          <input type="datetime-local" value={form.sales_end} onChange={e => setForm({ ...form, sales_end: e.target.value })} />
        </label>
      </div>
    </>
  );
}

export function OrganizerEvents({ token, communityId }: { token: string; communityId?: string }) {
  const [events, setEvents] = useState<Event[]>([]);
  const [communities, setCommunities] = useState<Community[]>([]);
  const [categories, setCategories] = useState<EventCategory[]>([]);
  const [editing, setEditing] = useState<Event | null>(null);
  const [formSeed, setFormSeed] = useState(emptyForm);
  const draft = useDraftState(communityId ? `community:${communityId}:event:${editing?.id || 'new'}` : '', formSeed);
  const form = draft.value; const setForm = draft.set;
  const [discardDraft, setDiscardDraft] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [types, setTypes] = useState<TicketType[]>([]);
  const [ticketForm, setTicketForm] = useState(emptyTicketForm);
  const [showTicketForm, setShowTicketForm] = useState(false);
  const [savingTicket, setSavingTicket] = useState(false);
  const [editingType, setEditingType] = useState<TicketType | null>(null);
  const [typeForm, setTypeForm] = useState(emptyTicketForm);
  const [configEvent, setConfigEvent] = useState<Event | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  useRevealFocus(showForm, '[data-event-editor]');
  useRevealFocus(error, '.management-screen [role="alert"]');
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

  useEffect(() => { if (draft.ready && !form.category && categories.length) setForm(value => ({ ...value, category: categories[0].slug })); }, [draft.ready, categories]);

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
                  country_code: 'NG', lga: form.venue_lga || null,
                  latitude: form.venue_latitude === '' ? null : Number(form.venue_latitude), longitude: form.venue_longitude === '' ? null : Number(form.venue_longitude),
                },
              }),
        }),
      }, liveToken());
      setMessage(`Event "${data.title}" created.`);
      await draft.clear();
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
          ...(editing.venue && { venue: { name: form.venue_name, address: form.venue_address, city: form.venue_city || null, region: form.venue_region || null, lga: form.venue_lga || null, country_code: editing.venue.country_code || 'NG', latitude: form.venue_latitude === '' ? null : Number(form.venue_latitude), longitude: form.venue_longitude === '' ? null : Number(form.venue_longitude) } }),
          title: form.title,
          description: form.description,
          starts_at: new Date(form.starts_at).toISOString(),
          ends_at: new Date(form.ends_at).toISOString(),
        }),
      }, liveToken());
      setMessage(`Event "${data.title}" updated.`);
      await draft.clear();
      setEditing(null); setFormSeed(emptyForm);
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
    let body: ReturnType<typeof ticketTypePayload>;
    try { body = ticketTypePayload(ticketForm); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Check the ticket type details.'); return; }
    setSavingTicket(true); setError('');
    try {
      await apiJson<TicketType>(`events/${configEvent.id}/ticket-types`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }, liveToken());
      setMessage('Ticket type created.');
      setTicketForm(emptyTicketForm);
      setShowTicketForm(false);
      await loadTypes(configEvent);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Unable to create ticket type');
    } finally { setSavingTicket(false); }
  };

  const beginTypeEdit = (type: TicketType) => {
    setEditingType(type);
    setShowTicketForm(false);
    setError('');
    setTypeForm({
      name: type.name,
      description: type.description ?? '',
      price: String(Number(type.price)),
      currency: type.currency,
      quantity: String(type.quantity),
      max_per_user: String(type.max_per_user),
      max_per_order: String(type.max_per_order),
      visibility: type.visibility,
      sales_start: type.sales_start ? localInput(type.sales_start) : '',
      sales_end: type.sales_end ? localInput(type.sales_end) : '',
    });
  };

  /** Forward-looking maintenance. Issued tickets, orders and attendance are never rewritten. */
  const updateTicketType = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!configEvent || !editingType) return;
    let body: ReturnType<typeof ticketTypePayload>;
    try { body = ticketTypePayload(typeForm, Boolean(editingType.sold)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Check the ticket type details.'); return; }
    setSavingTicket(true); setError('');
    try {
      await apiJson<TicketType>(`events/${configEvent.id}/ticket-types/${editingType.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }, liveToken());
      setMessage(`"${body.name}" updated. Tickets already issued keep the terms they were sold on.`);
      setEditingType(null);
      await loadTypes(configEvent);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Unable to update ticket type');
    } finally { setSavingTicket(false); }
  };

  const beginEdit = (event: Event) => {
    setEditing(event);
setFormSeed({
  title: event.title,
  description: event.description,
  category: event.category,
  starts_at: localInput(event.starts_at),
  ends_at: localInput(event.ends_at),
  online_url: event.online_url ?? '',
  venue_name: event.venue?.name ?? '',
  venue_address: event.venue?.address ?? '',
  venue_city: event.venue?.city ?? '',
  venue_region: event.venue?.region ?? '', venue_lga: event.venue?.lga ?? '', venue_latitude: String(event.venue?.latitude ?? ''), venue_longitude: String(event.venue?.longitude ?? ''),
});
    setShowForm(true);
    setConfigEvent(null);
  };

  const cancelForm = () => { setEditing(null); setFormSeed(emptyForm); setShowForm(false); setError(''); };

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
            <button className="accent" onClick={() => { setShowForm(true); setEditing(null); setFormSeed(emptyForm); }}>
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
          <p role="status">{draft.ready ? 'Draft saved privately on this browser; closing keeps it.' : 'Recovering draft…'}</p>{draft.error && <p role="alert">{draft.error}</p>}
          <form data-event-editor onSubmit={editing ? update : create}>
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
            {(!editing || editing.venue) && (
  <>
    <label>
      <span className="label-text">Online URL (leave blank for in-person)</span>
      <input
        type="url"
        disabled={!!editing}
        value={form.online_url}
        onChange={e => setForm({ ...form, online_url: e.target.value })}
        placeholder="https://meet.example.com/event"
      />
    </label>

    {(editing?.venue || !form.online_url) && (
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
            <span className="label-text">City / Town</span>
            <input
              value={form.venue_city}
              onChange={e => setForm({ ...form, venue_city: e.target.value })}
              placeholder="e.g. Enugu"
            />
          </label>

<NigeriaLocation region={form.venue_region} lga={form.venue_lga} onChange={(region, lga) => setForm({ ...form, venue_region: region, venue_lga: lga })} />
          {(['latitude', 'longitude'] as const).map(key => <label key={key}>Venue {key} (optional)<input type="number" step="any" min={key === 'latitude' ? -90 : -180} max={key === 'latitude' ? 90 : 180} value={form[`venue_${key}`]} onChange={e => setForm({ ...form, [`venue_${key}`]: e.target.value })} /></label>)}
        </div>
      </>
    )}
  </>
)}
            <div className="form-actions">
              <button type="submit" className="accent" disabled={saving || !draft.ready || (!editing && (categoriesLoading || categories.length === 0))}>
                {saving ? 'Saving…' : editing ? 'Save changes' : 'Create event'}
              </button>
              <button type="button" className="secondary" onClick={cancelForm}>Close and keep draft</button><button type="button" disabled={saving} onClick={() => setDiscardDraft(true)}>Discard draft</button>
            </div>
          </form>
        </div>
      )}

      {discardDraft && <GovernanceConfirm title="Discard event draft?" consequence="This removes the unfinished event form from this browser." requireReason={false} onClose={() => setDiscardDraft(false)} onConfirm={async () => { await draft.clear(); setDiscardDraft(false); cancelForm(); }} />}
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
                      <TicketTypeFields form={ticketForm} setForm={setTicketForm} />
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
                        <div key={type.id}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '.65rem .85rem', background: 'var(--tv-surface-sunken)', borderRadius: 'var(--tv-radius-md)', fontSize: '.875rem', gap: '.5rem', flexWrap: 'wrap' }}>
                            <strong>{type.name}</strong>
                            <div style={{ display: 'flex', gap: '.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
                              <span>{Number(type.price) === 0 ? 'Free' : `${type.currency} ${Number(type.price).toLocaleString()}`}</span>
                              <span className={`chip ${type.availability > 0 ? 'chip-green' : 'chip-red'}`}>{type.availability} left</span>
                              <span className="chip chip-default">{type.visibility}</span>
                              <span className="chip chip-default" title="Maximum tickets one buyer may take in a single order">Max {type.max_per_order}/order</span>
                              <button className="secondary sm" onClick={() => editingType?.id === type.id ? setEditingType(null) : beginTypeEdit(type)}>
                                {editingType?.id === type.id ? 'Close' : 'Edit'}
                              </button>
                            </div>
                          </div>
                          {editingType?.id === type.id && (
                            <form onSubmit={updateTicketType} data-ticket-type-editor style={{ background: 'var(--tv-surface-sunken)', padding: '1rem', borderRadius: 'var(--tv-radius-md)', marginTop: '.5rem', display: 'grid', gap: '.75rem' }}>
                              <TicketTypeFields form={typeForm} setForm={setTypeForm} lockPrice={Boolean(type.sold)} />
                              <p className="text-sm text-muted">Changing this affects future sales only. Tickets already issued keep the terms they were sold on.</p>
                              <div className="form-actions">
                                <button type="submit" className="accent sm" disabled={savingTicket}>{savingTicket ? 'Saving…' : 'Save ticket type'}</button>
                                <button type="button" className="secondary sm" onClick={() => setEditingType(null)} disabled={savingTicket}>Cancel</button>
                              </div>
                            </form>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <OrganizerEntitlements eventId={event.id} token={liveToken()} />
              </div>
            )}
          </article>
        ))}
      </div>
    </div>
  );
}
