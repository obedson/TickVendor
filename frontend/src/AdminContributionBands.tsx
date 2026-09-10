import { useEffect, useState } from 'react';
import { apiJson, ApiError, getLiveToken } from './api';

type Band = { id: string; currency: string; minimum_amount: string; maximum_amount?: string | null; points: number; per_user_period_cap?: number | null; is_active: boolean };

export function AdminContributionBands({ token, communityId }: { token: string; communityId?: string }) {
  const [community, setCommunity] = useState(communityId);
  const [bands, setBands] = useState<Band[]>([]);
  const [editing, setEditing] = useState('');
  const [form, setForm] = useState({ minimum_amount: '0', maximum_amount: '', points: '1', per_user_period_cap: '' });
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const liveToken = () => getLiveToken() ?? token;

  const load = async (id = community) => {
    if (!id) return;
    try {
      setBands(await apiJson<Band[]>(`admin/communities/${id}/contribution-bands`, {}, liveToken()));
    } catch (cause) {
      setError(cause instanceof ApiError && cause.status === 403 ? 'Administrator access required.' : 'Unable to load contribution tiers.');
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
    const payload = {
      currency: 'NGN',
      minimum_amount: Number(form.minimum_amount),
      maximum_amount: form.maximum_amount ? Number(form.maximum_amount) : null,
      points: Number(form.points),
      per_user_period_cap: form.per_user_period_cap ? Number(form.per_user_period_cap) : null,
      is_active: true,
    };
    try {
      await apiJson<Band>(
        `admin/communities/${community}/contribution-bands${editing ? `/${editing}` : ''}`,
        { method: editing ? 'PATCH' : 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) },
        liveToken(),
      );
      setMessage(editing ? 'Contribution tier updated.' : 'Contribution tier saved.');
      setEditing('');
      setForm({ minimum_amount: '0', maximum_amount: '', points: '1', per_user_period_cap: '' });
      await load();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Unable to save contribution tier.');
    }
  };

  const edit = (band: Band) => {
    setEditing(band.id);
    setForm({ minimum_amount: band.minimum_amount, maximum_amount: band.maximum_amount || '', points: String(band.points), per_user_period_cap: band.per_user_period_cap ? String(band.per_user_period_cap) : '' });
  };

  const toggle = async (band: Band) => {
    if (!community) return;
    try {
      const data = await apiJson<Band>(
        `admin/communities/${community}/contribution-bands/${band.id}`,
        { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ currency: band.currency, minimum_amount: Number(band.minimum_amount), maximum_amount: band.maximum_amount ? Number(band.maximum_amount) : null, points: band.points, per_user_period_cap: band.per_user_period_cap, is_active: !band.is_active }) },
        liveToken(),
      );
      setMessage(`Contribution tier ${data.is_active ? 'enabled' : 'disabled'}.`);
      await load();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Unable to update contribution tier.');
    }
  };

  return (
    <section className="panel">
      <h2>Contribution Tiers</h2>
      <p style={{ color: 'var(--tv-muted)', marginBottom: '1.25rem' }}>
        Define contribution ranges and the Impact Points members earn for each tier.
      </p>
      {error && <p role="alert" className="error">{error}</p>}
      {message && <p role="status" className="success-msg">{message}</p>}
      <form onSubmit={save} style={{ display: 'grid', gap: '.75rem', marginBottom: '1.5rem' }}>
        <div className="form-row">
          <label>
            <span className="label-text">Minimum amount (NGN)</span>
            <input required type="number" min="0" value={form.minimum_amount} onChange={e => setForm({ ...form, minimum_amount: e.target.value })} />
          </label>
          <label>
            <span className="label-text">Maximum amount (blank = unlimited)</span>
            <input type="number" min="0" value={form.maximum_amount} onChange={e => setForm({ ...form, maximum_amount: e.target.value })} />
          </label>
        </div>
        <div className="form-row">
          <label>
            <span className="label-text">Impact Points awarded</span>
            <input required type="number" min="0" value={form.points} onChange={e => setForm({ ...form, points: e.target.value })} />
          </label>
          <label>
            <span className="label-text">Period cap (optional)</span>
            <input type="number" min="1" value={form.per_user_period_cap} onChange={e => setForm({ ...form, per_user_period_cap: e.target.value })} />
          </label>
        </div>
        <div className="form-actions">
          <button type="submit" className="accent">{editing ? 'Save contribution tier' : 'Create contribution tier'}</button>
          {editing && <button type="button" className="secondary" onClick={() => { setEditing(''); setForm({ minimum_amount: '0', maximum_amount: '', points: '1', per_user_period_cap: '' }); }}>Cancel</button>}
        </div>
      </form>
      <h3 style={{ fontSize: '1rem', marginBottom: '.75rem' }}>Configured tiers</h3>
      {!error && !bands.length && <p className="empty">No contribution tiers configured. Contribution ranges must not overlap active tiers.</p>}
      <div className="stack">
        {bands.map(band => (
          <article className="card" key={band.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '.75rem', flexWrap: 'wrap' }}>
            <div>
              <strong>{Number(band.minimum_amount).toLocaleString()}–{band.maximum_amount ? Number(band.maximum_amount).toLocaleString() : '∞'} {band.currency}</strong>
              <p style={{ margin: '.25rem 0 0', fontSize: '.875rem', color: 'var(--tv-muted)' }}>{band.points} Impact Points · {band.is_active ? 'Active' : 'Disabled'}</p>
            </div>
            <div style={{ display: 'flex', gap: '.5rem' }}>
              <button type="button" className="secondary sm" onClick={() => edit(band)}>Edit</button>
              <button type="button" className="secondary sm" onClick={() => void toggle(band)}>{band.is_active ? 'Disable' : 'Enable'}</button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
