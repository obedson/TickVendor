/** One ticket, everything that can be done with it, and nothing it cannot do.
 *
 * The backend owns every decision here — who holds the ticket, whether a benefit is unlocked,
 * whether a coordinate is inside the venue. This screen only ever *asks*: it never decides a
 * geofence, never issues a credential locally, and never treats the permanent admission QR as a
 * transfer or redemption credential.
 */

import { useCallback, useEffect, useState } from 'react';
import { apiJson, ApiError, getLiveToken } from './api';
import { currentPosition, LocationFailure } from './geolocation';
import {
  formatDuration,
  TICKET_STATE,
  ticketState,
  TRANSFER_STATUS_LABEL,
  type RedemptionCredential,
  type StartedTransfer,
  type TicketDetail as TicketDetailData,
  type TicketEntitlement,
} from './tickets';
import type { OfflineTicket } from './offlineTickets';

type Props = {
  ticketId: string;
  token: string;
  onBack: () => void;
  onWalletChanged: () => void;
};

type Busy = '' | 'check-in' | 'check-out' | 'transfer' | 'cancel-transfer' | 'location';

/** Renders a value as a scannable code without pulling a camera library into the app. */
function QrImage({ value, alt }: { value: string; alt: string }) {
  const [src, setSrc] = useState('');
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    setSrc('');
    setFailed(false);
    import('qrcode')
      .then(({ default: QRCode }) => QRCode.toDataURL(value, { width: 220, margin: 2, color: { dark: '#172554', light: '#ffffff' } }))
      .then(data => { if (active) setSrc(data); })
      .catch(() => { if (active) setFailed(true); });
    return () => { active = false; };
  }, [value]);

  if (failed) return <p className="text-muted text-sm">The code could not be drawn. Use the text code instead.</p>;
  if (!src) return <p role="status" className="text-muted text-sm">Preparing code…</p>;
  return <img className="qr-image" src={src} alt={alt} />;
}

function message(cause: unknown, fallback: string): string {
  if (cause instanceof ApiError || cause instanceof LocationFailure || cause instanceof Error) return cause.message;
  return fallback;
}

/** The backend says location is missing, which is the one case where asking for it is justified. */
function needsLocation(cause: unknown): boolean {
  return cause instanceof ApiError && cause.status === 422 && /location/i.test(cause.message);
}

