import { useEffect, useState } from 'react';
import { apiJson, ApiError, getLiveToken } from './api';
import { enqueueAction, flushActions } from './offlineQueue';
import { EmptyState } from './AppShell';

type Notification = { id: string; title: string; message: string; read_at: string | null; notification_type?: string; created_at?: string };
type Preferences = { in_app_enabled: boolean; email_enabled: boolean; push_enabled: boolean; muted_types: string[] };

const PREF_SETTINGS = [
  { key: 'in_app_enabled' as const, label: 'In-app notifications', description: 'Updates about your participation and account activity.' },
  { key: 'email_enabled' as const, label: 'Email notifications', description: 'Important updates delivered to your email address.' },
  { key: 'push_enabled' as const, label: 'Push notifications', description: 'Time-sensitive updates when push notifications are available.' },
];

export function Notifications({ token }: { token: string }) {
  const [items, setItems] = useState<Notification[]>([]);
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [statusMsg, setStatusMsg] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [showPrefs, setShowPrefs] = useState(false);
  const [filter, setFilter] = useState<'all' | 'unread'>('unread');

  const liveToken = () => getLiveToken() ?? token;

  useEffect(() => {
    const flush = () => flushActions();
    flush();
    window.addEventListener('online', flush);
    Promise.all([
      apiJson<Notification[]>('notifications', {}, liveToken()),
      apiJson<Preferences>('notifications/preferences', {}, liveToken()),
    ])
      .then(([n, p]) => { setItems(n); setPrefs(p); })
      .catch(e => setError(e instanceof ApiError ? e.message : 'Unable to load notifications'))
      .finally(() => setLoading(false));
    return () => window.removeEventListener('online', flush);
  }, [token]);

  const markRead = async (item: Notification) => {
    try {
      await apiJson<unknown>(`notifications/${item.id}/read`, { method: 'POST' }, liveToken());
      setItems(current => current.map(n => n.id === item.id ? { ...n, read_at: new Date().toISOString() } : n));
    } catch {
      await enqueueAction({ kind: 'notification-read', resourceId: item.id });
      setStatusMsg('Read status will sync when you reconnect.');
    }
  };

  const markAllRead = async () => {
    const unread = items.filter(n => !n.read_at);
    await Promise.all(unread.map(n => markRead(n)));
    setStatusMsg('All notifications marked as read.');
  };

  const savePreferences = async (next: Preferences) => {
    try {
      await apiJson<Preferences>('notifications/preferences', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(next) }, liveToken());
      setPrefs(next);
      setStatusMsg('Preferences saved.');
    } catch {
      setStatusMsg('Preferences could not be saved. Please try again.');
    }
  };

  const unreadCount = items.filter(n => !n.read_at).length;
  const filteredItems = filter === 'unread' ? items.filter(n => !n.read_at) : items;

  return (
    <div>
      <div className="page-header">
        <div className="page-header-text">
          <p className="eyebrow">Updates</p>
          <h1>Notifications {unreadCount > 0 && <span className="chip chip-blue" style={{ fontSize: '.75rem', verticalAlign: 'middle' }}>{unreadCount} new</span>}</h1>
        </div>
        <div className="page-header-actions">
          {unreadCount > 0 && (
            <button className="secondary sm" onClick={markAllRead}>Mark all read</button>
          )}
          <button className="secondary sm" onClick={() => setShowPrefs(!showPrefs)}>
            {showPrefs ? 'Hide preferences' : 'Preferences'}
          </button>
        </div>
      </div>

      {loading && <p role="status" className="text-muted">Loading notifications…</p>}
      {error && <p role="alert" className="error">{error}</p>}
      {statusMsg && <p role="status" aria-live="polite" className="info-msg" style={{ marginBottom: '1rem' }}>{statusMsg}</p>}

      {/* Preferences panel */}
      {showPrefs && prefs && (
        <div className="notification-settings" style={{ marginBottom: '1.5rem' }}>
          <h3>Notification preferences</h3>
          {PREF_SETTINGS.map(({ key, label, description }) => (
            <label className="setting-row" key={key}>
              <span>
                <strong>{label}</strong>
                <small>{description}</small>
              </span>
              <label className="toggle" aria-label={label}>
                <input
                  type="checkbox"
                  checked={prefs[key]}
                  onChange={e => savePreferences({ ...prefs, [key]: e.target.checked })}
                />
                <span className="toggle-track" />
              </label>
            </label>
          ))}
        </div>
      )}

      {/* Filter tabs */}
      {!loading && !error && (
        <div style={{ display: 'flex', gap: '.5rem', marginBottom: '1.25rem' }}>
          <button className={filter === 'unread' ? 'accent sm' : 'secondary sm'} onClick={() => setFilter('unread')}>
            Unread {unreadCount > 0 && `(${unreadCount})`}
          </button>
          <button className={filter === 'all' ? 'accent sm' : 'secondary sm'} onClick={() => setFilter('all')}>
            All ({items.length})
          </button>
        </div>
      )}

      {/* Notification list */}
      {!loading && !error && !filteredItems.length && (
        <EmptyState
          title={filter === 'unread' ? 'All caught up!' : 'No notifications yet'}
          description={filter === 'unread' ? 'You have no unread notifications.' : 'Updates about your participation will appear here.'}
          action={filter === 'unread' && items.length > 0 ? 'View all notifications' : undefined}
          onAction={filter === 'unread' && items.length > 0 ? () => setFilter('all') : undefined}
        />
      )}

      <div className="stack">
        {filteredItems.map(item => (
          <article
            key={item.id}
            style={{
              padding: '1rem 1.25rem',
              background: item.read_at ? 'var(--tv-surface)' : 'var(--tv-info-bg)',
              border: `1px solid ${item.read_at ? 'var(--tv-border)' : '#93c5fd'}`,
              borderRadius: 'var(--tv-radius-lg)',
              display: 'flex',
              gap: '1rem',
              alignItems: 'flex-start',
            }}
          >
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '.5rem', marginBottom: '.25rem' }}>
                {!item.read_at && <span style={{ width: '.5rem', height: '.5rem', borderRadius: '50%', background: 'var(--tv-info)', flexShrink: 0 }} aria-label="Unread" />}
                <strong style={{ fontSize: '.9rem' }}>{item.title}</strong>
              </div>
              <p style={{ color: 'var(--tv-muted)', fontSize: '.875rem', margin: 0 }}>{item.message}</p>
              {item.created_at && (
                <time style={{ fontSize: '.75rem', color: 'var(--tv-muted-light)', display: 'block', marginTop: '.35rem' }}>
                  {new Date(item.created_at).toLocaleString()}
                </time>
              )}
            </div>
            {!item.read_at && (
              <button className="secondary sm" onClick={() => markRead(item)} style={{ flexShrink: 0 }}>
                Mark read
              </button>
            )}
          </article>
        ))}
      </div>
    </div>
  );
}
