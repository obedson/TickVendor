import { useEffect, useState } from 'react';
import './management.css';
import { apiJson, ApiError, getLiveToken } from './api';

type Board = { id: string; name: string; slug: string; metric: string; period: string; max_entries: number; is_enabled: boolean; event_id?: string | null };

export function AdminLeaderboards({ token, communityId }: { token: string; communityId?: string }) {
  const [community, setCommunity] = useState(communityId);
  const [boards, setBoards] = useState<Board[]>([]);
  const [form, setForm] = useState({ name: 'Community leaderboard', slug: 'community-leaderboard', metric: 'overall', period: 'all_time', max_entries: '100', is_enabled: 'true' });
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const liveToken = () => getLiveToken() ?? token;

  const load = async (id = community) => {
    if (!id) return;
    try {
      setBoards(await apiJson<Board[]>(`admin/communities/${id}/leaderboards`, {}, liveToken()));
    } catch (cause) {
      setError(cause instanceof ApiError && cause.status === 403 ? 'Administrator access required.' : 'Unable to load leaderboard configuration.');
    }
  };

  useEffect(() => {
    if (community) { load(); return; }
    apiJson<any[]>('communities/me', {}, liveToken())
      .then(items => { const id = items[0]?.id; setCommunity(id); if (id) load(id); })
      .catch(() => setError('Unable to load communities.'));
  }, [token, community]);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!community) return;
    const existing = boards[0];
    try {
      await apiJson<Board>(`admin/communities/${community}/leaderboards${existing ? `/${existing.id}` : ''}`, {
        method: existing ? 'PATCH' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...form, max_entries: Number(form.max_entries), is_enabled: form.is_enabled === 'true' }),
      }, liveToken());
      setMessage('Leaderboard configuration saved.');
      await load();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Unable to save leaderboard.');
    }
  };

  return (
    <section className="panel management-screen">
      <h2>Leaderboard configuration</h2>
      {error && <p role="alert" className="error">{error}</p>}
      {message && <p role="status" className="success-msg">{message}</p>}
      <form onSubmit={save} style={{ display: 'grid', gap: '.75rem', marginBottom: '1.5rem' }}>
        <div className="form-row">
          <label><span className="label-text">Name</span><input required value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} /></label>
          <label><span className="label-text">Slug</span><input required value={form.slug} onChange={e => setForm({ ...form, slug: e.target.value })} /></label>
        </div>
        <div className="form-row">
          <label>
            <span className="label-text">Metric</span>
            <select value={form.metric} onChange={e => setForm({ ...form, metric: e.target.value })}>
              <option value="overall">Overall</option>
              <option value="attendance">Attendance</option>
              <option value="tasks">Tasks</option>
              <option value="service">Service</option>
              <option value="leadership">Leadership</option>
              <option value="event">Event</option>
            </select>
          </label>
          <label>
            <span className="label-text">Period</span>
            <select value={form.period} onChange={e => setForm({ ...form, period: e.target.value })}>
              <option value="all_time">All time</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
            </select>
          </label>
          <label><span className="label-text">Max entries</span><input required type="number" min="1" max="500" value={form.max_entries} onChange={e => setForm({ ...form, max_entries: e.target.value })} /></label>
        </div>
        <div className="form-actions">
          <button type="submit" className="accent">Save leaderboard</button>
        </div>
      </form>
      {!error && !boards.length && <p className="empty">No leaderboard configured.</p>}
      <div className="stack">
        {boards.map(board => (
          <article className="card" key={board.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <strong>{board.name}</strong>
              <p style={{ margin: '.25rem 0 0', fontSize: '.875rem', color: 'var(--tv-muted)' }}>{board.metric} · {board.period} · {board.max_entries} entries</p>
            </div>
            <span className={`chip ${board.is_enabled ? 'chip-green' : 'chip-default'}`}>{board.is_enabled ? 'Enabled' : 'Disabled'}</span>
          </article>
        ))}
      </div>
    </section>
  );
}
