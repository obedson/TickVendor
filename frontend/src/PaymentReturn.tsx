import { useEffect, useState } from 'react';
import { apiJson, ApiError } from './api';

type PaymentReturnProps = {
  token: string;
  paymentId: string | null;
  providerReference: string | null;
};
type PaymentState = 'checking' | 'pending' | 'successful' | 'failed' | 'cancelled' | 'unknown' | 'error';

export function PaymentReturn({ token, paymentId, providerReference }: PaymentReturnProps) {
  const [state, setState] = useState<PaymentState>('checking');
  const [details, setDetails] = useState<any>(null);
  const [resolvedPaymentId, setResolvedPaymentId] = useState(paymentId);
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [available, setAvailable] = useState<number | null>(null);

  const check = () => {
    const request = providerReference && !resolvedPaymentId
      ? apiJson<any>('payments/verify-reference', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ provider_reference: providerReference }),
        }, token)
      : resolvedPaymentId
        ? apiJson<any>(`payments/${encodeURIComponent(resolvedPaymentId)}`, {}, token)
        : Promise.reject(new ApiError(404, 'Payment not found', 'unexpected'));
    request
      .then(data => {
        setDetails(data);
        if (data.payment_id) setResolvedPaymentId(data.payment_id);
        setState(
          data.status === 'success' || data.status === 'successful' ? 'successful' :
          // A released reservation is a finished story of its own, not a payment still to come.
          data.status === 'cancelled' ? 'cancelled' :
          data.status === 'failed' ? 'failed' : 'pending'
        );
      })
      .catch(e => setState(e instanceof ApiError && e.status === 404 ? 'unknown' : 'error'));
  };

  useEffect(() => { check(); }, [resolvedPaymentId, providerReference, token, attempt]);

  useEffect(() => {
    if (state !== 'pending' || attempt >= 8) return;
    const timer = window.setTimeout(() => setAttempt(v => v + 1), 2500);
    return () => window.clearTimeout(timer);
  }, [state, attempt]);

  /**
   * Ask the server to release the reservation behind this checkout.
   *
   * The provider tells the server whether the charge actually settled before anything is released,
   * so a click that races a successful payment cannot cancel a paid order — the server answers that
   * this one is not releasable and the status is read back instead. A payment still in flight is
   * left alone for the existing reservation timeout to release, which stays the fallback.
   */
  const release = async () => {
    setBusy(true);
    setNotice('');
    try {
      const result = await apiJson<any>('payments/cancel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(resolvedPaymentId
          ? { payment_id: resolvedPaymentId }
          : { provider_reference: providerReference }),
      }, token);
      setDetails(result);
      if (!result.released) {
        setState('checking');
        check();
        return;
      }
      setState('cancelled');
      // Those tickets went back on sale, so the event's remaining availability has changed.
      if (result.event_id) {
        apiJson<{ availability: number }[]>(`events/${result.event_id}/ticket-types`, {}, token)
          .then(types => setAvailable(types.reduce((total, type) => total + type.availability, 0)))
          .catch(() => {});
      }
    } catch (err) {
      setNotice(err instanceof ApiError ? err.message : 'The reservation could not be released.');
      setState('checking');
      check();
    } finally {
      setBusy(false);
    }
  };

  // Offered wherever a reservation can still be held. A payment that already succeeded is never
  // among these states, so the button cannot be used to give up a ticket that was paid for.
  const canRelease = Boolean(resolvedPaymentId || providerReference)
    && (state === 'pending' || state === 'failed' || state === 'unknown' || state === 'error');
  // The states where nothing more is expected to arrive on its own.
  const holdsReservation = state === 'failed' || state === 'unknown' || state === 'error';

  const stateConfig: Record<PaymentState, { icon: string; title: string; color: string; message: string }> = {
    checking: { icon: '⏳', title: 'Checking payment…', color: 'var(--tv-muted)', message: 'Verifying your payment status with the provider.' },
    pending: { icon: '⏳', title: 'Payment processing', color: 'var(--tv-warning)', message: 'Your payment is being processed. This may take a moment.' },
    successful: { icon: '✅', title: 'Payment confirmed!', color: 'var(--tv-success)', message: 'Your ticket has been issued and is available in My Tickets.' },
    failed: { icon: '❌', title: 'Payment not completed', color: 'var(--tv-danger)', message: 'The payment was not completed. No charge has been made.' },
    cancelled: { icon: '🚫', title: 'Payment cancelled', color: 'var(--tv-muted)', message: 'No charge was made, and your ticket reservation has been released.' },
    unknown: { icon: '❓', title: 'Payment not found', color: 'var(--tv-muted)', message: 'This payment reference could not be found. Contact support if you were charged.' },
    error: { icon: '⚠️', title: 'Unable to verify', color: 'var(--tv-danger)', message: 'Unable to check payment status. Please try again or contact support.' },
  };

  const config = stateConfig[state];

  return (
    <main className="auth">
      <section className="panel" aria-labelledby="payment-title" style={{ textAlign: 'center' }}>
        <div className="auth-brand" style={{ justifyContent: 'center' }}>
          <div className="auth-brand-logo" aria-hidden="true">TV</div>
          <span className="auth-brand-name">TickVendor</span>
        </div>

        <div style={{ fontSize: '3.5rem', margin: '1rem 0 .5rem' }} aria-hidden="true">{config.icon}</div>
        <h1 id="payment-title" style={{ color: config.color, fontSize: '1.5rem' }}>{config.title}</h1>
        <p style={{ color: 'var(--tv-muted)', marginBottom: '1.25rem' }}>{config.message}</p>

        {state === 'pending' && attempt < 8 && (
          <p role="status" className="info-msg" style={{ marginBottom: '1rem' }}>
            Checking again… ({attempt + 1}/8)
          </p>
        )}

        {(details?.provider_reference || details?.order_reference) && (
          <p style={{ fontSize: '.875rem', color: 'var(--tv-muted)', marginBottom: '1rem' }}>
            Reference: <code>{details.provider_reference || details.order_reference}</code>
          </p>
        )}

        {state === 'cancelled' && available !== null && (
          <p className="text-sm text-muted" style={{ marginBottom: '1rem' }}>
            {available === 1 ? '1 ticket is' : `${available} tickets are`} available again for this event.
          </p>
        )}

        {/* A payment that did not complete still holds the reservation until it expires, so saying
            only "no charge was made" would read as though nothing were outstanding. A payment that
            is merely still in flight is left to the state message above; offering the release under
            it is enough, without telling a buyer mid-charge to give up. */}
        {holdsReservation && !busy && (
          <p className="text-sm text-muted" style={{ marginBottom: '1rem' }}>
            Your ticket reservation is still held. Cancel the payment to release it now; otherwise it
            is released automatically when it expires.
          </p>
        )}

        {notice && <p role="alert" className="error" style={{ marginBottom: '1rem' }}>{notice}</p>}

        <div className="form-actions" style={{ justifyContent: 'center' }}>
          {state === 'successful' && (
            <button className="accent" onClick={() => window.location.assign('/')}>View my tickets</button>
          )}
          {(state === 'failed' || state === 'error' || state === 'unknown' || state === 'cancelled') && (
            <button className="secondary" onClick={() => window.location.assign('/')}>Back to TickVendor</button>
          )}
          {state === 'error' && (
            <button className="accent" onClick={() => { setState('checking'); setAttempt(0); check(); }}>Try again</button>
          )}
          {canRelease && (
            <button className="danger" disabled={busy} onClick={release}>
              {busy ? 'Releasing…' : 'Cancel payment'}
            </button>
          )}
        </div>
      </section>
    </main>
  );
}
