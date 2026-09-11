import { useEffect, useState } from 'react';
import { apiJson, ApiError } from './api';

type PaymentReturnProps = {
  token: string;
  paymentId: string | null;
  providerReference: string | null;
};
type PaymentState = 'checking' | 'pending' | 'successful' | 'failed' | 'unknown' | 'error';

export function PaymentReturn({ token, paymentId, providerReference }: PaymentReturnProps) {
  const [state, setState] = useState<PaymentState>('checking');
  const [details, setDetails] = useState<any>(null);
  const [resolvedPaymentId, setResolvedPaymentId] = useState(paymentId);
  const [attempt, setAttempt] = useState(0);

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

  const stateConfig: Record<PaymentState, { icon: string; title: string; color: string; message: string }> = {
    checking: { icon: '⏳', title: 'Checking payment…', color: 'var(--tv-muted)', message: 'Verifying your payment status with the provider.' },
    pending: { icon: '⏳', title: 'Payment processing', color: 'var(--tv-warning)', message: 'Your payment is being processed. This may take a moment.' },
    successful: { icon: '✅', title: 'Payment confirmed!', color: 'var(--tv-success)', message: 'Your ticket has been issued and is available in My Tickets.' },
    failed: { icon: '❌', title: 'Payment not completed', color: 'var(--tv-danger)', message: 'The payment was not completed. No charge has been made.' },
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

        <div className="form-actions" style={{ justifyContent: 'center' }}>
          {state === 'successful' && (
            <button className="accent" onClick={() => window.location.assign('/')}>View my tickets</button>
          )}
          {(state === 'failed' || state === 'error' || state === 'unknown') && (
            <button className="secondary" onClick={() => window.location.assign('/')}>Back to TickVendor</button>
          )}
          {state === 'error' && (
            <button className="accent" onClick={() => { setState('checking'); setAttempt(0); check(); }}>Try again</button>
          )}
        </div>
      </section>
    </main>
  );
}
