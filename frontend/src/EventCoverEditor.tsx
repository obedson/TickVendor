import { useState } from 'react';
import { apiFetchAuth } from './api';

export function EventCoverEditor({ eventId, token, hasCover, onSaved }: { eventId: string; token: string; hasCover: boolean; onSaved: () => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const upload = async (file?: File) => {
    if (!file) return;
    setError(''); setMessage('');
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 5 * 1024 * 1024) {
      setError('Choose a JPEG, PNG, or WebP image up to 5 MB.'); return;
    }
    setBusy(true);
    try {
      const body = new FormData(); body.append('upload', file);
      const response = await apiFetchAuth(`events/${eventId}/cover-image`, { method: 'POST', body }, token);
      if (!response.ok) { const data = await response.json().catch(() => null); throw Error(data?.detail || 'Unable to save event cover.'); }
      await onSaved(); setMessage('Event cover saved.');
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to upload cover.'); }
    finally { setBusy(false); }
  };
  const remove = async () => {
    setBusy(true); setError(''); setMessage('');
    try {
      const response = await apiFetchAuth(`events/${eventId}/cover-image`, { method: 'DELETE' }, token);
      if (!response.ok) throw Error('Unable to remove cover.');
      await onSaved(); setMessage('Event cover removed.');
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to remove cover.'); }
    finally { setBusy(false); }
  };
  return <fieldset><legend>Event cover</legend><p>Use an image you have permission to share. JPEG, PNG, or WebP, up to 5 MB. A wide image works best.</p>
    <label>{hasCover ? 'Replace cover' : 'Upload cover'}<input type="file" accept="image/jpeg,image/png,image/webp" disabled={busy} onChange={event => { void upload(event.target.files?.[0]); event.target.value = ''; }} /></label>
    {hasCover && <button type="button" className="secondary" disabled={busy} onClick={() => void remove()}>Remove cover</button>}
    {busy && <p role="status">Saving cover…</p>}{error && <p role="alert" className="error">{error}</p>}{message && <p role="status">{message}</p>}
  </fieldset>;
}
