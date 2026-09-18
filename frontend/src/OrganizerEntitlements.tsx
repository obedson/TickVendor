/** Organizer maintenance of the benefits attached to a ticket type.
 *
 * Benefit names are free text on purpose: "Meal", "Lunch", "Drink", "Gift", "Table", "Certificate"
 * are examples an organizer may use, not a list this screen enforces. Everything here is
 * forward-looking configuration — a benefit that has already been redeemed keeps its history,
 * and deactivating one stops future redemptions without rewriting what happened.
 */

import { useCallback, useEffect, useState } from 'react';
import { apiJson, ApiError, getLiveToken } from './api';

type TicketType = {
  id: string;
  name: string;
  price: string;
  currency: string;
  quantity: number;
  availability: number;
  visibility: string;
  max_per_user: number;
  max_per_order: number;
  sales_start?: string | null;
  sales_end?: string | null;
};

type Entitlement = {
  id: string;
  ticket_type_id: string;
  name: string;
  description?: string | null;
  quantity: number;
  is_active: boolean;
  redemption_mode: string;
  redemption_starts_at?: string | null;
  redemption_ends_at?: string | null;
  requires_check_in: boolean;
  requires_checkout: boolean;
  min_attendance_minutes?: number | null;
  requires_geofence: boolean;
  requires_staff_validation: boolean;
  one_time: boolean;
  max_redemptions_per_ticket: number;
};

/** `datetime-local` speaks wall-clock; the API speaks instants. Convert at the boundary only. */
function toLocalInput(value: string | null | undefined): string {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}
function fromLocalInput(value: string): string | null {
  return value ? new Date(value).toISOString() : null;
}

type Draft = {
  ticket_type_id: string;
  name: string;
  description: string;
  quantity: string;
  is_active: boolean;
  redemption_mode: string;
  redemption_starts_at: string;
  redemption_ends_at: string;
  requires_check_in: boolean;
  requires_checkout: boolean;
  min_attendance_minutes: string;
  requires_geofence: boolean;
  requires_staff_validation: boolean;
  one_time: boolean;
  max_redemptions_per_ticket: string;
};

function emptyDraft(ticketTypeId: string): Draft {
  return {
    ticket_type_id: ticketTypeId,
    name: '',
    description: '',
    quantity: '1',
    is_active: true,
    redemption_mode: 'either',
    redemption_starts_at: '',
    redemption_ends_at: '',
    requires_check_in: true,
    requires_checkout: false,
    min_attendance_minutes: '',
    requires_geofence: false,
    requires_staff_validation: true,
    one_time: true,
    max_redemptions_per_ticket: '1',
  };
}

function draftOf(entitlement: Entitlement): Draft {
  return {
    ticket_type_id: entitlement.ticket_type_id,
    name: entitlement.name,
    description: entitlement.description ?? '',
    quantity: String(entitlement.quantity),
    is_active: entitlement.is_active,
    redemption_mode: entitlement.redemption_mode,
    redemption_starts_at: toLocalInput(entitlement.redemption_starts_at),
    redemption_ends_at: toLocalInput(entitlement.redemption_ends_at),
    requires_check_in: entitlement.requires_check_in,
    requires_checkout: entitlement.requires_checkout,
    min_attendance_minutes: entitlement.min_attendance_minutes == null ? '' : String(entitlement.min_attendance_minutes),
    requires_geofence: entitlement.requires_geofence,
    requires_staff_validation: entitlement.requires_staff_validation,
    one_time: entitlement.one_time,
    max_redemptions_per_ticket: String(entitlement.max_redemptions_per_ticket),
  };
}

/**
 * The payload for create and edit alike.
 *
 * The window check mirrors the backend's own rule so the organizer gets a usable message before
 * the round trip; the backend remains the authority and is never bypassed.
 */
