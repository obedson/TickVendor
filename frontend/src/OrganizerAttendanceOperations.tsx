import { useEffect, useRef, useState } from 'react';
import './management.css';
import { apiJson, ApiError, getLiveToken } from './api';

type Validation = { result: string; ticket?: { public_id: string; attendee_id: string; status: string } | null };
type ScannerControls = { stop: () => void };
type DetectedBarcode = { rawValue: string };
type BarcodeDetectorInstance = { detect: (source: HTMLVideoElement) => Promise<DetectedBarcode[]> };
type BarcodeDetectorConstructor = new (options: { formats: string[] }) => BarcodeDetectorInstance;
type RosterItem = {
  attendance_id: string | null;
  participant_id: string;
  display_name: string;
  email: string;
  ticket_statuses: string[];
  attendance_status: string;
  verification_methods: string[];
  flagged_for_review: boolean;
  location_evidence: LocationEvidence[];
  latest_location_attempt: LocationEvidence | null;
};

type LocationEvidence = {
  latitude: number; longitude: number; accuracy_meters: number | null;
  distance_meters: number | null; radius_meters?: number | null; max_accuracy_meters?: number | null;
  outcome: string; operation: string; recorded_at: string;
};

function LocationReading({ value }: { value: LocationEvidence }) {
  const color = value.outcome === 'verified' ? 'chip-green'
    : value.outcome === 'outside_geofence' ? 'chip-red' : 'chip-yellow';
  return <div className="text-sm">
    <span className={`chip ${color}`}>{value.operation}: {value.outcome.replaceAll('_', ' ')}</span><br />
    Coordinates: {value.latitude.toFixed(6)}, {value.longitude.toFixed(6)}<br />
    Distance from venue: {value.distance_meters == null ? 'Not available' : `${value.distance_meters.toFixed(1)} m`}<br />
    Device accuracy: {value.accuracy_meters == null ? 'Not supplied' : `±${value.accuracy_meters.toFixed(1)} m`}
    {value.radius_meters != null && <> · Allowed radius: {value.radius_meters} m</>}<br />
    {value.max_accuracy_meters != null && <>Automatic accuracy threshold: ±{value.max_accuracy_meters} m<br /></>}
    <time dateTime={value.recorded_at}>{new Date(value.recorded_at).toLocaleString()}</time>
  </div>;
}

