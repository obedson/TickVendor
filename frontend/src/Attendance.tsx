import { useEffect, useState } from 'react';
import { apiJson, ApiError, getLiveToken } from './api';
import { EmptyState } from './AppShell';
import { currentPosition } from './geolocation';
import type { OfflineTicket } from './offlineTickets';

type AttendanceProps = { token: string; tickets: OfflineTicket[] };
type Candidate = { participant_id: string; display_name?: string };
type CheckInResult = { status: string; message?: string };
type EventAttendanceSettings = { geofence_enabled: boolean; geofence_radius_meters?: number; required_verification_methods: string[] };

export function Attendance({ token, tickets }: AttendanceProps) {
  const [ticket, setTicket] = useState<OfflineTicket | null>(tickets[0] ?? null);
  const [checkInStatus, setCheckInStatus] = useState('');
  const [busy, setBusy] = useState(false);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [peerMessage, setPeerMessage] = useState('');
  const [confirmedIds, setConfirmedIds] = useState<Set<string>>(new Set());
  const [error, setError] = useState('');
  const [geoStatus, setGeoStatus] = useState<'idle' | 'requesting' | 'granted' | 'failed'>('idle');
  const [geoMessage, setGeoMessage] = useState('');

  const liveToken = () => getLiveToken() ?? token;

  const loadCandidates = async () => {
    if (!ticket?.event_id) return;
    setPeerMessage('');
    try {
      setCandidates(await apiJson<Candidate[]>(`events/${ticket.event_id}/attendance/peer-candidates`, {}, liveToken()));
    } catch (cause) {
      setCandidates([]);
      setPeerMessage(cause instanceof ApiError && cause.status === 403
        ? 'Peer confirmation is available after you meet this event’s attendance eligibility requirements.'
        : cause instanceof ApiError && cause.status === 409 ? 'Peer confirmation is disabled for this event.'
        : cause instanceof Error ? cause.message : 'Unable to load peer confirmations.');
    }
  };

  useEffect(() => {
    setCandidates([]);
    setCheckInStatus('');
    setError('');
    setConfirmedIds(new Set());
    loadCandidates();
  }, [ticket, token]);

  const checkIn = async () => {
    if (!ticket?.event_id) return;
    setBusy(true);
    setError('');
    setCheckInStatus('');
    setGeoMessage('');

    const submit = (latitude?: number, longitude?: number, accuracy?: number) => {
      apiJson<CheckInResult>(`events/${ticket.event_id}/attendance/check-in`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticket_id: ticket.id!, latitude, longitude, accuracy_meters: accuracy }),
      }, liveToken())
        .then(data => {
          setCheckInStatus(`Check-in recorded. Status: ${data.status}`);
          loadCandidates();
        })
        .catch((e: Error) => setError(e instanceof ApiError ? e.message : e.message))
        .finally(() => setBusy(false));
    };

    let settings: EventAttendanceSettings;
    try {
      settings = await apiJson<EventAttendanceSettings>(`events/${ticket.event_id}`, {}, liveToken());
    } catch {
      // The backend remains authoritative if event settings cannot be refreshed.
      submit();
      return;
    }

    if (!settings.geofence_enabled) {
      setGeoStatus('idle');
      submit();
      return;
    }

    if (!navigator.geolocation) {
      setGeoStatus('failed');
      setGeoMessage('Location is not supported by this browser. Use event QR or organizer verification.');
      setBusy(false);
      return;
    }

    setGeoStatus('requesting');
    try {
      const position = await currentPosition({ targetAccuracy: settings.geofence_radius_meters });
      setGeoStatus('granted');
      submit(position.latitude, position.longitude, position.accuracy_meters);
    } catch (failure) {
      setGeoStatus('failed');
      setGeoMessage(`${failure instanceof Error ? failure.message : 'Location could not be requested.'} Ask event staff for an allowed verification method.`);
      setBusy(false);
    }
  };

  const confirm = async (subject_id: string) => {
    if (!ticket?.event_id) return;
    setBusy(true);
    setError('');
    try {
      await apiJson<unknown>(`events/${ticket.event_id}/attendance/peer-confirmations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ subject_id, confirmed: true }),
      }, liveToken());
      setConfirmedIds(prev => new Set([...prev, subject_id]));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Confirmation failed');
    } finally {
      setBusy(false);
    }
  };

  if (!tickets.length) {
    return (
      <div>
        <div className="page-header">
          <div className="page-header-text">
            <p className="eyebrow">Attendance</p>
            <h1>Check in</h1>
          </div>
        </div>
        <EmptyState
          title="No tickets available"
          description="Acquire a ticket for an event before checking in. Your tickets will appear here."
        />
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <div className="page-header-text">
          <p className="eyebrow">Attendance</p>
          <h1>Check in</h1>
          <p>Record your attendance at an event using your ticket.</p>
        </div>
      </div>

      <div className="content-with-aside">
        {/* Check-in panel */}
        <div className="panel">
          <h2 style={{ fontSize: '1.1rem', marginBottom: '1rem' }}>Event check-in</h2>

          <label>
            <span className="label-text">Select your ticket</span>
            <select
              value={ticket?.id ?? ''}
              onChange={e => setTicket(tickets.find(item => item.id === e.target.value) ?? null)}
            >
              {tickets.map(item => (
                <option key={item.id} value={item.id}>
                  {item.event_title || item.public_id}
                </option>
              ))}
            </select>
          </label>

          {ticket && (
            <div style={{ padding: '.75rem 1rem', background: 'var(--tv-surface-sunken)', borderRadius: 'var(--tv-radius-md)', marginBottom: '1rem', fontSize: '.875rem' }}>
              <strong>{ticket.event_title || ticket.public_id}</strong>
              {ticket.event_starts_at && (
                <p style={{ margin: '.25rem 0 0', color: 'var(--tv-muted)' }}>
                  {new Date(ticket.event_starts_at).toLocaleString()}
                </p>
              )}
              {ticket.venue_name && <p style={{ margin: '.1rem 0 0', color: 'var(--tv-muted)' }}>📍 {ticket.venue_name}</p>}
            </div>
          )}

          {geoStatus === 'requesting' && (
            <p className="info-msg" style={{ marginBottom: '1rem' }}>Requesting your location for GPS verification…</p>
          )}
          {geoStatus === 'failed' && geoMessage && (
            <p role="alert" className="info-msg" style={{ marginBottom: '1rem' }}>{geoMessage}</p>
          )}

          {checkInStatus && <p role="status" className="success-msg" style={{ marginBottom: '1rem' }}>{checkInStatus}</p>}
          {error && <p role="alert" className="error" style={{ marginBottom: '1rem' }}>{error}</p>}

          <button
            className="accent"
            disabled={busy || !ticket}
            onClick={checkIn}
            style={{ width: '100%' }}
          >
            {busy ? 'Checking in…' : 'Check in now'}
          </button>

          <p style={{ fontSize: '.8rem', color: 'var(--tv-muted)', marginTop: '.75rem', textAlign: 'center' }}>
            Location is requested only for GPS-verified events and is not stored continuously.
          </p>
        </div>

        {/* Peer confirmations panel */}
        <div className="panel">
          <h2 style={{ fontSize: '1.1rem', marginBottom: '1rem' }}>Peer confirmations</h2>
          <p style={{ fontSize: '.875rem', color: 'var(--tv-muted)', marginBottom: '1rem' }}>
            Confirm attendance for other participants at this event.
          </p>

          {peerMessage && <p role="status" className="info-msg">{peerMessage}</p>}
          {!candidates.length ? (
            <p className="empty">No peer confirmations available right now.</p>
          ) : (
            <div className="stack">
              {candidates.map(candidate => (
                <div
                  key={candidate.participant_id}
                  style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '.75rem', padding: '.65rem .85rem', background: 'var(--tv-surface-sunken)', borderRadius: 'var(--tv-radius-md)' }}
                >
                  <span style={{ fontSize: '.875rem', fontWeight: 600 }}>
                    {candidate.display_name || candidate.participant_id.slice(0, 8) + '…'}
                  </span>
                  {confirmedIds.has(candidate.participant_id) ? (
                    <span className="chip chip-green">Confirmed ✓</span>
                  ) : (
                    <button
                      className="secondary sm"
                      disabled={busy}
                      onClick={() => confirm(candidate.participant_id)}
                    >
                      Confirm
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
