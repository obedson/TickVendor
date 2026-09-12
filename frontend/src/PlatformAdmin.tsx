/**
 * Platform Administration workspace — restricted to Super Admin role.
 * Provides: Event Category management, User management overview,
 * Organization/Community overview, and platform-level audit.
 */
import { useEffect, useState } from 'react';
import { apiJson, ApiError, getLiveToken } from './api';
import { PlatformGovernance } from './PlatformGovernance';
import { EmptyState } from './AppShell';

type Category = { id: string; slug: string; name: string; is_active: boolean };

// ── Event Category Management ─────────────────────────────────────────────────
function CategoryManager({ token }: { token: string }) {
  const [categories, setCategories] = useState<Category[]>([]);
  const [form, setForm] = useState({ name: '', slug: '' });
  const [editing, setEditing] = useState<Category | null>(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [saving, setSaving] = useState(false);

  const liveToken = () => getLiveToken() ?? token;

  const load = async () => {
    try {
      // Use the authenticated /admin/categories endpoint with active_only=false
      // so super_admin sees all categories including inactive ones.
      setCategories(await apiJson<Category[]>('admin/categories?active_only=false', {}, liveToken()));
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Unable to load categories.');
    }
  };

  useEffect(() => { load(); }, [token]);

  const slugify = (name: string) => name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true); setError(''); setMessage('');
    try {
      if (editing) {
        await apiJson<Category>(`admin/categories/${editing.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: form.name, slug: form.slug }),
        }, liveToken());
        setMessage(`Category "${form.name}" updated.`);
      } else {
        await apiJson<Category>('admin/categories', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: form.name, slug: form.slug, is_active: true }),
        }, liveToken());
        setMessage(`Category "${form.name}" created.`);
      }
      setForm({ name: '', slug: '' });
      setEditing(null);
      await load();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Unable to save category.');
    } finally { setSaving(false); }
  };

  const toggleActive = async (cat: Category) => {
    setError(''); setMessage('');
    try {
      await apiJson<Category>(`admin/categories/${cat.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: !cat.is_active }),
      }, liveToken());
      setMessage(`Category "${cat.name}" ${cat.is_active ? 'deactivated' : 'activated'}.`);
      await load();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Unable to update category.');
    }
  };

  const beginEdit = (cat: Category) => {
    setEditing(cat);
    setForm({ name: cat.name, slug: cat.slug });
  };

  return (
    <section className="panel" style={{ marginBottom: '1.5rem' }}>
      <h2>Event Categories</h2>
      <p style={{ color: 'var(--tv-muted)', marginBottom: '1.25rem' }}>
        Manage the event categories available to organizers. Only active categories can be selected when creating events.
      </p>
      {error && <p role="alert" className="error">{error}</p>}
      {message && <p role="status" className="success-msg">{message}</p>}

      <form onSubmit={save} style={{ display: 'grid', gap: '.75rem', marginBottom: '1.5rem' }}>
        <div className="form-row">
          <label>
            <span className="label-text">Category name</span>
            <input
              required
              value={form.name}
              onChange={e => setForm({ name: e.target.value, slug: editing ? form.slug : slugify(e.target.value) })}
              placeholder="e.g. Technology"
            />
          </label>
          <label>
            <span className="label-text">Slug (identifier)</span>
            <input
              required
              value={form.slug}
              onChange={e => setForm({ ...form, slug: slugify(e.target.value) })}
              placeholder="e.g. technology"
              pattern="[a-z0-9-]+"
            />
          </label>
        </div>
        <div className="form-actions">
          <button type="submit" className="accent" disabled={saving}>
            {saving ? 'Saving…' : editing ? 'Update category' : 'Create category'}
          </button>
          {editing && (
            <button type="button" className="secondary" onClick={() => { setEditing(null); setForm({ name: '', slug: '' }); }}>
              Cancel
            </button>
          )}
        </div>
      </form>

      <h3 style={{ fontSize: '1rem', marginBottom: '.75rem' }}>All categories</h3>
      {!categories.length && <EmptyState title="No categories" description="Create the first event category above." />}
      <div className="stack">
        {categories.map(cat => (
          <article key={cat.id} className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '.75rem', flexWrap: 'wrap' }}>
            <div>
              <strong>{cat.name}</strong>
              <code style={{ display: 'block', fontSize: '.75rem', color: 'var(--tv-muted)', marginTop: '.2rem' }}>{cat.slug}</code>
            </div>
            <div style={{ display: 'flex', gap: '.5rem', alignItems: 'center' }}>
              <span className={`chip ${cat.is_active ? 'chip-green' : 'chip-default'}`}>
                {cat.is_active ? 'Active' : 'Inactive'}
              </span>
              <button className="secondary sm" onClick={() => beginEdit(cat)}>Edit</button>
              <button className="secondary sm" onClick={() => void toggleActive(cat)}>
                {cat.is_active ? 'Deactivate' : 'Activate'}
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

// ── Platform Admin Shell ──────────────────────────────────────────────────────
export function PlatformAdmin({ token, userRole }: { token: string; userRole: string }) {
  return <PlatformGovernance token={token} userRole={userRole} categories={<CategoryManager token={token} />} />;
}
