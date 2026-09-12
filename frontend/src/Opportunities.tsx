import { Fragment, useEffect, useState } from 'react';
import { SponsoredPlacement } from './SponsoredPlacement';
import { apiJson, ApiError } from './api';
import { EmptyState } from './AppShell';
import { PersonalHistory } from './PersonalHistory';

type Opportunity = {
  id: string;
  community_id: string;
  title: string;
  description: string;
  activity_type: string;
  dimension: string;
  starts_at: string;
  ends_at: string;
  location?: string | null;
  capacity?: number | null;
  members_only: boolean;
  status: string;
};
type Registration = {
  id: string;
  opportunity_id: string;
  participant_id: string;
  status: 'registered' | 'completed' | 'verified' | 'rejected';
};

const DIMENSION_COLORS: Record<string, string> = {
  service: 'chip-teal',
  leadership: 'chip-blue',
  community: 'chip-green',
  academic: 'chip-yellow',
};

const REG_STATUS_MAP: Record<string, { label: string; color: string }> = {
  registered: { label: 'Registered', color: 'chip-blue' },
  completed: { label: 'Completed — awaiting verification', color: 'chip-yellow' },
  verified: { label: 'Verified ✓', color: 'chip-green' },
  rejected: { label: 'Not approved', color: 'chip-red' },
};

