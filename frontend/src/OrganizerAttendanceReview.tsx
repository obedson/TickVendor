import { useEffect, useState } from 'react';
import { EmptyState } from './AppShell';
import { apiJson, ApiError, getLiveToken } from './api';

type Review = {
  attendance_id: string;
  participant_id: string;
  participant_name?: string;
  status: string;
  review_status: string;
  review_reason?: string;
  suspicious_signal_count: number;
};

export function OrganizerAttendanceReview({ token, eventId }: { token: string; eventId: string }) {
  const [items, setItems] = useState<Review[]>([]);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const liveToken = () => getLiveToken() ?? token;

  const load = async () => {
    if (!eventId) { setLoading(false); return; }
    setLoading(true); setError('');
    try {
      setItems(await apiJson<Review[]>(`events/${eventId}/attendance/review`, {}, liveToken()));
    } catch (cause) {
      setError(cause instanceof ApiError && cause.status === 403 ? 'Attendance review permission required.' : 'Unable to load review queue.');
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [token, eventId]);

  const resolve = async (item: Review, outcome: string) => {
    try {
      await apiJson<unknown>(`events/${eventId}/attendance/${item.attendance_id}/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ outcome, reason: `Organizer ${outcome} review` }),
      }, liveToken());
      setMessage(`Attendance ${outcome}.`);
      await load();
    } catch { setError('Unable to resolve review.'); }
  };

  return (
    <div>
      <div className="page-header">
        <div className="page-header-text">
          <p className="eyebrow">Operations</p>
          <h1>Attendance review</h1>
          <p>Review flagged attendance records for this event.</p>
        </div>
        {items.length > 0 && (
          <div className="page-header-actions">
            <span className="chip chip-yellow">{items.length} flagged</span>
          </div>
        )}
      </div>

      {error && <p role="alert" className="error" style={{ marginBottom: '1rem' }}>{error}</p>}
      {message && <p role="status" className="success-msg" style={{ marginBottom: '1rem' }}>{message}</p>}
      {loading && <p role="status" className="text-muted">Loading review queue…</p>}

      {!eventId && (
        <p className="info-msg">Select an event from the Events section to review its attendance records.</p>
      )}

      {!loading && !error && eventId && !items.length && (
        <EmptyState
          title="No flagged attendance"
          description="All attendance records for this event are clear. Flagged records will appear here for review."
        />
      )}

      <div className="stack">
        {items.map(item => (
          <article key={item.attendance_id} className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', flexWrap: 'wrap' }}>
              <div>
                <h3 style={{ margin: '0 0 .35rem', fontSize: '1rem' }}>
                  {item.participant_name || `Participant ${item.participant_id.slice(0, 8)}…`}
                </h3>
                <div style={{ display: 'flex', gap: '.5rem', flexWrap: 'wrap' }}>
                  <span className="chip chip-default">{item.status}</span>
                  {item.suspicious_signal_count > 0 && (
                    <span className="chip chip-red">⚠ {item.suspicious_signal_count} signal{item.suspicious_signal_count !== 1 ? 's' : ''}</span>
                  )}
                </div>
              </div>
              <div style={{ display: 'flex', gap: '.5rem', flexShrink: 0 }}>
                <button className="accent sm" onClick={() => resolve(item, 'confirmed')}>Confirm</button>
                <button className="secondary sm" onClick={() => resolve(item, 'cleared')}>Clear</button>
                <button className="danger sm" onClick={() => resolve(item, 'rejected')}>Reject</button>
              </div>
            </div>
            {item.review_reason && (
              <p style={{ marginTop: '.75rem', fontSize: '.875rem', color: 'var(--tv-muted)', padding: '.65rem .85rem', background: 'var(--tv-surface-sunken)', borderRadius: 'var(--tv-radius-md)' }}>
                {item.review_reason}
              </p>
            )}
          </article>
        ))}
      </div>
    </div>
  );
}
