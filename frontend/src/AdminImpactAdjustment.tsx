import { useEffect, useState } from 'react';
import './management.css';
import { apiJson, ApiError, getLiveToken } from './api';

type Member = { user_id: string; display_name?: string; username?: string; email?: string; status: string };

export function AdminImpactAdjustment({ token, communityId }: { token: string; communityId?: string }) {
  const [community, setCommunity] = useState(communityId);
  const [members, setMembers] = useState<Member[]>([]);
  const [target, setTarget] = useState('');
  const [amount, setAmount] = useState('');
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const liveToken = () => getLiveToken() ?? token;

  const load = async (id = community) => {
    if (!id) return;
    try {
      const data = await apiJson<{ members: Member[] }>(`communities/${id}/members`, {}, liveToken());
      setMembers(data.members);
    } catch { setError('Unable to load community members.'); }
  };

  useEffect(() => {
    if (community) { load(); return; }
    apiJson<any[]>('communities/me', {}, liveToken())
      .then(items => { const id = items[0]?.id; setCommunity(id); if (id) load(id); })
      .catch(() => setError('Unable to load communities.'));
  }, [token, community]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!community || !target || Number(amount) === 0) return;
    setBusy(true); setError(''); setMessage('');
    try {
      const data = await apiJson<{ points: number; id: string }>(`admin/communities/${community}/point-adjustments`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_user_id: target, amount: Number(amount), reason }),
      }, liveToken());
      setMessage(`Impact Points adjusted by ${data.points}. Reference ${data.id}.`);
      setAmount(''); setReason(''); setTarget('');
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Unable to adjust Impact Points.');
    } finally { setBusy(false); }
  };

  return (
    <section className="panel management-screen">
      <h2>Manual Impact Point adjustment</h2>
      <p style={{ color: 'var(--tv-muted)', marginBottom: '1.25rem' }}>Adjustments are append-only and audited.</p>
      {error && <p role="alert" className="error">{error}</p>}
      {message && <p role="status" className="success-msg">{message}</p>}
      <form onSubmit={submit} style={{ display: 'grid', gap: '.75rem' }}>
        <label>
          <span className="label-text">Participant</span>
          <select required value={target} onChange={e => setTarget(e.target.value)}>
            <option value="">Select a member</option>
            {members.filter(m => m.status === 'active').map(m => (
              <option key={m.user_id} value={m.user_id}>{[m.display_name || m.username || 'Private member', m.email].filter(Boolean).join(' — ')}</option>
            ))}
          </select>
        </label>
        <label>
          <span className="label-text">Amount (positive to add, negative to deduct)</span>
          <input required type="number" min="-100000" max="100000" value={amount} onChange={e => setAmount(e.target.value)} />
        </label>
        <label>
          <span className="label-text">Reason</span>
          <textarea required minLength={3} value={reason} onChange={e => setReason(e.target.value)} rows={3} />
        </label>
        <div className="form-actions">
          <button type="submit" className="accent" disabled={busy || !target || Number(amount) === 0}>
            {busy ? 'Submitting…' : 'Adjust points'}
          </button>
        </div>
      </form>
    </section>
  );
}