export function Opportunities({ token }: { token: string }) {
  const [items, setItems] = useState<Opportunity[]>([]);
  const [selected, setSelected] = useState<Opportunity | null>(null);
  const [registration, setRegistration] = useState<Registration | null>(null);
  const [registrationLoading, setRegistrationLoading] = useState(false);
  const [actionBusy, setActionBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiJson<Opportunity[]>('activity-opportunities', {}, token)
      .then(setItems)
      .catch(cause => setError(cause instanceof ApiError ? cause.message : 'Unable to load opportunities.'))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    setMessage('');
    if (!selected) { setRegistration(null); return; }
    setRegistration(null);
    setRegistrationLoading(true);
    setError('');
    apiJson<Registration | null>(`activity-opportunities/${selected.id}/registration/me`, {}, token)
      .then(setRegistration)
      .catch(cause => setError(cause instanceof ApiError ? cause.message : 'Unable to load registration.'))
      .finally(() => setRegistrationLoading(false));
  }, [selected, token]);

  const join = async () => {
    if (!selected || actionBusy) return;
    setActionBusy(true); setError(''); setMessage('');
    try {
      const current = await apiJson<Registration>(`activity-opportunities/${selected.id}/join`, { method: 'POST' }, token);
      setRegistration(current);
      setMessage('You are now registered for this opportunity.');
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Unable to register.');
    } finally { setActionBusy(false); }
  };

  const complete = async () => {
    if (!selected || registration?.status !== 'registered' || actionBusy) return;
    setActionBusy(true); setError(''); setMessage('');
    try {
      const current = await apiJson<Registration>(`activity-opportunities/${selected.id}/complete`, { method: 'POST' }, token);
      setRegistration(current);
      setMessage('Participation marked as completed and submitted for verification.');
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Unable to complete participation.');
    } finally { setActionBusy(false); }
  };

  if (selected) {
    const regInfo = registration ? REG_STATUS_MAP[registration.status] : null;

    return (
      <div>
        <div className="page-header">
          <div className="page-header-text">
            <button className="link" onClick={() => setSelected(null)} style={{ marginBottom: '.75rem', display: 'inline-flex', alignItems: 'center', gap: '.35rem' }}>
              ← Back to opportunities
            </button>
            <p className="eyebrow">{selected.activity_type} · {selected.dimension}</p>
            <h1>{selected.title}</h1>
          </div>
        </div>

        <div className="content-with-aside">
          <div>
            <div className="panel" style={{ marginBottom: '1rem' }}>
              <h2 style={{ fontSize: '1.1rem', marginBottom: '.75rem' }}>About this opportunity</h2>
              <p style={{ color: 'var(--tv-muted)', lineHeight: '1.7' }}>{selected.description}</p>
            </div>
            <div className="panel">
              <h2 style={{ fontSize: '1.1rem', marginBottom: '.75rem' }}>Details</h2>
              <p><strong>Starts:</strong> <time>{new Date(selected.starts_at).toLocaleString()}</time></p>
              <p><strong>Ends:</strong> <time>{new Date(selected.ends_at).toLocaleString()}</time></p>
              {selected.location && <p><strong>Location:</strong> {selected.location}</p>}
              {selected.capacity && <p><strong>Capacity:</strong> {selected.capacity} participants</p>}
              <p><strong>Members only:</strong> {selected.members_only ? 'Yes' : 'No'}</p>
            </div>
          </div>

          <div className="panel">
            <h2 style={{ fontSize: '1.1rem', marginBottom: '1rem' }}>Your registration</h2>
            {error && <p role="alert" className="error" style={{ marginBottom: '1rem' }}>{error}</p>}
            {message && <p role="status" className="success-msg" style={{ marginBottom: '1rem' }}>{message}</p>}

            {registrationLoading ? (
              <p role="status" className="text-muted text-sm">Loading registration…</p>
            ) : registration ? (
              <>
                {regInfo && <span className={`chip ${regInfo.color}`} style={{ marginBottom: '1rem', display: 'inline-block' }}>{regInfo.label}</span>}
                {registration.status === 'registered' && (
                  <button
                    className="accent"
                    onClick={complete}
                    disabled={actionBusy}
                    style={{ width: '100%', marginTop: '.75rem' }}
                  >
                    {actionBusy ? 'Completing…' : 'Mark as completed'}
                  </button>
                )}
                {registration.status === 'verified' && (
                  <p className="text-muted text-sm">Your participation has been verified. Impact Points have been awarded.</p>
                )}
              </>
            ) : !error ? (
              <button
                className="accent"
                onClick={join}
                disabled={actionBusy}
                style={{ width: '100%' }}
              >
                {actionBusy ? 'Joining…' : 'Join this opportunity'}
              </button>
            ) : null}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <div className="page-header-text">
          <p className="eyebrow">Discover</p>
          <h1>Community opportunities</h1>
          <p>Find ways to participate, serve, and lead within your communities.</p>
        </div>
      </div>

      <PersonalHistory token={token} kind="opportunity" title="My registrations, history and archived participation" />
      {loading && <p role="status" className="text-muted">Loading opportunities…</p>}
      {error && <p role="alert" className="error">{error}</p>}
      {!loading && !error && !items.length && (
        <EmptyState
          title="No opportunities available"
          description="There are no open community opportunities right now. Check back soon."
        />
      )}

      <div className="grid">
        {items.map((item, index) => (
          <Fragment key={item.id}>
          <article className="card" key={item.id} style={{ display: 'flex', flexDirection: 'column', gap: '.5rem' }}>
            <div style={{ display: 'flex', gap: '.5rem', flexWrap: 'wrap' }}>
              <span className={`chip ${DIMENSION_COLORS[item.dimension] || 'chip-default'}`}>{item.dimension}</span>
              <span className="chip chip-default">{item.activity_type.replace(/_/g, ' ')}</span>
            </div>
            <h3 style={{ margin: 0 }}>{item.title}</h3>
            <p style={{ color: 'var(--tv-muted)', fontSize: '.875rem', flex: 1, margin: 0 }}>
              {item.description.length > 100 ? item.description.slice(0, 100) + '…' : item.description}
            </p>
            <time style={{ fontSize: '.8rem', color: 'var(--tv-muted-light)' }}>
              {new Date(item.starts_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
            </time>
            {item.location && (
              <p style={{ fontSize: '.8rem', color: 'var(--tv-muted-light)', margin: 0 }}>📍 {item.location}</p>
            )}
            <button
              className="secondary sm"
              onClick={() => setSelected(item)}
              style={{ alignSelf: 'flex-start', marginTop: '.25rem' }}
            >
              View opportunity
            </button>
          </article>
          {index === 2 && items.length > 3 && <div className="result-placement"><SponsoredPlacement surface="opportunities" /></div>}
          </Fragment>
        ))}
      </div>
    </div>
  );
}
