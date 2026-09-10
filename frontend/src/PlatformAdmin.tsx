/**
 * Platform Administration workspace — restricted to Super Admin role.
 * Provides: Event Category management, User management overview,
 * Organization/Community overview, and platform-level audit.
 */
import { useEffect, useState } from 'react';
import { apiJson, ApiError, getLiveToken } from './api';
import { EmptyState } from './AppShell';

type Category = { id: string; slug: string; name: string; is_active: boolean };
type PlatformUser = { id: string; email: string; role: string; username: string; display_name: string; is_active: boolean; is_email_verified: boolean };
type PlatformCommunity = { id: string; name: string; slug: string; is_active: boolean; member_count?: number };

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
type PlatformView = 'categories' | 'users' | 'communities';

export function PlatformAdmin({ token, userRole }: { token: string; userRole: string }) {
  const [view, setView] = useState<PlatformView>('categories');

  if (userRole !== 'super_admin') {
    return (
      <div className="panel">
        <p role="alert" className="error">Platform Administration is restricted to Super Administrators.</p>
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <div className="page-header-text">
          <p className="eyebrow">Platform</p>
          <h1>Platform Administration</h1>
          <p>Manage platform-wide configuration, categories, and oversight.</p>
        </div>
      </div>

      <nav style={{ display: 'flex', gap: '.5rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
        {([
          { id: 'categories', label: 'Event Categories' },
          { id: 'users', label: 'Users' },
          { id: 'communities', label: 'Communities' },
        ] as { id: PlatformView; label: string }[]).map(item => (
          <button
            key={item.id}
            className={view === item.id ? 'accent sm' : 'secondary sm'}
            onClick={() => setView(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>

      {view === 'categories' && <CategoryManager token={token} />}
      {view === 'users' && <PlatformUsers token={token} />}
      {view === 'communities' && <PlatformCommunities token={token} />}
    </div>
  );
}

// ── Platform Users overview ───────────────────────────────────────────────────
function PlatformUsers({ token }: { token: string }) {
  const [users, setUsers] = useState<PlatformUser[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const liveToken = () => getLiveToken() ?? token;

  useEffect(() => {
    setLoading(true);
    // Use the search endpoint to list users (platform admin can search all).
    apiJson<{ users?: PlatformUser[] }>('search?q=&limit=50', {}, liveToken())
      .then(data => setUsers(data.users ?? []))
      .catch((cause: Error) => setError(cause.message))
      .finally(() => setLoading(false));
  }, [token]);

  return (
    <section className="panel">
      <h2>Platform Users</h2>
      <p style={{ color: 'var(--tv-muted)', marginBottom: '1rem' }}>
        Overview of registered users. Role changes require direct database or API access.
      </p>
      {error && <p role="alert" className="error">{error}</p>}
      {loading && <p role="status" className="text-muted">Loading users…</p>}
      {!loading && !error && !users.length && (
        <EmptyState title="No users found" description="No users returned from search." />
      )}
      <div className="stack">
        {users.map(u => (
          <article key={u.id} className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '.75rem', flexWrap: 'wrap' }}>
            <div>
              <strong>{u.display_name}</strong>
              <p style={{ margin: '.2rem 0 0', fontSize: '.85rem', color: 'var(--tv-muted)' }}>@{u.username} · {u.email}</p>
            </div>
            <span className={`chip ${u.role === 'super_admin' ? 'chip-red' : u.role === 'organizer' ? 'chip-blue' : 'chip-default'}`}>
              {u.role.replace(/_/g, ' ')}
            </span>
          </article>
        ))}
      </div>
    </section>
  );
}

// ── Platform Communities overview ─────────────────────────────────────────────
function PlatformCommunities({ token }: { token: string }) {
  const [communities, setCommunities] = useState<PlatformCommunity[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const liveToken = () => getLiveToken() ?? token;

  useEffect(() => {
    setLoading(true);
    apiJson<{ communities?: PlatformCommunity[] }>('search?q=&limit=50', {}, liveToken())
      .then(data => setCommunities(data.communities ?? []))
      .catch((cause: Error) => setError(cause.message))
      .finally(() => setLoading(false));
  }, [token]);

  return (
    <section className="panel">
      <h2>Platform Communities</h2>
      <p style={{ color: 'var(--tv-muted)', marginBottom: '1rem' }}>
        Overview of all communities on the platform.
      </p>
      {error && <p role="alert" className="error">{error}</p>}
      {loading && <p role="status" className="text-muted">Loading communities…</p>}
      {!loading && !error && !communities.length && (
        <EmptyState title="No communities found" description="No communities returned from search." />
      )}
      <div className="stack">
        {communities.map(c => (
          <article key={c.id} className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '.75rem', flexWrap: 'wrap' }}>
            <div>
              <strong>{c.name}</strong>
              <code style={{ display: 'block', fontSize: '.75rem', color: 'var(--tv-muted)', marginTop: '.2rem' }}>{c.slug}</code>
            </div>
            <span className={`chip ${c.is_active ? 'chip-green' : 'chip-default'}`}>
              {c.is_active ? 'Active' : 'Inactive'}
            </span>
          </article>
        ))}
      </div>
    </section>
  );
}
