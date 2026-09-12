import { useEffect, useState } from 'react';
import './management.css';
import { apiJson, ApiError, getLiveToken } from './api';

type Rule = { id: string; source_type: string; points: number; max_awards_per_user?: number; is_active: boolean };

export function AdminPointRules({ token, communityId }: { token: string; communityId?: string }) {
  const [rules, setRules] = useState<Rule[]>([]);
  const [community, setCommunity] = useState(communityId);
  const [source, setSource] = useState('task_completion');
  const [points, setPoints] = useState('5');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const liveToken = () => getLiveToken() ?? token;

  const load = async (id = community) => {
    if (!id) return;
    try {
      setRules(await apiJson<Rule[]>(`admin/communities/${id}/point-rules`, {}, liveToken()));
    } catch (cause) {
      setError(cause instanceof ApiError && cause.status === 403 ? 'Administrator access required.' : 'Unable to load point rules.');
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
    try {
      await apiJson<Rule>(`admin/communities/${community}/point-rules`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_type: source, points: Number(points), is_active: true }),
      }, liveToken());
      setMessage('Point rule saved.');
      await load();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Unable to save point rule.');
    }
  };

  return (
    <section className="panel management-screen">
      <h2>Point rules</h2>
      {error && <p role="alert" className="error">{error}</p>}
      {message && <p role="status" className="success-msg">{message}</p>}
      <form onSubmit={save} style={{ display: 'grid', gap: '.75rem', marginBottom: '1.5rem' }}>
        <label>
          <span className="label-text">Source type</span>
          <select value={source} onChange={e => setSource(e.target.value)}>
            <option value="attendance">Attendance</option>
            <option value="task_completion">Task completion</option>
            <option value="volunteer_activity">Volunteer activity</option>
            <option value="peer_verification">Peer verification</option>
            <option value="leadership_activity">Leadership activity</option>
          </select>
        </label>
        <label>
          <span className="label-text">Points</span>
          <input required type="number" min="0" value={points} onChange={e => setPoints(e.target.value)} />
        </label>
        <div className="form-actions">
          <button type="submit" className="accent">Save point rule</button>
        </div>
      </form>
      <div className="stack">
        {rules.map(rule => (
          <article className="card" key={rule.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <strong>{rule.source_type.replace(/_/g, ' ')}</strong>
            <span>{rule.points} points · <span className={`chip ${rule.is_active ? 'chip-green' : 'chip-default'}`}>{rule.is_active ? 'Active' : 'Disabled'}</span></span>
          </article>
        ))}
      </div>
    </section>
  );
}
