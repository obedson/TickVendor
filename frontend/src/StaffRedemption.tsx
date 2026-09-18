/** The door-side validator: one field, one confirmation, no second chances.
 *
 * A staff member either types the four-character code the attendee is showing or points a
 * keyboard-wedge barcode scanner at the redemption QR — such a scanner types the payload and
 * presses Enter, which is exactly what a text field already does, so no camera library is
 * needed. Staff validation is the only path that redeems a staff-validated benefit: this screen
 * never redeems on its own, never retries a submission, and shows whatever the backend decided.
 */

import { useEffect, useRef, useState } from 'react';
import { apiJson, ApiError, getLiveToken } from './api';
import { currentPosition, LocationFailure } from './geolocation';
import { ManagedEventSelector } from './ManagedEventSelector';

type ValidationResult = {
  result: string;
  entitlement: string;
  event: string;
  ticket: string;
  public_id: string;
  attendee: string;
  status: string;
  remaining: number;
  redeemed_at?: string | null;
};

/** Codes are exactly four characters; a QR payload is a longer opaque string. */
const CODE_LENGTH = 4;

function credential(value: string): { code: string } | { qr_payload: string } | { error: string } {
  const trimmed = value.trim();
  if (!trimmed) return { error: 'Enter the code shown by the attendee, or scan their redemption QR.' };
  if (trimmed.length === CODE_LENGTH) return { code: trimmed.toUpperCase() };
  if (trimmed.length < 8) return { error: 'A redemption code is exactly 4 characters. Check the code and try again.' };
  if (trimmed.length > 200) return { error: 'That does not look like a redemption code or QR payload.' };
  return { qr_payload: trimmed };
}

function Validator({ eventId, token }: { eventId: string; token: string }) {
  const [value, setValue] = useState('');
  const [useLocation, setUseLocation] = useState(false);
  const [result, setResult] = useState<ValidationResult | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  // The next attendee is waiting: return focus so a scanner can fire straight away.
  useEffect(() => { input.current?.focus(); }, [result, error]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const parsed = credential(value);
    if ('error' in parsed) { setError(parsed.error); setResult(null); return; }

    setBusy(true);
    setError('');
    setResult(null);
    const body: Record<string, unknown> = { ...parsed };
    if (useLocation) {
      try {
        const point = await currentPosition({ timeout: 10000 });
        body.latitude = point.latitude;
        body.longitude = point.longitude;
        body.accuracy_meters = point.accuracy_meters;
      } catch (failure) {
        setError(failure instanceof LocationFailure
          ? `${failure.message} Turn the location option off to validate without it.`
          : 'This device could not read its location. Turn the location option off to validate without it.');
        setBusy(false);
        return;
      }
    }

    try {
      setResult(await apiJson<ValidationResult>(`events/${eventId}/redemptions/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }, getLiveToken() ?? token));
      setValue('');
    } catch (cause) {
      setError(cause instanceof ApiError
        ? cause.message
        : 'The redemption could not be validated. Check the connection and try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel" aria-labelledby="validator-title">
      <h3 id="validator-title">Validate a benefit</h3>
      <p className="text-sm text-muted">
        Type the 4-character code the attendee is showing, or scan their redemption QR.
        Each code works once and expires quickly, so validate it while they are in front of you.
      </p>

      <form onSubmit={submit} className="stack">
        <label>
          <span className="label-text">Redemption code or QR</span>
          <input
            ref={input}
            value={value}
            onChange={event => setValue(event.target.value)}
            placeholder="A7K3"
            autoComplete="off"
            autoCapitalize="characters"
            spellCheck={false}
            inputMode="text"
            aria-describedby="validator-hint"
          />
        </label>
        <p id="validator-hint" className="text-sm text-muted">
          The code is not case sensitive.
        </p>
        <label className="check">
          <input type="checkbox" checked={useLocation} onChange={event => setUseLocation(event.target.checked)} />
          <span>Include this device's location (needed when the benefit requires the venue)</span>
        </label>
        <div className="form-actions">
          <button type="submit" className="accent" disabled={busy || !value.trim()}>
            {busy ? 'Validating…' : 'Validate redemption'}
          </button>
        </div>
      </form>

      {error && <p role="alert" className="error">{error}</p>}

      {result && (
        <div role="status" className="validation-result">
          <p className="success-msg">
            <span aria-hidden="true">✓</span> {result.entitlement} redeemed for {result.attendee}.
          </p>
          <dl className="claim-facts">
            <dt>Attendee</dt><dd>{result.attendee}</dd>
            <dt>Event</dt><dd>{result.event}</dd>
            <dt>Ticket</dt><dd>{result.ticket} · {result.public_id}</dd>
            <dt>Benefit</dt><dd>{result.entitlement}</dd>
            <dt>Ticket benefit status</dt><dd>{result.status}</dd>
            <dt>Redemptions left on this ticket</dt><dd>{result.remaining}</dd>
            {result.redeemed_at && (
              <>
                <dt>Validated at</dt>
                <dd><time dateTime={result.redeemed_at}>{new Date(result.redeemed_at).toLocaleString()}</time></dd>
              </>
            )}
          </dl>
          <p className="text-sm text-muted">Hand over the benefit now. The code cannot be used again.</p>
        </div>
      )}
    </section>
  );
}

export function StaffRedemption({ token, communityId }: { token: string; communityId: string }) {
  return (
    <div className="management-screen">
      <div className="page-header">
        <div className="page-header-text">
          <p className="eyebrow">Operations</p>
          <h1>Benefit validation</h1>
          <p>Confirm the benefits attendees redeem at the venue.</p>
        </div>
      </div>
      <ManagedEventSelector token={token} communityId={communityId}>
        {eventId => <Validator eventId={eventId} token={token} />}
      </ManagedEventSelector>
    </div>
  );
}
