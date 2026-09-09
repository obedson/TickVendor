import { useEffect, useState } from 'react';
import { apiJson, ApiError } from './api';
import { EmptyState } from './AppShell';

type Community = {
  id: string;
  community: { name: string; description?: string; logo_url?: string };
  membership: { role: string; status: string; joined_at?: string };
};

const ROLE_COLORS: Record<string, string> = {
  admin: 'chip-blue',
  organizer: 'chip-teal',
  member: 'chip-green',
};

const STATUS_COLORS: Record<string, string> = {
  active: 'chip-green',
  inactive: 'chip-default',
  pending: 'chip-yellow',
};

export function Communities({ token }: { token: string }) {
  const [items, setItems] = useState<Community[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiJson<Community[]>('communities/me', {}, token)
      .then(setItems)
      .catch(e => setError(e instanceof ApiError ? e.message : 'Unable to load communities'))
      .finally(() => setLoading(false));
  }, [token]);

  return (
    <div>
      <div className="page-header">
        <div className="page-header-text">
          <p className="eyebrow">Community</p>
          <h1>Your communities</h1>
          <p>Communities you belong to and your membership status.</p>
        </div>
      </div>

      {loading && <p role="status" className="text-muted">Loading communities…</p>}
      {error && <p role="alert" className="error">{error}</p>}

      {!loading && !error && !items.length && (
        <EmptyState
          title="No community memberships"
          description="You are not a member of any communities yet. Contact a community administrator to join."
        />
      )}

      <div className="grid">
        {items.map(item => (
          <article className="card" key={item.id} style={{ display: 'flex', flexDirection: 'column', gap: '.65rem' }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '.75rem' }}>
              {item.community.logo_url ? (
                <img
                  src={item.community.logo_url}
                  alt=""
                  style={{ width: '2.5rem', height: '2.5rem', borderRadius: 'var(--tv-radius-md)', objectFit: 'cover', flexShrink: 0 }}
                />
              ) : (
                <div style={{ width: '2.5rem', height: '2.5rem', borderRadius: 'var(--tv-radius-md)', background: 'var(--tv-accent-light)', display: 'grid', placeItems: 'center', color: 'var(--tv-accent)', fontWeight: 800, fontSize: '1rem', flexShrink: 0 }}>
                  {item.community.name.slice(0, 1).toUpperCase()}
                </div>
              )}
              <div style={{ flex: 1, minWidth: 0 }}>
                <h3 style={{ margin: 0, fontSize: '1rem' }}>{item.community.name}</h3>
                <div style={{ display: 'flex', gap: '.35rem', marginTop: '.35rem', flexWrap: 'wrap' }}>
                  <span className={`chip ${ROLE_COLORS[item.membership.role] || 'chip-default'}`}>{item.membership.role}</span>
                  <span className={`chip ${STATUS_COLORS[item.membership.status] || 'chip-default'}`}>{item.membership.status}</span>
                </div>
              </div>
            </div>
            {item.community.description && (
              <p style={{ color: 'var(--tv-muted)', fontSize: '.875rem', margin: 0 }}>
                {item.community.description.length > 120 ? item.community.description.slice(0, 120) + '…' : item.community.description}
              </p>
            )}
            {item.membership.joined_at && (
              <p style={{ fontSize: '.75rem', color: 'var(--tv-muted-light)', margin: 0 }}>
                Member since {new Date(item.membership.joined_at).toLocaleDateString(undefined, { month: 'long', year: 'numeric' })}
              </p>
            )}
          </article>
        ))}
      </div>
    </div>
  );
}
