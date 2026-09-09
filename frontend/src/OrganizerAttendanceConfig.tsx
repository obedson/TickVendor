import { useState } from 'react';
import { apiFetch } from './api';

type Config = {
  qr_attendance_enabled: boolean;
  geofence_enabled: boolean;
  organizer_verification_enabled: boolean;
  peer_confirmation_enabled: boolean;
  geofence_radius_meters: number;
  max_peer_confirmations: number;
  confirmations_required: number;
  peer_selection_limit: number;
  required_verification_methods: string[];
};

const initial: Config = {
  qr_attendance_enabled: true,
  geofence_enabled: false,
  organizer_verification_enabled: true,
  peer_confirmation_enabled: false,
  geofence_radius_meters: 100,
  max_peer_confirmations: 3,
  confirmations_required: 0,
  peer_selection_limit: 5,
  required_verification_methods: [],
};

export function OrganizerAttendanceConfig({ token, communityId, eventId }: { token: string; communityId: string; eventId: string }) {
  const [config, setConfig] = useState(initial);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const toggle = (field: keyof Config) => setConfig(current => ({ ...current, [field]: !current[field] }));

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError(''); setMessage('');
    try {
      const response = await apiFetch(`communities/${communityId}/events/${eventId}/attendance-config`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      const data = await response.json();
      if (!response.ok) throw Error(data.detail || 'Unable to save attendance configuration');
      setMessage('Attendance configuration saved.');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to save attendance configuration');
    } finally { setBusy(false); }
  };

  const CheckRow = ({ label, field, description }: { label: string; field: keyof Config; description?: string }) => (
    <label style={{ display: 'flex', alignItems: 'flex-start', gap: '.75rem', padding: '.75rem 0', borderTop: '1px solid var(--tv-border)', margin: 0, cursor: 'pointer' }}>
      <input
        type="checkbox"
        checked={config[field] as boolean}
        onChange={() => toggle(field)}
        style={{ marginTop: '.15rem', flexShrink: 0 }}
      />
      <span>
        <strong style={{ display: 'block', fontSize: '.875rem' }}>{label}</strong>
        {description && <small style={{ color: 'var(--tv-muted)', fontSize: '.8rem' }}>{description}</small>}
      </span>
    </label>
  );

  return (
    <form onSubmit={save}>
      <h4 style={{ marginBottom: '1rem' }}>Attendance configuration</h4>

      <div style={{ marginBottom: '1rem' }}>
        <CheckRow label="QR code verification" field="qr_attendance_enabled" description="Allow check-in via ticket QR code scan." />
        <CheckRow label="GPS / geofence verification" field="geofence_enabled" description="Require participants to be within the event geofence." />
        <CheckRow label="Organizer verification" field="organizer_verification_enabled" description="Allow organizers to manually verify attendance." />
        <CheckRow label="Peer confirmation" field="peer_confirmation_enabled" description="Allow participants to confirm each other's attendance." />
      </div>

      {config.geofence_enabled && (
        <label style={{ marginBottom: '1rem' }}>
          <span className="label-text">Geofence radius (meters)</span>
          <input type="number" min="10" max="10000" value={config.geofence_radius_meters} onChange={e => setConfig({ ...config, geofence_radius_meters: Number(e.target.value) })} />
        </label>
      )}

      {config.peer_confirmation_enabled && (
        <div className="form-row" style={{ marginBottom: '1rem' }}>
          <label>
            <span className="label-text">Required peer confirmations</span>
            <input type="number" min="0" max="100" value={config.confirmations_required} onChange={e => setConfig({ ...config, confirmations_required: Number(e.target.value) })} />
          </label>
          <label>
            <span className="label-text">Max confirmations per user</span>
            <input type="number" min="1" max="100" value={config.max_peer_confirmations} onChange={e => setConfig({ ...config, max_peer_confirmations: Number(e.target.value) })} />
          </label>
        </div>
      )}

      {message && <p role="status" className="success-msg" style={{ marginBottom: '.75rem' }}>{message}</p>}
      {error && <p role="alert" className="error" style={{ marginBottom: '.75rem' }}>{error}</p>}

      <button type="submit" className="accent sm" disabled={busy}>
        {busy ? 'Saving…' : 'Save attendance settings'}
      </button>
    </form>
  );
}
