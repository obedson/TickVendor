import { useEffect, useState } from 'react';
import { apiJson, ApiError } from './api';

type Profile = {
  display_name: string;
  bio?: string;
  location?: string;
  photo_url?: string;
  visibility: 'public' | 'members' | 'private';
  impact_points?: number;
  rank?: { name: string } | null;
  badges?: { id: string; name: string }[];
};

export function ProfileEditor({ token }: { token: string }) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [form, setForm] = useState<Partial<Profile>>({});
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiJson<Profile>('profiles/me', {}, token)
      .then(data => {
        setProfile(data);
        setForm({
          display_name: data.display_name,
          bio: data.bio || '',
          location: data.location || '',
          photo_url: data.photo_url || '',
          visibility: data.visibility,
        });
      })
      .catch(e => setError(e instanceof ApiError ? e.message : 'Unable to load profile'))
      .finally(() => setLoading(false));
  }, [token]);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setMessage(''); setError('');
    try {
      const data = await apiJson<Profile>('profiles/me', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      }, token);
      setProfile(data);
      setMessage('Profile saved successfully.');
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Unable to save profile');
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <div>
        <div className="page-header">
          <div className="page-header-text">
            <p className="eyebrow">Account</p>
            <h1>Profile &amp; settings</h1>
          </div>
        </div>
        <p role="status" className="text-muted">Loading profile…</p>
      </div>
    );
  }

  if (error && !profile) {
    return (
      <div>
        <div className="page-header">
          <div className="page-header-text">
            <p className="eyebrow">Account</p>
            <h1>Profile &amp; settings</h1>
          </div>
        </div>
        <p role="alert" className="error">{error}</p>
      </div>
    );
  }

  if (!profile) return null;

  return (
    <div>
      <div className="page-header">
        <div className="page-header-text">
          <p className="eyebrow">Account</p>
          <h1>Profile &amp; settings</h1>
          <p>Manage your public profile and notification preferences.</p>
        </div>
      </div>

      <div className="content-with-aside">
        {/* Profile form */}
        <div className="panel">
          <h2 style={{ fontSize: '1.1rem', marginBottom: '1.25rem' }}>Profile information</h2>

          {message && <p role="status" className="success-msg" style={{ marginBottom: '1rem' }}>{message}</p>}
          {error && <p role="alert" className="error" style={{ marginBottom: '1rem' }}>{error}</p>}

          <form onSubmit={save}>
            <label>
              <span className="label-text">Display name</span>
              <input
                required
                value={form.display_name || ''}
                onChange={e => setForm({ ...form, display_name: e.target.value })}
                placeholder="Your public name"
                autoComplete="name"
              />
            </label>
            <label>
              <span className="label-text">Bio</span>
              <textarea
                value={form.bio || ''}
                onChange={e => setForm({ ...form, bio: e.target.value })}
                placeholder="Tell your community about yourself…"
                rows={4}
                maxLength={500}
              />
              <span style={{ fontSize: '.75rem', color: 'var(--tv-muted)' }}>{(form.bio || '').length}/500</span>
            </label>
            <label>
              <span className="label-text">Location</span>
              <input
                value={form.location || ''}
                onChange={e => setForm({ ...form, location: e.target.value })}
                placeholder="City, Country"
                autoComplete="address-level2"
              />
            </label>
            <label>
              <span className="label-text">Profile photo URL</span>
              <input
                type="url"
                value={form.photo_url || ''}
                onChange={e => setForm({ ...form, photo_url: e.target.value })}
                placeholder="https://example.com/photo.jpg"
              />
            </label>
            <label>
              <span className="label-text">Profile visibility</span>
              <select
                value={form.visibility}
                onChange={e => setForm({ ...form, visibility: e.target.value as Profile['visibility'] })}
              >
                <option value="public">Public — visible to everyone</option>
                <option value="members">Members — visible to community members</option>
                <option value="private">Private — visible only to you</option>
              </select>
            </label>
            <div className="form-actions">
              <button type="submit" className="accent" disabled={busy}>
                {busy ? 'Saving…' : 'Save profile'}
              </button>
            </div>
          </form>
        </div>

        {/* Stats sidebar */}
        <div style={{ display: 'grid', gap: '1rem', alignContent: 'start' }}>
          {/* Avatar */}
          <div className="panel" style={{ textAlign: 'center' }}>
            {profile.photo_url ? (
              <img
                src={profile.photo_url}
                alt={profile.display_name}
                style={{ width: '5rem', height: '5rem', borderRadius: '50%', objectFit: 'cover', margin: '0 auto .75rem', display: 'block', border: '3px solid var(--tv-border)' }}
              />
            ) : (
              <div style={{ width: '5rem', height: '5rem', borderRadius: '50%', background: 'linear-gradient(135deg, var(--tv-accent-light), #a7f3d0)', display: 'grid', placeItems: 'center', margin: '0 auto .75rem', color: 'var(--tv-accent)', fontWeight: 900, fontSize: '2rem' }}>
                {profile.display_name.slice(0, 1).toUpperCase()}
              </div>
            )}
            <strong style={{ display: 'block' }}>{profile.display_name}</strong>
            {profile.rank && <span className="chip chip-teal" style={{ marginTop: '.35rem' }}>{profile.rank.name}</span>}
          </div>

          {/* Impact stats */}
          <div className="card">
            <h3 style={{ fontSize: '.85rem', color: 'var(--tv-muted)', textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: '.5rem' }}>Impact Points</h3>
            <p className="metric" style={{ fontSize: '2rem' }}>{(profile.impact_points ?? 0).toLocaleString()}</p>
          </div>

          {profile.badges && profile.badges.length > 0 && (
            <div className="card">
              <h3 style={{ fontSize: '.85rem', color: 'var(--tv-muted)', textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: '.75rem' }}>Recent badges</h3>
              <div style={{ display: 'flex', gap: '.5rem', flexWrap: 'wrap' }}>
                {profile.badges.slice(0, 6).map(badge => (
                  <span key={badge.id} className="chip chip-teal" title={badge.name}>🏅 {badge.name}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
