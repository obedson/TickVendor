import { useEffect, useState } from 'react';
import { apiJson, ApiError } from './api';
import { EmptyState } from './AppShell';

type Opportunity = { id: string; title: string; description: string; activity_type: string; dimension: string; starts_at: string; ends_at: string; location?: string | null; status: string; capacity?: number | null };

const ACTIVITY_TYPES = ['volunteer_work', 'community_service', 'leadership', 'mentoring', 'fundraising', 'advocacy', 'other'];
const DIMENSIONS = ['service', 'leadership', 'community', 'academic'];

const emptyForm = { title: '', description: '', activity_type: 'volunteer_work', dimension: 'service', starts_at: '', ends_at: '', location: '', capacity: '' };

export function OrganizerOpportunities({ token, communityId }: { token: string; communityId?: string }) {
  const [community, setCommunity] = useState('');
  const [items, setItems] = useState<Opportunity[]>([]);
  const [form, setForm] = useState(emptyForm);
  const [showForm, setShowForm] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const headers = { Authorization: `Bearer ${token}` };

  const load = async (id?: string) => {
    setLoading(true);
    try {
      const memberships = await apiJson<{ id: string }[]>('communities/me', {}, token);
      const selected = id || communityId || memberships[0]?.id;
      if (!selected) throw Error('No active community selected.');
      setCommunity(selected);
      setItems(await apiJson<Opportunity[]>(`communities/${selected}/activity-opportunities`, {}, token));
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : cause instanceof Error ? cause.message : 'Unable to load opportunities.');
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [token]);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true); setError(''); setMessage('');
    try {
      const item = await apiJson<Opportunity>(`communities/${community}/activity-opportunities`, {
        method: 'POST',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...form,
          capacity: form.capacity ? Number(form.capacity) : null,
          starts_at: new Date(form.starts_at).toISOString(),
          ends_at: new Date(form.ends_at).toISOString(),
        }),
      }, token);
      setMessage(`Opportunity "${item.title}" created.`);
      setForm(emptyForm);
      setShowForm(false);
      await load(community);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Unable to create opportunity.');
    } finally { setSaving(false); }
  };

  const publish = async (id: string, title: string) => {
    try {
      await apiJson(`activity-opportunities/${id}/publish`, { method: 'POST', headers }, token);
      setMessage(`"${title}" is now published.`);
      await load(community);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Unable to publish opportunity.');
    }
  };

  return (
    <div>
      <div className="page-header">
        <div className="page-header-text">
          <p className="eyebrow">Operations</p>
          <h1>Community opportunities</h1>
          <p>Create and manage participation opportunities for your community.</p>
        </div>
        <div className="page-header-actions">
          {!showForm && (
            <button className="accent" onClick={() => setShowForm(true)}>+ Create opportunity</button>
          )}
        </div>
      </div>

      {message && <p role="status" className="success-msg" style={{ marginBottom: '1rem' }}>{message}</p>}
      {error && <p role="alert" className="error" style={{ marginBottom: '1rem' }}>{error}</p>}

      {showForm && (
        <div className="panel" style={{ marginBottom: '1.5rem' }}>
          <h2 style={{ fontSize: '1.1rem', marginBottom: '1.25rem' }}>Create opportunity</h2>
          <form onSubmit={create}>
            <label>
              <span className="label-text">Title</span>
              <input required value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="e.g. Community Clean-up Day" />
            </label>
            <label>
              <span className="label-text">Description</span>
              <textarea required minLength={10} value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} rows={4} placeholder="Describe the opportunity and what participants will do…" />
            </label>
            <div className="form-row">
              <label>
                <span className="label-text">Activity type</span>
                <select value={form.activity_type} onChange={e => setForm({ ...form, activity_type: e.target.value })}>
                  {ACTIVITY_TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
                </select>
              </label>
              <label>
                <span className="label-text">Dimension</span>
                <select value={form.dimension} onChange={e => setForm({ ...form, dimension: e.target.value })}>
                  {DIMENSIONS.map(d => <option key={d} value={d}>{d}</option>)}
                </select>
              </label>
            </div>
            <div className="form-row">
              <label>
                <span className="label-text">Start date &amp; time</span>
                <input required type="datetime-local" value={form.starts_at} onChange={e => setForm({ ...form, starts_at: e.target.value })} />
              </label>
              <label>
                <span className="label-text">End date &amp; time</span>
                <input required type="datetime-local" value={form.ends_at} onChange={e => setForm({ ...form, ends_at: e.target.value })} />
              </label>
            </div>
            <div className="form-row">
              <label>
                <span className="label-text">Location (optional)</span>
                <input value={form.location} onChange={e => setForm({ ...form, location: e.target.value })} placeholder="Address or online link" />
              </label>
              <label>
                <span className="label-text">Capacity (optional)</span>
                <input type="number" min="1" value={form.capacity} onChange={e => setForm({ ...form, capacity: e.target.value })} placeholder="Leave blank for unlimited" />
              </label>
            </div>
            <div className="form-actions">
              <button type="submit" className="accent" disabled={saving}>{saving ? 'Creating…' : 'Create opportunity'}</button>
              <button type="button" className="secondary" onClick={() => { setShowForm(false); setForm(emptyForm); }}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      {loading && <p role="status" className="text-muted">Loading opportunities…</p>}
      {!loading && !error && !items.length && (
        <EmptyState
          title="No opportunities yet"
          description="Create your first community opportunity to start engaging members."
          action="Create opportunity"
          onAction={() => setShowForm(true)}
        />
      )}

      <div className="grid">
        {items.map(item => (
          <article className="card" key={item.id} style={{ display: 'flex', flexDirection: 'column', gap: '.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '.5rem' }}>
              <h3 style={{ margin: 0, fontSize: '1rem' }}>{item.title}</h3>
              <span className={`chip ${item.status === 'published' ? 'chip-green' : 'chip-default'}`}>{item.status}</span>
            </div>
            <div style={{ display: 'flex', gap: '.35rem', flexWrap: 'wrap' }}>
              <span className="chip chip-teal">{item.dimension}</span>
              <span className="chip chip-default">{item.activity_type.replace(/_/g, ' ')}</span>
            </div>
            <time style={{ fontSize: '.8rem', color: 'var(--tv-muted)' }}>
              {new Date(item.starts_at).toLocaleDateString()} – {new Date(item.ends_at).toLocaleDateString()}
            </time>
            {item.location && <p style={{ fontSize: '.8rem', color: 'var(--tv-muted)', margin: 0 }}>📍 {item.location}</p>}
            {item.capacity && <p style={{ fontSize: '.8rem', color: 'var(--tv-muted)', margin: 0 }}>👥 {item.capacity} capacity</p>}
            {item.status === 'draft' && (
              <button className="accent sm" onClick={() => publish(item.id, item.title)} style={{ alignSelf: 'flex-start', marginTop: '.25rem' }}>
                Publish
              </button>
            )}
          </article>
        ))}
      </div>
    </div>
  );
}
