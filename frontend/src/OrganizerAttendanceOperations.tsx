import { useState } from 'react';
import { apiJson, ApiError, getLiveToken } from './api';

type Validation = { result: string; ticket?: { public_id: string; attendee_id: string; status: string } | null };

export function OrganizerAttendanceOperations({ token, eventId }: { token: string; eventId: string }) {
  const [qr, setQr] = useState('');
  const [result, setResult] = useState<Validation | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const scan = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!eventId) { setError('No event selected. Select an event from the Events section first.'); return; }
    setBusy(true); setError(''); setResult(null);
    try {
      const data = await apiJson<Validation>(`events/${eventId}/tickets/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ qr_token: qr }),
      }, getLiveToken() ?? token);
      setResult(data);
      setQr('');
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Unable to validate ticket');
    } finally { setBusy(false); }
  };

  const resultColor = result?.result === 'valid' ? 'chip-green' : result?.result === 'already_used' ? 'chip-yellow' : result ? 'chip-red' : '';

  return (
    <div>
      <div className="page-header">
        <div className="page-header-text">
          <p className="eyebrow">Operations</p>
          <h1>Ticket check-in</h1>
          <p>Validate attendee tickets at the event entrance. Validation is server-side and atomic.</p>
        </div>
      </div>

      <div style={{ display: 'grid', gap: '1.25rem', gridTemplateColumns: 'minmax(0,1fr) minmax(0,320px)' }}>
        <div className="panel">
          <h2 style={{ fontSize: '1.1rem', marginBottom: '1rem' }}>Scan QR code</h2>
          <p style={{ fontSize: '.875rem', color: 'var(--tv-muted)', marginBottom: '1.25rem' }}>
            Enter the QR token from the attendee's ticket. In a production setup, use a barcode scanner that types the value into this field.
          </p>

          {!eventId && (
            <p className="info-msg" style={{ marginBottom: '1rem' }}>Select an event from the Events section to enable ticket validation.</p>
          )}

          <form onSubmit={scan}>
            <label>
              <span className="label-text">QR token</span>
              <input
                aria-label="QR token"
                required
                minLength={32}
                maxLength={128}
                value={qr}
                onChange={e => setQr(e.target.value)}
                placeholder="Paste or scan QR token here…"
                autoFocus
                autoComplete="off"
              />
            </label>
            <div className="form-actions">
              <button type="submit" className="accent" disabled={busy || !eventId} style={{ width: '100%' }}>
                {busy ? 'Validating…' : 'Validate ticket'}
              </button>
            </div>
          </form>

          {error && <p role="alert" className="error" style={{ marginTop: '1rem' }}>{error}</p>}
        </div>

        <div className="panel">
          <h2 style={{ fontSize: '1.1rem', marginBottom: '1rem' }}>Validation result</h2>
          {!result ? (
            <p className="text-muted text-sm">Scan a ticket to see the result here.</p>
          ) : (
            <div role="status">
              <div style={{ textAlign: 'center', padding: '1.5rem 1rem' }}>
                <span style={{ fontSize: '3rem' }} aria-hidden="true">
                  {result.result === 'valid' ? '✅' : result.result === 'already_used' ? '⚠️' : '❌'}
                </span>
                <p style={{ marginTop: '.75rem', marginBottom: '.5rem' }}>
                  <span className={`chip ${resultColor}`} style={{ fontSize: '.9rem', padding: '.35rem .85rem' }}>
                    {result.result === 'valid' ? 'Valid — entry granted' : result.result === 'already_used' ? 'Already used' : result.result}
                  </span>
                </p>
                {result.ticket && (
                  <div style={{ marginTop: '1rem', fontSize: '.875rem', color: 'var(--tv-muted)' }}>
                    <p>Ticket: <code>{result.ticket.public_id}</code></p>
                    <p>Status: {result.ticket.status}</p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
