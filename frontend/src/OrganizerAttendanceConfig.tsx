import { useEffect, useState } from 'react';
import './management.css';
import { apiJson, ApiError, getLiveToken } from './api';

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

  useEffect(() => {
    if (!communityId || !eventId) return;
    apiJson<Config>(`communities/${communityId}/events/${eventId}/attendance-config`, {}, getLiveToken() ?? token)
      .then(setConfig)
      .catch(() => setError('Unable to load attendance configuration.'));
  }, [communityId, eventId, token]);

  const toggle = (field: keyof Config) => setConfig(current => {
    const enabled = !current[field];
    const methodByField: Partial<Record<keyof Config, string>> = {
      qr_attendance_enabled: 'qr',
      geofence_enabled: 'gps',
      organizer_verification_enabled: 'organizer',
      peer_confirmation_enabled: 'peer',
    };
    const method = methodByField[field];
    return {
      ...current,
      [field]: enabled,
      required_verification_methods: !enabled && method
        ? current.required_verification_methods.filter(item => item !== method)
        : current.required_verification_methods,
    };
  });
  const toggleRequired = (method: string) => setConfig(current => ({
    ...current,
    required_verification_methods: current.required_verification_methods.includes(method)
      ? current.required_verification_methods.filter(item => item !== method)
      : [...current.required_verification_methods, method],
  }));

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError(''); setMessage('');
    try {
      await apiJson<Config>(`communities/${communityId}/events/${eventId}/attendance-config`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      }, getLiveToken() ?? token);
      setMessage('Attendance configuration saved.');
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Unable to save attendance configuration');
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
    <form className="management-screen" onSubmit={save}>
      <h4 style={{ marginBottom: '1rem' }}>Attendance configuration</h4>

      <div style={{ marginBottom: '1rem' }}>
        <CheckRow label="QR code verification" field="qr_attendance_enabled" description="Allow check-in via ticket QR code scan." />
        <CheckRow label="GPS / geofence verification" field="geofence_enabled" description="Use the event geofence for participant location check-in." />
        <CheckRow label="Organizer verification" field="organizer_verification_enabled" description="Allow organizers to manually verify attendance." />
        <CheckRow label="Peer confirmation" field="peer_confirmation_enabled" description="Allow participants to confirm each other's attendance." />
      </div>

      <fieldset style={{ marginBottom: '1rem' }}>
        <legend>Required to qualify for attendance</legend>
        <p className="text-muted text-sm" style={{ marginBottom: '.5rem' }}>
          Every selected method is required. Leave all unselected to allow a basic check-in.
        </p>
        {([
          ['qr', 'QR code', config.qr_attendance_enabled],
          ['gps', 'GPS / geofence', config.geofence_enabled],
          ['organizer', 'Organizer verification', config.organizer_verification_enabled],
          ['peer', 'Peer confirmation', config.peer_confirmation_enabled],
        ] as const).map(([method, label, enabled]) => (
          <label key={method} style={{ display: 'inline-flex', alignItems: 'center', gap: '.4rem', marginRight: '1rem' }}>
            <input
              type="checkbox"
              checked={config.required_verification_methods.includes(method)}
              disabled={!enabled}
              onChange={() => toggleRequired(method)}
            />
            <span>{label}</span>
          </label>
        ))}
      </fieldset>

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
