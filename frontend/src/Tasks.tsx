import { useEffect, useState } from 'react';
import { apiJson, ApiError, getLiveToken } from './api';
import { EmptyState } from './AppShell';

type Task = {
  id: string;
  title: string;
  description: string;
  due_at?: string | null;
  priority: string;
  impact_point_reward: number;
  verification_required: boolean;
  event_id?: string | null;
  status: string;
};
type Assignment = { id: string; task_id: string; status: string; due_at?: string | null };

const PRIORITY_COLORS: Record<string, string> = {
  high: 'chip-red',
  medium: 'chip-yellow',
  low: 'chip-blue',
};

const STATUS_COLORS: Record<string, string> = {
  assigned: 'chip-blue',
  submitted: 'chip-yellow',
  verified: 'chip-green',
  rejected: 'chip-red',
};

export function Tasks({ token, communityId }: { token: string; communityId?: string }) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [selected, setSelected] = useState<Task | null>(null);
  const [evidence, setEvidence] = useState('');
  const [statusMsg, setStatusMsg] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [noCommunity, setNoCommunity] = useState(false);
  const [filter, setFilter] = useState<'all' | 'active' | 'completed'>('active');

  const liveToken = () => getLiveToken() ?? token;

  const load = async () => {
    setLoading(true);
    setNoCommunity(false);
    try {
      const communities = communityId ? [{ id: communityId }] : await apiJson<{ id: string }[]>('communities/me', {}, liveToken());
      const id = communities[0]?.id;
      if (!id) { setNoCommunity(true); setTasks([]); setAssignments([]); return; }
      const [a, t] = await Promise.all([
        apiJson<Assignment[]>('task-assignments/me', {}, liveToken()),
        apiJson<Task[]>(`communities/${id}/tasks`, {}, liveToken()),
      ]);
      setAssignments(a);
      setTasks(t);
      setError('');
    } catch (e) {
      setError(e instanceof ApiError ? e.message : e instanceof Error ? e.message : 'Unable to load tasks');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [token, communityId]);

  const submit = async () => {
    if (!selected) return;
    const assignment = assignments.find(item => item.task_id === selected.id);
    if (!assignment) { setError('This task is not assigned to you.'); return; }
    setBusy(true);
    setError('');
    try {
      await apiJson<unknown>(`task-assignments/${assignment.id}/submissions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ evidence_text: evidence }),
      }, liveToken());
      setStatusMsg(selected.verification_required ? 'Submitted for verification.' : 'Task completed!');
      setSelected(null);
      setEvidence('');
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Unable to submit task');
    } finally {
      setBusy(false);
    }
  };

  const filteredTasks = tasks.filter(task => {
    const assignment = assignments.find(a => a.task_id === task.id);
    const status = assignment?.status || 'available';
    if (filter === 'active') return !['verified', 'rejected'].includes(status);
    if (filter === 'completed') return ['verified', 'rejected'].includes(status);
    return true;
  });

  return (
    <div>
      <div className="page-header">
        <div className="page-header-text">
          <p className="eyebrow">Participation</p>
          <h1>Tasks</h1>
          <p>Complete tasks to earn Impact Points and contribute to your community.</p>
        </div>
      </div>

      {loading && <p role="status" className="text-muted">Loading tasks…</p>}
      {error && <p role="alert" className="error">{error}</p>}
      {statusMsg && <p role="status" className="success-msg" style={{ marginBottom: '1rem' }}>{statusMsg}</p>}

      {!loading && !error && noCommunity && (
        <EmptyState
          title="Join a community to view tasks"
          description="Tasks are created within communities. Join a community to see available tasks."
        />
      )}

      {!loading && !error && !noCommunity && (
        <>
          {/* Filter tabs */}
          <div style={{ display: 'flex', gap: '.5rem', marginBottom: '1.25rem', flexWrap: 'wrap' }}>
            {(['active', 'all', 'completed'] as const).map(f => (
              <button
                key={f}
                className={filter === f ? 'accent sm' : 'secondary sm'}
                onClick={() => setFilter(f)}
              >
                {f === 'active' ? 'Active' : f === 'all' ? 'All tasks' : 'Completed'}
              </button>
            ))}
          </div>

          {!filteredTasks.length && (
            <EmptyState
              title={filter === 'active' ? 'No active tasks' : filter === 'completed' ? 'No completed tasks' : 'No tasks available'}
              description="There are no tasks matching this filter for your community right now."
            />
          )}

          <div className="grid">
            {filteredTasks.map(task => {
              const assignment = assignments.find(a => a.task_id === task.id);
              const status = assignment?.status || 'available';
              const canSubmit = assignment && !['submitted', 'verified', 'rejected'].includes(status);

              return (
                <article className="card" key={task.id} style={{ display: 'flex', flexDirection: 'column', gap: '.5rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '.5rem' }}>
                    <h3 style={{ margin: 0, fontSize: '1rem' }}>{task.title}</h3>
                    <span className={`chip ${PRIORITY_COLORS[task.priority] || 'chip-default'}`}>{task.priority}</span>
                  </div>
                  <p style={{ color: 'var(--tv-muted)', fontSize: '.875rem', flex: 1, margin: 0 }}>
                    {task.description.length > 100 ? task.description.slice(0, 100) + '…' : task.description}
                  </p>
                  <div style={{ display: 'flex', gap: '.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
                    <span className={`chip ${STATUS_COLORS[status] || 'chip-default'}`}>{status}</span>
                    <span className="chip chip-teal">+{task.impact_point_reward} pts</span>
                    {task.verification_required && <span className="chip chip-default">Needs review</span>}
                  </div>
                  {task.due_at && (
                    <time style={{ fontSize: '.8rem', color: 'var(--tv-muted)' }}>
                      Due {new Date(task.due_at).toLocaleDateString()}
                    </time>
                  )}
                  {canSubmit && (
                    <button
                      className="secondary sm"
                      onClick={() => { setSelected(task); setEvidence(''); setError(''); }}
                      style={{ alignSelf: 'flex-start', marginTop: '.25rem' }}
                    >
                      Submit evidence
                    </button>
                  )}
                </article>
              );
            })}
          </div>
        </>
      )}

      {/* Evidence submission modal */}
      {selected && (
        <div
          style={{ position: 'fixed', inset: 0, background: 'rgba(15,23,42,.5)', zIndex: 300, display: 'grid', placeItems: 'center', padding: '1rem' }}
          onClick={() => setSelected(null)}
        >
          <div
            className="panel"
            style={{ width: 'min(100%, 36rem)', maxHeight: '90vh', overflow: 'auto' }}
            onClick={e => e.stopPropagation()}
          >
            <h2 style={{ fontSize: '1.25rem', marginBottom: '.25rem' }}>Submit task evidence</h2>
            <p style={{ color: 'var(--tv-muted)', fontSize: '.875rem', marginBottom: '1.25rem' }}>{selected.title}</p>

            {error && <p role="alert" className="error" style={{ marginBottom: '1rem' }}>{error}</p>}

            <label>
              <span className="label-text">Evidence description</span>
              <textarea
                value={evidence}
                onChange={e => setEvidence(e.target.value)}
                maxLength={10000}
                rows={6}
                placeholder="Describe what you did, include links or references if applicable…"
              />
            </label>
            <p style={{ fontSize: '.8rem', color: 'var(--tv-muted)', marginTop: '.25rem' }}>
              {evidence.length}/10,000 characters
            </p>

            <div className="form-actions">
              <button
                className="accent"
                disabled={busy || !evidence.trim()}
                onClick={submit}
              >
                {busy ? 'Submitting…' : 'Submit task'}
              </button>
              <button className="secondary" onClick={() => setSelected(null)}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