function payload(draft: Draft) {
  const starts = fromLocalInput(draft.redemption_starts_at);
  const ends = fromLocalInput(draft.redemption_ends_at);
  if (starts && ends && new Date(ends) <= new Date(starts)) {
    throw new Error('Redemption must end after it starts.');
  }
  return {
    ticket_type_id: draft.ticket_type_id,
    name: draft.name.trim(),
    description: draft.description.trim() || null,
    quantity: Number(draft.quantity),
    is_active: draft.is_active,
    redemption_mode: draft.redemption_mode,
    redemption_starts_at: starts,
    redemption_ends_at: ends,
    requires_check_in: draft.requires_check_in,
    requires_checkout: draft.requires_checkout,
    min_attendance_minutes: draft.min_attendance_minutes === '' ? null : Number(draft.min_attendance_minutes),
    requires_geofence: draft.requires_geofence,
    requires_staff_validation: draft.requires_staff_validation,
    one_time: draft.one_time,
    max_redemptions_per_ticket: Number(draft.max_redemptions_per_ticket),
  };
}

export function OrganizerEntitlements({ eventId, token }: { eventId: string; token: string }) {
  const [types, setTypes] = useState<TicketType[]>([]);
  const [entitlements, setEntitlements] = useState<Entitlement[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [saving, setSaving] = useState(false);
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState<Draft>(() => emptyDraft(''));
  const [editingId, setEditingId] = useState('');

  const liveToken = () => getLiveToken() ?? token;

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [typeRows, entitlementRows] = await Promise.all([
        apiJson<TicketType[]>(`events/${eventId}/ticket-types`, {}, liveToken()),
        apiJson<Entitlement[]>(`events/${eventId}/entitlements`, {}, liveToken()),
      ]);
      setTypes(typeRows);
      setEntitlements(entitlementRows);
      setDraft(current => current.ticket_type_id || !typeRows.length
        ? current
        : emptyDraft(typeRows[0].id));
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Unable to load benefits for this event.');
    } finally {
      setLoading(false);
    }
  }, [eventId, token]);

  useEffect(() => { load(); }, [load]);

  const beginCreate = () => {
    setEditingId('');
    setCreating(true);
    setNotice('');
    setError('');
    setDraft(emptyDraft(types[0]?.id ?? ''));
  };

  const beginEdit = (entitlement: Entitlement) => {
    setCreating(false);
    setEditingId(entitlement.id);
    setNotice('');
    setError('');
    setDraft(draftOf(entitlement));
  };

  const closeForm = () => { setCreating(false); setEditingId(''); setError(''); };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    let body: ReturnType<typeof payload>;
    try {
      body = payload(draft);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Check the benefit details.');
      return;
    }
    if (!body.name) { setError('Give this benefit a name.'); return; }
    if (!body.ticket_type_id) { setError('Choose the ticket type this benefit belongs to.'); return; }
    setSaving(true);
    setError('');
    setNotice('');
    try {
      if (editingId) {
        await apiJson<Entitlement>(`events/${eventId}/entitlements/${editingId}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        }, liveToken());
        setNotice(`"${body.name}" updated. Tickets already issued keep their redemption history.`);
      } else {
        await apiJson<Entitlement>(`events/${eventId}/entitlements`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        }, liveToken());
        setNotice(`"${body.name}" added.`);
      }
      closeForm();
      await load();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'The benefit could not be saved.');
    } finally {
      setSaving(false);
    }
  };

  /** Activating and deactivating is the same edit with one field changed. */
  const toggleActive = async (entitlement: Entitlement) => {
    setSaving(true);
    setError('');
    setNotice('');
    try {
      await apiJson<Entitlement>(`events/${eventId}/entitlements/${entitlement.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: !entitlement.is_active }),
      }, liveToken());
      setNotice(entitlement.is_active
        ? `"${entitlement.name}" is now off. Holders can no longer redeem it.`
        : `"${entitlement.name}" is now on.`);
      await load();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'The benefit could not be changed.');
    } finally {
      setSaving(false);
    }
  };

  const form = (
    <form onSubmit={submit} className="stack" data-entitlement-editor>
      <div className="form-row">
        <label>
          <span className="label-text">Ticket type</span>
          {/* A benefit cannot move between ticket types: the edit contract has no such field, and
              moving one would move redemption history that already happened. Say so rather than
              offering a control whose change would be silently dropped. */}
          <select
            required
            value={draft.ticket_type_id}
            disabled={Boolean(editingId)}
            onChange={e => setDraft({ ...draft, ticket_type_id: e.target.value })}
          >
            <option value="">Select a ticket type</option>
            {types.map(type => <option key={type.id} value={type.id}>{type.name}</option>)}
          </select>
        </label>
        <label>
          <span className="label-text">Benefit name</span>
          <input required value={draft.name} onChange={e => setDraft({ ...draft, name: e.target.value })} placeholder="e.g. Lunch, Drink, Gift" />
        </label>
      </div>
      {Boolean(editingId) && (
        <p className="text-sm text-muted">
          This benefit stays on the ticket type it was created for, so the redemptions already
          recorded against it keep their meaning. Add a new benefit on another ticket type instead.
        </p>
      )}
      <label>
        <span className="label-text">Description (optional)</span>
        <input value={draft.description} onChange={e => setDraft({ ...draft, description: e.target.value })} placeholder="What the holder receives…" />
      </label>
      <div className="form-row">
        <label>
          <span className="label-text">Quantity</span>
          <input required type="number" min="0" max="1000" value={draft.quantity} onChange={e => setDraft({ ...draft, quantity: e.target.value })} />
        </label>
        <label>
          <span className="label-text">Redemptions per ticket</span>
          <input required type="number" min="1" max="100" value={draft.max_redemptions_per_ticket} onChange={e => setDraft({ ...draft, max_redemptions_per_ticket: e.target.value })} />
        </label>
        <label>
          <span className="label-text">Credential</span>
          <select value={draft.redemption_mode} onChange={e => setDraft({ ...draft, redemption_mode: e.target.value })}>
            <option value="either">QR code or short code</option>
            <option value="qr">QR code only</option>
            <option value="code">Short code only</option>
          </select>
        </label>
      </div>
      <div className="form-row">
        <label>
          <span className="label-text">Redemption opens (optional)</span>
          <input type="datetime-local" value={draft.redemption_starts_at} onChange={e => setDraft({ ...draft, redemption_starts_at: e.target.value })} />
        </label>
        <label>
          <span className="label-text">Redemption closes (optional)</span>
          <input type="datetime-local" value={draft.redemption_ends_at} onChange={e => setDraft({ ...draft, redemption_ends_at: e.target.value })} />
        </label>
        <label>
          <span className="label-text">Minimum time at event, minutes (optional)</span>
          <input type="number" min="0" max="10080" value={draft.min_attendance_minutes} onChange={e => setDraft({ ...draft, min_attendance_minutes: e.target.value })} placeholder="No minimum" />
        </label>
      </div>
      <fieldset className="check-group">
        <legend className="label-text">Conditions</legend>
        <label className="check">
          <input type="checkbox" checked={draft.requires_check_in} onChange={e => setDraft({ ...draft, requires_check_in: e.target.checked })} />
          <span>Must be checked in</span>
        </label>
        <label className="check">
          <input type="checkbox" checked={draft.requires_checkout} onChange={e => setDraft({ ...draft, requires_checkout: e.target.checked })} />
          <span>Must have checked out</span>
        </label>
        <label className="check">
          <input type="checkbox" checked={draft.requires_geofence} onChange={e => setDraft({ ...draft, requires_geofence: e.target.checked })} />
          <span>Only inside the venue</span>
        </label>
        <label className="check">
          <input type="checkbox" checked={draft.requires_staff_validation} onChange={e => setDraft({ ...draft, requires_staff_validation: e.target.checked })} />
          <span>Staff must validate the code</span>
        </label>
        <label className="check">
          <input type="checkbox" checked={draft.one_time} onChange={e => setDraft({ ...draft, one_time: e.target.checked })} />
          <span>One credential at a time</span>
        </label>
        <label className="check">
          <input type="checkbox" checked={draft.is_active} onChange={e => setDraft({ ...draft, is_active: e.target.checked })} />
          <span>Active</span>
        </label>
      </fieldset>
      <div className="form-actions">
        <button type="submit" className="accent sm" disabled={saving}>
          {saving ? 'Saving…' : editingId ? 'Save benefit' : 'Add benefit'}
        </button>
        <button type="button" className="secondary sm" onClick={closeForm} disabled={saving}>Cancel</button>
      </div>
    </form>
  );

  return (
    <section className="panel" aria-labelledby="benefits-config-title">
      <div className="panel-head">
        <h4 id="benefits-config-title">Ticket benefits</h4>
        {!creating && !editingId && (
          <button className="accent sm" onClick={beginCreate} disabled={!types.length}>+ Add benefit</button>
        )}
      </div>
      <p className="text-sm text-muted">
        Benefits are attached to a ticket type and are shown to whoever holds the ticket.
        Deactivating one stops future redemptions without erasing past ones.
      </p>

      {error && <p role="alert" className="error">{error}</p>}
      {notice && <p role="status" className="success-msg">{notice}</p>}
      {loading && <p role="status" className="text-muted">Loading benefits…</p>}

      {!loading && !types.length && !error && (
        <p className="empty">Create a ticket type first — benefits attach to a ticket type.</p>
      )}

      {(creating || editingId) && form}

      {!loading && Boolean(entitlements.length) && (
        <ul className="benefit-list">
          {entitlements.map(entitlement => {
            const type = types.find(item => item.id === entitlement.ticket_type_id);
            return (
              <li key={entitlement.id} className="benefit">
                <div className="benefit-head">
                  <strong>{entitlement.name}</strong>
                  <span className={`chip ${entitlement.is_active ? 'chip-green' : 'chip-default'}`}>
                    <span aria-hidden="true">{entitlement.is_active ? '●' : '⊘'}</span>{' '}
                    {entitlement.is_active ? 'Active' : 'Off'}
                  </span>
                </div>
                <p className="text-sm text-muted">
                  {type ? type.name : 'Ticket type removed'} · {entitlement.quantity} per ticket ·{' '}
                  {entitlement.max_redemptions_per_ticket} redemption{entitlement.max_redemptions_per_ticket === 1 ? '' : 's'} ·{' '}
                  {entitlement.redemption_mode === 'either' ? 'QR or code' : entitlement.redemption_mode === 'qr' ? 'QR only' : 'Code only'}
                </p>
                <p className="text-sm text-muted">
                  {[
                    entitlement.requires_check_in ? 'checked in' : null,
                    entitlement.requires_checkout ? 'checked out' : null,
                    entitlement.requires_geofence ? 'inside venue' : null,
                    entitlement.requires_staff_validation ? 'staff validated' : 'self-service',
                    entitlement.min_attendance_minutes ? `${entitlement.min_attendance_minutes} min attendance` : null,
                    entitlement.redemption_starts_at ? `opens ${new Date(entitlement.redemption_starts_at).toLocaleString()}` : null,
                    entitlement.redemption_ends_at ? `closes ${new Date(entitlement.redemption_ends_at).toLocaleString()}` : null,
                  ].filter(Boolean).join(' · ') || 'No conditions — available as soon as the ticket is held.'}
                </p>
                <div className="form-actions">
                  <button className="secondary sm" onClick={() => beginEdit(entitlement)} disabled={saving}>Edit</button>
                  <button className="secondary sm" onClick={() => toggleActive(entitlement)} disabled={saving}>
                    {entitlement.is_active ? 'Deactivate' : 'Activate'}
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
