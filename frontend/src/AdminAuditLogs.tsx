import { useEffect, useState } from 'react';
import { EmptyState } from './AppShell';
import { apiJson, ApiError, getLiveToken } from './api';

type Log = { id: string; actor_id?: string; action: string; target_type?: string; target_id?: string; occurred_at: string; metadata: unknown };

// Human-readable labels for audit action codes.
const ACTION_LABELS: Record<string, string> = {
  'event.created': 'Event created',
  'event.updated': 'Event updated',
  'event.published': 'Event published',
  'event.unpublished': 'Event unpublished',
  'event.deleted': 'Event deleted',
  'event.cover_image_updated': 'Event cover image updated',
  'ticket_type.created': 'Ticket type created',
  'ticket.cancelled': 'Ticket cancelled',
  'ticket.refunded': 'Ticket refunded',
  'attendance.verified': 'Attendance verified',
  'attendance.checked_in': 'Attendance checked in',
  'attendance.rejected': 'Attendance rejected',
  'attendance.override': 'Attendance override',
  'attendance.review_cleared': 'Attendance review cleared',
  'attendance.review_confirmed': 'Attendance review confirmed',
  'attendance.review_rejected': 'Attendance review rejected',
  'task.created': 'Task created',
  'task.verified': 'Task verified',
  'task.rejected': 'Task rejected',
  'contribution.verified': 'Contribution verified',
  'contribution.rejected': 'Contribution rejected',
  'impact.adjusted': 'Impact Points adjusted',
  'impact.awarded': 'Impact Points awarded',
  'badge.awarded': 'Badge awarded',
  'badge.revoked': 'Badge revoked',
  'rank.changed': 'Rank changed',
  'rank.achieved': 'Rank achieved',
  'membership.role_changed': 'Membership role changed',
  'membership.status_changed': 'Membership status changed',
  'community.created': 'Community created',
  'community.updated': 'Community updated',
  'point_rule.updated': 'Point rule updated',
  'contribution_band.created': 'Contribution tier created',
  'contribution_band.updated': 'Contribution tier updated',
  'achievement_rule.created': 'Achievement rule created',
  'achievement_rule.updated': 'Achievement rule updated',
  'badge.created': 'Badge created',
  'badge.updated': 'Badge updated',
  'milestone.created': 'Milestone created',
  'rank.created': 'Rank created',
  'rank.updated': 'Rank updated',
  'notification_rule.created': 'Notification rule created',
  'notification_rule.updated': 'Notification rule updated',
  'leaderboard.created': 'Leaderboard created',
  'leaderboard.updated': 'Leaderboard updated',
};

function friendlyAction(action: string): string {
  return ACTION_LABELS[action] ?? action.replace(/[._]/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

export function AdminAuditLogs({ token, communityId }: { token: string; communityId?: string }) {
  const [logs, setLogs] = useState<Log[]>([]);
  const [error, setError] = useState('');
  const [action, setAction] = useState('');
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);

  const liveToken = () => getLiveToken() ?? token;

  const load = async () => {
    setLoading(true); setError('');
    try {
      let id = communityId;
      if (!id) {
        const memberships = await apiJson<any[]>('communities/me', {}, liveToken());
        id = memberships[0]?.id;
      }
      if (!id) { setError('No active community selected.'); return; }
      const query = new URLSearchParams({ limit: '25', offset: String(offset) });
      if (action) query.set('action', action);
      setLogs(await apiJson<Log[]>(`admin/communities/${id}/audit-logs?${query}`, {}, liveToken()));
    } catch (cause) {
      setError(cause instanceof ApiError && cause.status === 403 ? 'Administrator access required.' : 'Unable to load audit logs.');
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [token, communityId, offset, action]);

  return (
    <div>
      <div className="page-header">
        <div className="page-header-text">
          <p className="eyebrow">Administration</p>
          <h1>Audit log</h1>
          <p>Immutable record of all significant actions in this community.</p>
        </div>
        <div className="page-header-actions">
          <div className="search-input">
            <span className="search-icon" aria-hidden="true">⌕</span>
            <input
              type="search"
              value={action}
              onChange={e => { setOffset(0); setAction(e.target.value); }}
              placeholder="Filter by action…"
              aria-label="Action filter"
              style={{ width: '18rem' }}
            />
          </div>
        </div>
      </div>

      {error && <p role="alert" className="error" style={{ marginBottom: '1rem' }}>{error}</p>}
      {loading && <p role="status" className="text-muted">Loading audit log…</p>}

      {!loading && !error && !logs.length && (
        <EmptyState
          title="No audit records"
          description={action ? 'No records match this filter.' : 'No audit records have been created yet.'}
          action={action ? 'Clear filter' : undefined}
          onAction={action ? () => setAction('') : undefined}
        />
      )}

      <div className="stack">
        {logs.map(log => (
          <article key={log.id} className="card" style={{ fontSize: '.875rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', flexWrap: 'wrap' }}>
              <div>
                {/* Human-readable action name */}
                <strong style={{ color: 'var(--tv-ink)' }}>{friendlyAction(log.action)}</strong>
                <div style={{ display: 'flex', gap: '.75rem', marginTop: '.25rem', color: 'var(--tv-muted)', fontSize: '.8rem', flexWrap: 'wrap' }}>
                  <time dateTime={log.occurred_at}>{new Date(log.occurred_at).toLocaleString()}</time>
                  {log.target_type && (
                    <span>
                      {log.target_type.replace(/_/g, ' ')}
                      {log.target_id ? ` #${log.target_id.slice(0, 8)}` : ''}
                    </span>
                  )}
                  {log.actor_id && <span>by {log.actor_id.slice(0, 8)}…</span>}
                </div>
                {/* Concise technical code for reference */}
                <code style={{ fontSize: '.75rem', color: 'var(--tv-muted-light)', marginTop: '.2rem', display: 'block' }}>{log.action}</code>
              </div>
              {Boolean(log.metadata) && (
                <button
                  className="secondary sm"
                  onClick={() => setExpanded(expanded === log.id ? null : log.id)}
                  aria-expanded={expanded === log.id}
                >
                  {expanded === log.id ? 'Hide details' : 'Show details'}
                </button>
              )}
            </div>
            {expanded === log.id && Boolean(log.metadata) && (
              <details open style={{ marginTop: '.75rem' }}>
                <summary style={{ fontSize: '.8rem', color: 'var(--tv-muted)', cursor: 'pointer', marginBottom: '.5rem' }}>Raw metadata</summary>
                <pre style={{ fontSize: '.75rem', overflowX: 'auto' }}>{JSON.stringify(log.metadata, null, 2)}</pre>
              </details>
            )}
          </article>
        ))}
      </div>

      {(offset > 0 || logs.length === 25) && (
        <div className="pagination" style={{ marginTop: '1rem' }}>
          <span className="pagination-info">Page {Math.floor(offset / 25) + 1}</span>
          <div className="pagination-actions">
            <button className="secondary sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 25))}>← Previous</button>
            <button className="secondary sm" disabled={logs.length < 25} onClick={() => setOffset(offset + 25)}>Next →</button>
          </div>
        </div>
      )}
    </div>
  );
}
