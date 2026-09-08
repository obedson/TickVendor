import { useEffect, useState } from 'react';
import { EmptyState } from './AppShell';

type Submission = {
  assignment_id: string;
  task_title: string;
  assignee_id: string;
  assignee_name?: string;
  submitted_at: string;
  evidence_text?: string;
  evidence_url?: string;
  evidence_attachments: string[];
};

export function OrganizerTaskQueue({ token, communityId }: { token: string; communityId?: string }) {
  const [items, setItems] = useState<Submission[]>([]);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);
  const headers = { Authorization: `Bearer ${token}` };

  const load = async () => {
    setLoading(true);
    try {
      let id = communityId;
      if (!id) {
        const memberships = await fetch('/api/v1/communities/me', { headers });
        if (!memberships.ok) throw Error('Unable to load communities');
        id = (await memberships.json())[0]?.id;
      }
      if (!id) throw Error('No active community selected');
      const response = await fetch(`/api/v1/communities/${id}/task-verification-queue`, { headers });
      if (!response.ok) throw Error(response.status === 403 ? 'Organizer access required' : 'Unable to load task queue');
      setItems(await response.json());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to load task queue');
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [token, communityId]);

  const verify = async (assignmentId: string, approve: boolean) => {
    const response = await fetch(`/api/v1/task-assignments/${assignmentId}/verify`, {
      method: 'POST',
      headers: { ...headers, 'Content-Type': 'application/json' },
      body: JSON.stringify({ approve }),
    });
    if (!response.ok) { const data = await response.json(); setError(data.detail || 'Unable to update submission'); return; }
    setMessage(approve ? 'Task verified and points awarded.' : 'Task submission rejected.');
    setExpanded(null);
    await load();
  };

  return (
    <div>
      <div className="page-header">
        <div className="page-header-text">
          <p className="eyebrow">Operations</p>
          <h1>Task verification</h1>
          <p>Review and verify task submissions from community members.</p>
        </div>
        {items.length > 0 && (
          <div className="page-header-actions">
            <span className="chip chip-yellow">{items.length} pending</span>
          </div>
        )}
      </div>

      {error && <p role="alert" className="error" style={{ marginBottom: '1rem' }}>{error}</p>}
      {message && <p role="status" className="success-msg" style={{ marginBottom: '1rem' }}>{message}</p>}
      {loading && <p role="status" className="text-muted">Loading task queue…</p>}

      {!loading && !error && !items.length && (
        <EmptyState
          title="Queue is clear"
          description="No task submissions are waiting for review. Check back when members submit their work."
        />
      )}

      <div className="stack">
        {items.map(item => (
          <article key={item.assignment_id} className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', flexWrap: 'wrap' }}>
              <div>
                <h3 style={{ margin: '0 0 .25rem' }}>{item.task_title}</h3>
                <p style={{ margin: 0, fontSize: '.875rem', color: 'var(--tv-muted)' }}>
                  {item.assignee_name || item.assignee_id.slice(0, 8) + '…'} ·{' '}
                  <time>{new Date(item.submitted_at).toLocaleString()}</time>
                </p>
              </div>
              <div style={{ display: 'flex', gap: '.5rem', flexShrink: 0 }}>
                <button
                  className="secondary sm"
                  onClick={() => setExpanded(expanded === item.assignment_id ? null : item.assignment_id)}
                >
                  {expanded === item.assignment_id ? 'Hide evidence' : 'View evidence'}
                </button>
                <button className="accent sm" onClick={() => verify(item.assignment_id, true)}>Verify</button>
                <button className="danger sm" onClick={() => verify(item.assignment_id, false)}>Reject</button>
              </div>
            </div>

            {expanded === item.assignment_id && (
              <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--tv-border)' }}>
                {item.evidence_text ? (
                  <div style={{ background: 'var(--tv-surface-sunken)', borderRadius: 'var(--tv-radius-md)', padding: '1rem', fontSize: '.875rem', lineHeight: '1.6' }}>
                    {item.evidence_text}
                  </div>
                ) : (
                  <p className="text-muted text-sm">No text evidence provided.</p>
                )}
                {item.evidence_url && (
                  <p style={{ marginTop: '.75rem' }}>
                    <a href={item.evidence_url} target="_blank" rel="noopener noreferrer">View evidence link →</a>
                  </p>
                )}
              </div>
            )}
          </article>
        ))}
      </div>
    </div>
  );
}