export function TicketDetail({ ticketId, token, onBack, onWalletChanged }: Props) {
  const [detail, setDetail] = useState<TicketDetailData | null>(null);
  const [walletTicket, setWalletTicket] = useState<OfflineTicket | null>(null);
  const [geofenced, setGeofenced] = useState<boolean | null>(null);
  const [locationRadius, setLocationRadius] = useState<number | undefined>();
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState<Busy>('');
  const [transferEmail, setTransferEmail] = useState('');
  const [transfer, setTransfer] = useState<StartedTransfer | null>(null);
  const [showTransfer, setShowTransfer] = useState(false);
  const [shared, setShared] = useState('');
  const [redemption, setRedemption] = useState<{ entitlement: string; credential: RedemptionCredential } | null>(null);
  /** Set when the backend refused an action for want of a coordinate, so we can offer one retry. */
  const [locationRetry, setLocationRetry] = useState<'' | 'check-in' | 'check-out'>('');
  const [clock, setClock] = useState(() => Date.now());

  const liveToken = () => getLiveToken() ?? token;

  const load = useCallback(async (query = '') => {
    setLoading(true);
    setLoadError('');
    try {
      setDetail(await apiJson<TicketDetailData>(`tickets/${ticketId}${query}`, {}, liveToken()));
    } catch (cause) {
      setLoadError(message(cause, 'Unable to load this ticket.'));
    } finally {
      setLoading(false);
    }
    // The wallet row carries the holder-facing state (unassigned / invitation sent / checked in)
    // that the detail payload does not restate. Read it from the same source My Tickets uses.
    apiJson<OfflineTicket[]>('tickets/me', {}, liveToken())
      .then(rows => setWalletTicket(rows.find(row => row.id === ticketId) ?? null))
      .catch(() => setWalletTicket(null));
  }, [ticketId, token]);

  useEffect(() => { load(); }, [load]);

  // Only needed to know whether a fix is required before check-in or checkout. A failure here is
  // not fatal: the backend still refuses a geofenced action that arrives without coordinates.
  useEffect(() => {
    const eventId = detail?.ticket.event_id;
    if (!eventId) return;
    let active = true;
    setLocationRadius(undefined);
    apiJson<{ geofence_enabled: boolean; geofence_radius_meters?: number }>(`events/${eventId}`, {}, liveToken())
      .then(event => { if (active) { setGeofenced(event.geofence_enabled); setLocationRadius(event.geofence_enabled ? event.geofence_radius_meters : undefined); } })
      .catch(() => { if (active) setGeofenced(null); });
    return () => { active = false; };
  }, [detail?.ticket.event_id, token]);

  // A redemption credential is short-lived; the countdown is display only, the backend decides.
  useEffect(() => {
    if (!redemption?.credential.expires_at) return;
    const timer = window.setInterval(() => setClock(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [redemption?.credential.expires_at]);

  const secondsLeft = redemption?.credential.expires_at
    ? Math.max(0, Math.floor((new Date(redemption.credential.expires_at).getTime() - clock) / 1000))
    : null;

  /**
   * Read one fix. Whether a coordinate is needed at all is the *caller's* decision — every call
   * site makes it before calling — so there are exactly two outcomes here: the point that was
   * read, or `null` when the read failed and the caller must stop. `currentPosition` either
   * resolves with a full reading or rejects with a classified `LocationFailure`; it never
   * resolves a partial value, so no third outcome exists.
   */
  const readLocation = async (): Promise<{ latitude: number; longitude: number; accuracy_meters: number } | null> => {
    try {
      return await currentPosition({ timeout: 10000, targetAccuracy: locationRadius });
    } catch (failure) {
      setError(failure instanceof LocationFailure
        ? `${failure.message} Ask event staff to record this for you.`
        : 'Your location could not be read. Ask event staff to record this for you.');
      return null;
    }
  };

  const submitCheckIn = async (withLocation: boolean) => {
    if (!detail) return;
    setBusy('check-in');
    setError('');
    setNotice('');
    setLocationRetry('');
    let point: { latitude: number; longitude: number; accuracy_meters: number } | undefined;
    if (withLocation || geofenced === true) {
      const read = await readLocation();
      if (read === null) { setBusy(''); return; }
      point = read;
    }
    try {
      await apiJson(`events/${detail.ticket.event_id}/tickets/${ticketId}/check-in`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(point ?? {}),
      }, liveToken());
      setNotice('You are checked in. Your attendance is recorded.');
      await load();
      onWalletChanged();
    } catch (cause) {
      setError(message(cause, 'Check-in could not be completed.'));
      if (needsLocation(cause)) setLocationRetry('check-in');
    } finally {
      setBusy('');
    }
  };

  const submitCheckOut = async (withLocation: boolean) => {
    if (!detail) return;
    setBusy('check-out');
    setError('');
    setNotice('');
    setLocationRetry('');
    let point: { latitude: number; longitude: number; accuracy_meters: number } | undefined;
    if (withLocation || geofenced === true) {
      const read = await readLocation();
      if (read === null) { setBusy(''); return; }
      point = read;
    }
    try {
      const state = await apiJson<{ duration_seconds?: number | null }>(
        `events/${detail.ticket.event_id}/tickets/${ticketId}/check-out`,
        { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(point ?? {}) },
        liveToken(),
      );
      const spent = formatDuration(state.duration_seconds);
      setNotice(spent ? `Checkout recorded. You spent ${spent} at this event.` : 'Checkout recorded. Your attendance is finalised.');
      await load();
      onWalletChanged();
    } catch (cause) {
      setError(message(cause, 'Checkout could not be completed.'));
      if (needsLocation(cause)) setLocationRetry('check-out');
    } finally {
      setBusy('');
    }
  };

  const startTransfer = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy('transfer');
    setError('');
    setNotice('');
    try {
      const started = await apiJson<StartedTransfer>(`tickets/${ticketId}/transfers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ recipient_email: transferEmail.trim() || null }),
      }, liveToken());
      setTransfer(started);
      setShared('');
      setNotice('Transfer link ready. Send it to the person who will attend.');
      onWalletChanged();
    } catch (cause) {
      setError(message(cause, 'The transfer link could not be created.'));
    } finally {
      setBusy('');
    }
  };

  const cancelTransfer = async () => {
    setBusy('cancel-transfer');
    setError('');
    setNotice('');
    try {
      await apiJson(`tickets/${ticketId}/transfers`, { method: 'DELETE' }, liveToken());
      setTransfer(null);
      setNotice('Transfer link cancelled. You still hold this ticket.');
      await load();
      onWalletChanged();
    } catch (cause) {
      setError(message(cause, 'The transfer link could not be cancelled.'));
    } finally {
      setBusy('');
    }
  };

  const shareUrl = transfer?.share_url ?? '';
  const shareText = detail ? `${detail.ticket_type_name} ticket for ${detail.event_title}` : 'Your ticket';

  const copyLink = async () => {
    setShared('');
    try {
      await navigator.clipboard.writeText(shareUrl);
      setShared('Link copied.');
    } catch {
      setShared('Copying is blocked in this browser. Select the link and copy it manually.');
    }
  };

  const nativeShare = async () => {
    setShared('');
    try {
      await navigator.share({ title: shareText, text: shareText, url: shareUrl });
      setShared('Shared.');
    } catch {
      // A cancelled share sheet is not a failure worth shouting about.
      setShared('Sharing was cancelled. The link is still valid.');
    }
  };

  const redeem = async (entitlement: TicketEntitlement) => {
    if (!detail) return;
    setBusy('location');
    setError('');
    setNotice('');
    let point: { latitude: number; longitude: number; accuracy_meters: number } | undefined;
    if (entitlement.requires_geofence) {
      const read = await readLocation();
      if (read === null) { setBusy(''); return; }
      point = read;
    }
    try {
      const credential = await apiJson<RedemptionCredential>(
        `tickets/${ticketId}/entitlements/${entitlement.id}/redemption`,
        { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(point ?? {}) },
        liveToken(),
      );
      setRedemption({ entitlement: entitlement.name, credential });
    } catch (cause) {
      setError(message(cause, 'This benefit could not be redeemed.'));
    } finally {
      setBusy('');
    }
  };

  /** Ask the backend to re-evaluate eligibility with a real fix rather than guessing locally. */
  const refreshWithLocation = async () => {
    setBusy('location');
    setError('');
    const read = await readLocation();
    if (read === null) { setBusy(''); return; }
    try {
      const query = new URLSearchParams({
        latitude: String(read.latitude),
        longitude: String(read.longitude),
        accuracy_meters: String(read.accuracy_meters),
      });
      await load(`?${query}`);
      setNotice('Location confirmed.');
    } finally {
      setBusy('');
    }
  };

  if (loading && !detail) return <p role="status" className="text-muted">Loading your ticket…</p>;

  if (loadError) {
    return (
      <div>
        <button className="link" onClick={onBack}>← Back to My Tickets</button>
        <p role="alert" className="error" style={{ marginTop: '1rem' }}>{loadError}</p>
      </div>
    );
  }

  if (!detail) return null;

  const state = walletTicket ? ticketState(walletTicket) : null;
  const stateInfo = state ? TICKET_STATE[state] : null;
  const attendance = detail.attendance;
  const checkedIn = Boolean(attendance?.checked_in_at);
  const checkedOut = Boolean(attendance?.checked_out_at);
  const holdsTicket = state === null || ['claimed', 'checked_in', 'checked_out'].includes(state);
  const canCheckIn = detail.self_check_in_enabled && !checkedIn && holdsTicket;
  const canCheckOut = detail.self_checkout_enabled && checkedIn && !checkedOut;
  const canTransfer = state === null || ['claimed', 'unassigned', 'invitation_sent'].includes(state);
  const duration = formatDuration(attendance?.duration_seconds);
  const geofenceLocked = detail.entitlements.some(item => item.requires_geofence && item.status === 'locked');
  const busyAny = Boolean(busy);

  return (
    <div className="ticket-detail">
      <button className="link" onClick={onBack}>← Back to My Tickets</button>

      <div className="page-header">
        <div className="page-header-text">
          <p className="eyebrow">Ticket</p>
          <h1>{detail.event_title}</h1>
          <p>{detail.ticket_type_name}</p>
        </div>
      </div>

      {error && <p role="alert" className="error">{error}</p>}
      {notice && <p role="status" className="success-msg">{notice}</p>}

      <div className="ticket-detail-grid">
        {/* ── Admission ── */}
        <section className="panel" aria-labelledby="admission-title">
          <h2 id="admission-title" className="panel-title">Admission</h2>
          <p className="ticket-state-line">
            {stateInfo && (
              <span className={`chip ${stateInfo.chip}`}>
                <span aria-hidden="true">{stateInfo.glyph}</span> {stateInfo.label}
              </span>
            )}
            <code className="text-sm text-muted">{detail.ticket.public_id}</code>
          </p>
          {stateInfo && <p className="text-sm text-muted">{stateInfo.help}</p>}

          <p className="text-sm text-muted">
            {walletTicket?.purchaser_id && walletTicket.attendee_id === walletTicket.purchaser_id
              ? 'You purchased this ticket.'
              : 'This ticket was shared with you — you are the attendee for attendance and benefits.'}
          </p>

          <dl className="claim-facts">
            <dt>Starts</dt>
            <dd><time dateTime={detail.event_starts_at}>{new Date(detail.event_starts_at).toLocaleString()}</time></dd>
            {detail.event_ends_at && (
              <>
                <dt>Ends</dt>
                <dd><time dateTime={detail.event_ends_at}>{new Date(detail.event_ends_at).toLocaleString()}</time></dd>
              </>
            )}
            {(detail.venue_name || detail.venue_address) && (
              <>
                <dt>Venue</dt>
                <dd>{[detail.venue_name, detail.venue_address].filter(Boolean).join(', ')}</dd>
              </>
            )}
            {checkedIn && attendance?.checked_in_at && (
              <>
                <dt>Checked in</dt>
                <dd><time dateTime={attendance.checked_in_at}>{new Date(attendance.checked_in_at).toLocaleString()}</time></dd>
              </>
            )}
            {checkedOut && attendance?.checked_out_at && (
              <>
                <dt>Checked out</dt>
                <dd><time dateTime={attendance.checked_out_at}>{new Date(attendance.checked_out_at).toLocaleString()}</time></dd>
              </>
            )}
            {checkedOut && duration && (
              <>
                <dt>Time at event</dt>
                <dd>{duration}</dd>
              </>
            )}
          </dl>

          {/* The admission QR is the entry credential and nothing else: it is never offered as a
              transfer or redemption credential, and it is withheld until somebody holds the ticket. */}
          {holdsTicket ? (
            <div className="admission-code">
              <QrImage value={detail.ticket.qr_token} alt={`Admission QR code for ticket ${detail.ticket.public_id}`} />
              <p className="text-sm text-muted">Show this code at the door. Do not send it to anyone — use Transfer instead.</p>
            </div>
          ) : (
            <p className="info-msg">This ticket has no attendee yet, so there is no admission code. Send it to the person who will attend.</p>
          )}

          {locationRetry === 'check-in' && (
            <div className="form-actions">
              <button className="accent" onClick={() => submitCheckIn(true)} disabled={busyAny}>
                Use my location and try again
              </button>
            </div>
          )}
          {canCheckIn && locationRetry !== 'check-in' && (
            <div className="form-actions">
              <button className="accent" onClick={() => submitCheckIn(false)} disabled={busyAny}>
                {busy === 'check-in' ? 'Checking in…' : 'Self check-in'}
              </button>
            </div>
          )}
          {detail.self_check_in_enabled && !checkedIn && !holdsTicket && (
            <p className="info-msg">Claim or transfer this ticket to an attendee before check-in.</p>
          )}

          {locationRetry === 'check-out' && (
            <div className="form-actions">
              <button className="accent" onClick={() => submitCheckOut(true)} disabled={busyAny}>
                Use my location and try again
              </button>
            </div>
          )}
          {canCheckOut && locationRetry !== 'check-out' && (
            <div className="form-actions">
              <button className="secondary" onClick={() => submitCheckOut(false)} disabled={busyAny}>
                {busy === 'check-out' ? 'Recording checkout…' : 'Self checkout'}
              </button>
            </div>
          )}
          {detail.self_check_in_enabled && geofenced !== false && !checkedIn && (
            <p className="text-sm text-muted">Your location is read once, at check-in, to confirm you are at the venue. It is not tracked.</p>
          )}
        </section>

        {/* ── Transfer ── */}
        <section className="panel" aria-labelledby="transfer-title">
          <h2 id="transfer-title" className="panel-title">Transfer this ticket</h2>
          {state === 'invitation_sent' && !transfer && (
            <p className="info-msg">A claim link is outstanding. Creating a new link retires the previous one.</p>
          )}
          {!canTransfer ? (
            <p className="text-muted text-sm">
              {state === 'checked_in' || state === 'checked_out'
                ? 'This ticket has been used and can no longer be transferred.'
                : 'This ticket is no longer valid and cannot be transferred.'}
            </p>
          ) : !transfer ? (
            !showTransfer ? (
              <div className="form-actions">
                <button className="accent" onClick={() => setShowTransfer(true)}>Send / transfer ticket</button>
              </div>
            ) : (
              <form onSubmit={startTransfer} className="stack">
                <label>
                  <span className="label-text">Recipient email (optional)</span>
                  <input
                    type="email"
                    value={transferEmail}
                    onChange={event => setTransferEmail(event.target.value)}
                    placeholder="them@example.com"
                    autoComplete="email"
                  />
                </label>
                <p className="text-sm text-muted">
                  The ticket moves when they open the link and claim it. Until then you still hold it,
                  and you can cancel the link at any time.
                </p>
                <div className="form-actions">
                  <button type="submit" className="accent" disabled={busyAny}>
                    {busy === 'transfer' ? 'Creating link…' : 'Create transfer link'}
                  </button>
                  <button type="button" className="secondary" onClick={() => { setShowTransfer(false); setTransferEmail(''); }}>
                    Cancel
                  </button>
                </div>
              </form>
            )
          ) : (
            <div className="stack">
              <p className="text-sm text-muted">
                {TRANSFER_STATUS_LABEL[transfer.status] ?? transfer.status} · link expires{' '}
                <time dateTime={transfer.expires_at}>{new Date(transfer.expires_at).toLocaleString()}</time>
              </p>
              <label>
                <span className="label-text">Claim link</span>
                <input readOnly value={shareUrl} onFocus={event => event.currentTarget.select()} />
              </label>
              <div className="share-actions">
                <a
                  className="button-like"
                  href={`https://wa.me/?text=${encodeURIComponent(`${shareText} — ${shareUrl}`)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Share on WhatsApp
                </a>
                <a
                  className="button-like"
                  href={`mailto:?subject=${encodeURIComponent(shareText)}&body=${encodeURIComponent(`Claim your ticket: ${shareUrl}`)}`}
                >
                  Send by email
                </a>
                <button type="button" className="secondary" onClick={copyLink}>Copy link</button>
                {typeof navigator !== 'undefined' && typeof navigator.share === 'function' && (
                  <button type="button" className="secondary" onClick={nativeShare}>Share…</button>
                )}
              </div>
              {shared && <p role="status" className="text-sm">{shared}</p>}
              <div className="form-actions">
                <button type="button" className="danger" onClick={cancelTransfer} disabled={busyAny}>
                  {busy === 'cancel-transfer' ? 'Cancelling…' : 'Cancel transfer link'}
                </button>
              </div>
            </div>
          )}
        </section>

        {/* ── Benefits ── */}
        <section className="panel ticket-benefits" aria-labelledby="benefits-title">
          <h2 id="benefits-title" className="panel-title">Included with this ticket</h2>
          {geofenceLocked && (
            <div className="form-actions">
              <button className="secondary sm" onClick={refreshWithLocation} disabled={busyAny}>
                {busy === 'location' ? 'Checking…' : 'Check my location'}
              </button>
            </div>
          )}
          {!detail.entitlements.length ? (
            <p className="text-muted text-sm">This ticket has no benefits attached.</p>
          ) : (
            <ul className="benefit-list">
              {detail.entitlements.map(entitlement => {
                const statusLabel = entitlement.status === 'available' ? 'Available'
                  : entitlement.status === 'redeemed' ? 'Redeemed'
                  : entitlement.status === 'expired' ? 'Expired'
                  : entitlement.status === 'revoked' ? 'Withdrawn'
                  : 'Locked';
                const statusGlyph = entitlement.status === 'available' ? '●'
                  : entitlement.status === 'redeemed' ? '✓'
                  : entitlement.status === 'expired' ? '⌛'
                  : entitlement.status === 'revoked' ? '⊘'
                  : '🔒';
                const statusChip = entitlement.status === 'available' ? 'chip-green'
                  : entitlement.status === 'redeemed' ? 'chip-teal'
                  : entitlement.status === 'revoked' ? 'chip-red'
                  : 'chip-default';
                return (
                  <li key={entitlement.id} className="benefit">
                    <div className="benefit-head">
                      <strong>{entitlement.name}</strong>
                      <span className={`chip ${statusChip}`}>
                        <span aria-hidden="true">{statusGlyph}</span> {statusLabel}
                      </span>
                    </div>
                    {entitlement.description && <p className="text-sm text-muted">{entitlement.description}</p>}
                    {entitlement.locked_reason && <p className="text-sm benefit-reason">{entitlement.locked_reason}</p>}
                    <p className="text-sm text-muted">
                      {entitlement.remaining} of {entitlement.quantity} remaining
                      {entitlement.requires_staff_validation ? ' · staff validates the code' : ''}
                      {entitlement.min_attendance_minutes ? ` · needs ${entitlement.min_attendance_minutes} minutes at the event` : ''}
                    </p>
                    {entitlement.redemption_ends_at && entitlement.status !== 'redeemed' && (
                      <p className="text-sm text-muted">
                        Redeem by <time dateTime={entitlement.redemption_ends_at}>{new Date(entitlement.redemption_ends_at).toLocaleString()}</time>
                      </p>
                    )}
                    {entitlement.status === 'available' && (
                      <div className="form-actions">
                        <button className="accent sm" onClick={() => redeem(entitlement)} disabled={busyAny}>
                          {busy === 'location' ? 'Preparing…' : `Redeem ${entitlement.name}`}
                        </button>
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        {/* ── Redemption credential ── */}
        {redemption && (
          <section className="panel redemption-panel" aria-labelledby="redemption-title">
            <h2 id="redemption-title" className="panel-title">Redeem {redemption.entitlement}</h2>
            {secondsLeft !== null && secondsLeft <= 0 ? (
              <>
                <p role="alert" className="error">This code has expired. Redeem again for a new one.</p>
                <div className="form-actions">
                  <button className="secondary" onClick={() => setRedemption(null)}>Close</button>
                </div>
              </>
            ) : (
              <>
                {redemption.credential.qr_payload && (
                  <QrImage value={redemption.credential.qr_payload} alt={`Redemption QR code for ${redemption.entitlement}`} />
                )}
                {redemption.credential.code && (
                  <div className="redemption-code">
                    <span className="label-text">Give this code to staff</span>
                    <output aria-label={`Redemption code ${redemption.credential.code.split('').join(' ')}`}>
                      {redemption.credential.code}
                    </output>
                  </div>
                )}
                {secondsLeft !== null && (
                  <p className="text-sm text-muted">
                    Expires in {Math.floor(secondsLeft / 60)}:{String(secondsLeft % 60).padStart(2, '0')}
                  </p>
                )}
                <p className="text-sm text-muted">Staff will confirm this code once. It cannot be reused.</p>
                <div className="form-actions">
                  <button className="secondary" onClick={() => setRedemption(null)}>Done</button>
                </div>
              </>
            )}
          </section>
        )}
      </div>
    </div>
  );
}
