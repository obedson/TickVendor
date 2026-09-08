import { useEffect, useState } from 'react';
import { EmptyState } from './AppShell';

type Log = { id: string; actor_id?: string; action: string; target_type?: string; target_id?: string; occurred_at: string; metadata: unknown };

export function AdminAuditLogs({ token, communityId }: { token: string; communityId?: string }) {
  const [logs, setLogs] = useState<Log[]>([]);
  const [error, setError] = useState('');
  const [action, setAction] = useState('');
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);
  const headers = { Authorization: `Bearer ${token}` };

  const load = async () => {
    setLoading(true);
    try {
      let id = communityId;
      if (!id) {
        const memberships = await fetch('/api/v1/communities/me', { headers });
        if (!memberships.ok) { setError('Unable to load communities.'); return; }
        id = (await memberships.json())[0]?.id;
      }
      if (!id) { setError('No active community selected.'); return; }
      const query = new URLSearchParams({ limit: '25', offset: String(offset) });
      if (action) query.set('action', action);
      const response = await fetch(`/api/v1/admin/communities/${id}/audit-logs?${query}`, { headers });
      if (!response.ok) { setError(response.status === 403 ? 'Administrator access required.' : 'Unable to load audit logs.'); return; }
      setLogs(await response.json());
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
                <strong style={{ fontFamily: 'var(--tv-font-mono)', fontSize: '.8rem', color: 'var(--tv-ink)' }}>{log.action}</strong>
                <div style={{ display: 'flex', gap: '.75rem', marginTop: '.25rem', color: 'var(--tv-muted)', fontSize: '.8rem', flexWrap: 'wrap' }}>
                  <time>{new Date(log.occurred_at).toLocaleString()}</time>
                  {log.target_type && <span>{log.target_type}{log.target_id ? ` #${log.target_id.slice(0, 8)}` : ''}</span>}
                  {log.actor_id && <span>by {log.actor_id.slice(0, 8)}…</span>}
                </div>
              </div>
              {log.metadata && (
                <button
                  className="secondary sm"
                  onClick={() => setExpanded(expanded === log.id ? null : log.id)}
                >
                  {expanded === log.id ? 'Hide' : 'Details'}
                </button>
              )}
            </div>
            {expanded === log.id && log.metadata && (
              <pre style={{ marginTop: '.75rem' }}>{JSON.stringify(log.metadata, null, 2)}</pre>
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