export function OrganizerAttendanceOperations({ token, eventId }: { token: string; eventId: string }) {
  const [qr, setQr] = useState('');
  const [result, setResult] = useState<Validation | null>(null);
  const [error, setError] = useState('');
  const [cameraError, setCameraError] = useState('');
  const [busy, setBusy] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [roster, setRoster] = useState<RosterItem[]>([]);
  const [rosterLoading, setRosterLoading] = useState(false);
  const [reviewReasons, setReviewReasons] = useState<Record<string, string>>({});
  const [organizerVerificationEnabled, setOrganizerVerificationEnabled] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const controlsRef = useRef<ScannerControls | null>(null);
  const acceptingScanRef = useRef(false);
  const detectingRef = useRef(false);
  const liveToken = () => getLiveToken() ?? token;

  const loadRoster = async () => {
    if (!eventId) { setRoster([]); return; }
    setRosterLoading(true);
    try {
      setRoster(await apiJson<RosterItem[]>(`events/${eventId}/attendance/roster`, {}, liveToken()));
    } catch {
      setRoster([]);
    } finally {
      setRosterLoading(false);
    }
  };

  useEffect(() => {
    loadRoster();
    if (eventId) {
      apiJson<{ organizer_verification_enabled: boolean }>(`events/${eventId}`, {}, liveToken())
        .then(event => setOrganizerVerificationEnabled(event.organizer_verification_enabled))
        .catch(() => setOrganizerVerificationEnabled(false));
    }
    return () => controlsRef.current?.stop();
  }, [eventId, token]);

  const stopCamera = () => {
    controlsRef.current?.stop();
    controlsRef.current = null;
    acceptingScanRef.current = false;
    setScanning(false);
  };

  const validateToken = async (value: string) => {
    if (!eventId) { setError('No event selected. Select an event from the Events section first.'); return; }
    setBusy(true); setError(''); setResult(null);
    try {
      const data = await apiJson<Validation>(`events/${eventId}/tickets/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ qr_token: value }),
      }, liveToken());
      setResult(data);
      setQr('');
      await loadRoster();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Unable to validate ticket');
    } finally { setBusy(false); }
  };

  const scan = async (e: React.FormEvent) => {
    e.preventDefault();
    await validateToken(qr);
  };

  const startCamera = async () => {
    if (!eventId) { setError('No event selected. Select an event from the Events section first.'); return; }
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraError('Camera scanning is not supported by this browser. Paste the QR token or use a hardware scanner.');
      return;
    }
    const Detector = (window as unknown as { BarcodeDetector?: BarcodeDetectorConstructor }).BarcodeDetector;
    if (!Detector) {
      setCameraError('QR camera decoding is not supported by this browser. Paste the QR token or use a hardware scanner.');
      return;
    }
    setCameraError('');
    setScanning(true);
    acceptingScanRef.current = true;
    let stream: MediaStream | null = null;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: { facingMode: { ideal: 'environment' } },
      });
      const activeStream = stream;
      const video = videoRef.current;
      if (!video) throw new Error('Camera preview unavailable');
      video.srcObject = activeStream;
      await video.play();
      const detector = new Detector({ formats: ['qr_code'] });
      const timer = window.setInterval(async () => {
        if (!acceptingScanRef.current || detectingRef.current || video.readyState < 2) return;
        detectingRef.current = true;
        try {
          const [scanResult] = await detector.detect(video);
          if (!scanResult?.rawValue || !acceptingScanRef.current) return;
          acceptingScanRef.current = false;
          setQr(scanResult.rawValue);
          controlsRef.current?.stop();
          controlsRef.current = null;
          setScanning(false);
          void validateToken(scanResult.rawValue);
        } catch {
          // Individual frames can fail to decode while the camera continues scanning.
        } finally {
          detectingRef.current = false;
        }
      }, 250);
      controlsRef.current = {
        stop: () => {
          window.clearInterval(timer);
          activeStream.getTracks().forEach(track => track.stop());
          video.srcObject = null;
        },
      };
    } catch (cause) {
      stream?.getTracks().forEach(track => track.stop());
      stopCamera();
      const name = cause instanceof Error ? cause.name : '';
      setCameraError(name === 'NotAllowedError'
        ? 'Camera permission was denied. Allow camera access, paste the QR token, or use a hardware scanner.'
        : 'The camera could not be started. Paste the QR token or use a hardware scanner.');
    }
  };

  const resultColor = result?.result === 'valid' ? 'chip-green' : result?.result === 'already_used' ? 'chip-yellow' : result ? 'chip-red' : '';

  const verifyAttendance = async (item: RosterItem, approve: boolean) => {
    if (!item.attendance_id) return;
    const reason = reviewReasons[item.attendance_id]?.trim()
      || (approve ? 'Organizer verified from attendance roster' : 'Organizer rejected from attendance roster');
    setBusy(true); setError('');
    try {
      await apiJson(`events/${eventId}/attendance/${item.attendance_id}/organizer-review`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approve, reason }),
      }, liveToken());
      await loadRoster();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Unable to update attendance verification');
    } finally { setBusy(false); }
  };

  return (
    <div className="management-screen">
      <div className="page-header">
        <div className="page-header-text">
          <p className="eyebrow">Operations</p>
          <h1>Ticket check-in</h1>
          <p>Validate attendee tickets at the event entrance. Validation is server-side and atomic.</p>
        </div>
      </div>

      <div className="content-with-aside">
        <div className="panel">
          <h2 style={{ fontSize: '1.1rem', marginBottom: '1rem' }}>Scan QR code</h2>
          <p style={{ fontSize: '.875rem', color: 'var(--tv-muted)', marginBottom: '1.25rem' }}>
            Use this device's camera, paste the QR token, or use a hardware scanner that types into the field.
          </p>

          {!eventId && <p className="info-msg" style={{ marginBottom: '1rem' }}>Select an event from the Events section to enable ticket validation.</p>}

          <div style={{ marginBottom: '1rem' }}>
            {!scanning ? (
              <button type="button" className="secondary" disabled={!eventId || busy} onClick={startCamera} style={{ width: '100%' }}>Open camera scanner</button>
            ) : (
              <button type="button" className="secondary" onClick={stopCamera} style={{ width: '100%' }}>Stop camera</button>
            )}
            <video ref={videoRef} aria-label="QR camera preview" muted playsInline style={{ display: scanning ? 'block' : 'none', width: '100%', marginTop: '.75rem', borderRadius: 'var(--tv-radius-md)', background: '#111' }} />
            {cameraError && <p role="alert" className="info-msg" style={{ marginTop: '.75rem' }}>{cameraError}</p>}
          </div>

          <form onSubmit={scan}>
            <label>
              <span className="label-text">QR token</span>
              <input aria-label="QR token" required minLength={32} maxLength={128} value={qr} onChange={e => setQr(e.target.value)} placeholder="Paste or scan QR token here…" autoComplete="off" />
            </label>
            <div className="form-actions">
              <button type="submit" className="accent" disabled={busy || !eventId} style={{ width: '100%' }}>{busy ? 'Validating…' : 'Validate ticket'}</button>
            </div>
          </form>

          {error && <p role="alert" className="error" style={{ marginTop: '1rem' }}>{error}</p>}
        </div>

        <div className="panel">
          <h2 style={{ fontSize: '1.1rem', marginBottom: '1rem' }}>Validation result</h2>
          {!result ? <p className="text-muted text-sm">Scan a ticket to see the result here.</p> : (
            <div role="status"><div style={{ textAlign: 'center', padding: '1.5rem 1rem' }}>
              <span style={{ fontSize: '3rem' }} aria-hidden="true">{result.result === 'valid' ? '✅' : result.result === 'already_used' ? '⚠️' : '❌'}</span>
              <p style={{ marginTop: '.75rem', marginBottom: '.5rem' }}><span className={`chip ${resultColor}`} style={{ fontSize: '.9rem', padding: '.35rem .85rem' }}>{result.result === 'valid' ? 'Valid — entry granted' : result.result === 'already_used' ? 'Already used' : result.result}</span></p>
              {result.ticket && <div style={{ marginTop: '1rem', fontSize: '.875rem', color: 'var(--tv-muted)' }}><p>Ticket: <code>{result.ticket.public_id}</code></p><p>Status: {result.ticket.status}</p></div>}
            </div></div>
          )}
        </div>
      </div>

      <div className="panel" style={{ marginTop: '1.25rem' }}>
        <h2 style={{ fontSize: '1.1rem', marginBottom: '.25rem' }}>Attendance roster</h2>
        <p className="text-muted text-sm" style={{ marginBottom: '1rem' }}>Ticket holders and attendance-only participants for this event.</p>
        <p className="text-muted text-sm">Coordinates are reported by the participant's device. Distance is measured from the configured venue; accuracy describes uncertainty, not distance. Failed location attempts do not grant admission.</p>
        <button className="secondary" onClick={loadRoster} disabled={rosterLoading || !eventId}>Refresh roster</button>
        {rosterLoading ? <p role="status" className="text-muted">Loading attendance roster…</p> : !roster.length ? <p className="empty">No attendees or ticket holders yet.</p> : (
          <div className="table-wrap"><table className="management-table">
<caption>Event attendance roster</caption>
            <thead><tr><th>Participant</th><th>Ticket</th><th>Attendance</th><th>Verification</th><th>Location evidence</th><th>Organizer action</th></tr></thead>
            <tbody>{roster.map(item => (
              <tr key={item.participant_id}>
                <td data-label="Participant"><strong>{item.display_name}</strong><br /><span className="text-muted text-sm">{item.email}</span></td>
                <td data-label="Ticket">{item.ticket_statuses.length ? item.ticket_statuses.join(', ') : 'No ticket'}</td>
                <td data-label="Attendance">{item.attendance_status}{item.flagged_for_review ? ' ⚠' : ''}</td>
                <td data-label="Verification">{item.verification_methods.length ? item.verification_methods.join(', ') : 'None'}</td>
                <td data-label="Location evidence">
                  {item.latest_location_attempt && <><p>Latest submitted location</p><LocationReading value={item.latest_location_attempt} /></>}
                  {item.location_evidence?.map((value, index) => <LocationReading key={index} value={value} />)}
                  {!item.latest_location_attempt && !item.location_evidence?.length && 'No location submitted'}
                </td>
                <td data-label="Organizer action">
                  {!organizerVerificationEnabled ? 'Organizer verification disabled' : !item.attendance_id ? 'Not checked in' : item.verification_methods.includes('organizer') || item.attendance_status === 'rejected'
                    ? 'Organizer decision recorded' : <div className="stack">
                    <label><span className="sr-only">Reason for {item.display_name}</span><input value={reviewReasons[item.attendance_id] ?? ''} onChange={event => setReviewReasons(current => ({ ...current, [item.attendance_id!]: event.target.value }))} placeholder="Reason (optional)" maxLength={500} /></label>
                    <div className="form-actions"><button className="accent sm" disabled={busy} onClick={() => verifyAttendance(item, true)}>Verify</button><button className="danger sm" disabled={busy} onClick={() => verifyAttendance(item, false)}>Reject</button></div>
                  </div>}
                </td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </div>
    </div>
  );
}
