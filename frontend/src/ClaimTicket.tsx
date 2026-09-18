/** The claim page behind every ticket transfer link (`/claim/<token>`).
 *
 * The link is the credential, so this page is reachable signed out: a recipient who has never
 * used TickVendor must be able to see what they are being offered before creating an account.
 * The preview endpoint is anonymous-safe by design and never names the current holder, so the
 * page shows event context only. The claim itself is a single authenticated POST that the
 * backend performs atomically under a row lock — this page never tries to decide who holds the
 * ticket, and it never retries a claim on its own.
 */

import { useEffect, useState, type ReactNode } from 'react';
import { apiJson, ApiError, getLiveToken } from './api';
import { TRANSFER_STATUS_LABEL, type TransferPreview } from './tickets';

type Props = {
  claimToken: string;
  token?: string;
  authenticated: boolean;
  /** Rendered in place when the recipient is signed out, so the claim link survives sign-in. */
  auth: ReactNode;
  onClaimed: () => void;
  onGoToTickets: () => void;
};

export function ClaimTicket({ claimToken, token, authenticated, auth, onClaimed, onGoToTickets }: Props) {
  const [preview, setPreview] = useState<TransferPreview | null>(null);
  const [loadError, setLoadError] = useState('');
  const [claimError, setClaimError] = useState('');
  const [loading, setLoading] = useState(true);
  const [claiming, setClaiming] = useState(false);
  const [claimed, setClaimed] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setLoadError('');
    apiJson<TransferPreview>(`tickets/transfers/${encodeURIComponent(claimToken)}`, {}, getLiveToken() ?? token)
      .then(data => { if (active) setPreview(data); })
      .catch((cause: unknown) => {
        if (!active) return;
        setLoadError(cause instanceof ApiError && cause.status === 404
          ? 'This transfer link is not valid. Ask the sender for a new link.'
          : cause instanceof Error ? cause.message : 'Unable to open this transfer link.');
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [claimToken, token]);

  const claim = async () => {
    setClaiming(true);
    setClaimError('');
    try {
      await apiJson(`tickets/transfers/${encodeURIComponent(claimToken)}/claim`, { method: 'POST' }, getLiveToken() ?? token);
      setClaimed(true);
      onClaimed();
    } catch (cause) {
      setClaimError(cause instanceof ApiError
        ? cause.message
        : 'The ticket could not be claimed. Ask the sender to send it again.');
    } finally {
      setClaiming(false);
    }
  };

  const startsAt = preview?.event_starts_at ? new Date(preview.event_starts_at) : null;

  return (
    <main className="claim-page">
      <section className="panel" aria-labelledby="claim-title">
        <div className="auth-brand">
          <div className="auth-brand-logo" aria-hidden="true">TV</div>
          <span className="auth-brand-name">TickVendor</span>
        </div>

        {loading && <p role="status" className="text-muted">Opening your ticket…</p>}

        {!loading && loadError && (
          <>
            <h1 id="claim-title">Ticket link unavailable</h1>
            <p role="alert" className="error">{loadError}</p>
          </>
        )}

        {!loading && !loadError && preview && (
          <>
            <p className="eyebrow">Ticket transfer</p>
            <h1 id="claim-title">{preview.event_title || 'A ticket is waiting for you'}</h1>
            <dl className="claim-facts">
              {preview.ticket_type_name && (
                <>
                  <dt>Ticket</dt>
                  <dd>{preview.ticket_type_name}</dd>
                </>
              )}
              {startsAt && (
                <>
                  <dt>Starts</dt>
                  <dd><time dateTime={preview.event_starts_at ?? undefined}>{startsAt.toLocaleString()}</time></dd>
                </>
              )}
              <dt>Link status</dt>
              <dd>{TRANSFER_STATUS_LABEL[preview.status] ?? preview.status}</dd>
              {preview.expires_at && (
                <>
                  <dt>Link expires</dt>
                  <dd><time dateTime={preview.expires_at}>{new Date(preview.expires_at).toLocaleString()}</time></dd>
                </>
              )}
            </dl>

            {claimed ? (
              <>
                <p role="status" className="success-msg">Ticket claimed. It is now in My Tickets.</p>
                <div className="form-actions">
                  <button className="accent" onClick={onGoToTickets}>Open My Tickets</button>
                </div>
              </>
            ) : preview.claimable ? (
              <>
                {claimError && <p role="alert" className="error">{claimError}</p>}
                {authenticated ? (
                  <>
                    <p className="text-muted text-sm">
                      Claiming moves this ticket to your wallet. The sender keeps their account — only
                      the ticket changes hands.
                    </p>
                    <div className="form-actions">
                      <button className="accent" onClick={claim} disabled={claiming}>
                        {claiming ? 'Claiming…' : 'Claim ticket'}
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <p className="info-msg">
                      Sign in or create an account to claim this ticket. You will come straight back
                      to this page.
                    </p>
                    {auth}
                  </>
                )}
              </>
            ) : (
              <p role="alert" className="error">
                {preview.status === 'claimed'
                  ? 'This ticket has already been claimed. If it was not you, ask the sender to send it again.'
                  : preview.status === 'expired'
                    ? 'This transfer link has expired. Ask the sender to send the ticket again.'
                    : 'This transfer link is no longer active. Ask the sender to send the ticket again.'}
              </p>
            )}
          </>
        )}
      </section>
    </main>
  );
}
