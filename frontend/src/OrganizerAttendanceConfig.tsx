import { lazy, Suspense, useEffect, useState } from 'react';
import './management.css';
import { apiJson, ApiError, getLiveToken } from './api';
import { resolveSelfServiceToggle, toCheckoutInput, toCheckoutInstant } from './attendanceConfigForm';

const MapboxVenuePicker = lazy(() => import('./MapboxVenuePicker'));

type Config = {
  latitude: string | number | null;
  longitude: string | number | null;
  qr_attendance_enabled: boolean;
  geofence_enabled: boolean;
  organizer_verification_enabled: boolean;
  peer_confirmation_enabled: boolean;
  geofence_radius_meters: number;
  geofence_max_accuracy_meters: number;
  confirmations_required: number;
  peer_selection_limit: number;
  required_verification_methods: string[];
  self_check_in_enabled: boolean;
  self_checkout_enabled: boolean;
  /** Held in the wall-clock form the datetime input speaks; converted to an instant on save. */
  checkout_opens_at: string | null;
};

const initial: Config = {
  latitude: null, longitude: null,
  qr_attendance_enabled: true,
  geofence_enabled: false,
  organizer_verification_enabled: true,
  peer_confirmation_enabled: false,
  geofence_radius_meters: 100,
  geofence_max_accuracy_meters: 50,
  confirmations_required: 0,
  peer_selection_limit: 5,
  required_verification_methods: [],
  self_check_in_enabled: false,
  self_checkout_enabled: false,
  checkout_opens_at: null,
};

export function OrganizerAttendanceConfig({ token, communityId, eventId }: { token: string; communityId: string; eventId: string }) {
  const [config, setConfig] = useState(initial);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!communityId || !eventId) return;
    apiJson<Config>(`communities/${communityId}/events/${eventId}/attendance-config`, {}, getLiveToken() ?? token)
      .then(loaded => setConfig({ ...loaded, checkout_opens_at: toCheckoutInput(loaded.checkout_opens_at) }))
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
    const next: Config = {
      ...current,
      [field]: enabled,
      required_verification_methods: !enabled && method
        ? current.required_verification_methods.filter(item => item !== method)
        : current.required_verification_methods,
    };
    // Self check-in and self checkout are two halves of one journey, so they move together: see
    // `resolveSelfServiceToggle`. Everything else here is a switch of its own.
    return field === 'self_check_in_enabled' || field === 'self_checkout_enabled'
      ? { ...next, ...resolveSelfServiceToggle(next, field, enabled) }
      : next;
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
        body: JSON.stringify({
          ...config,
          latitude: config.latitude === '' ? null : config.latitude,
          longitude: config.longitude === '' ? null : config.longitude,
          // Blank means no checkout window; the API takes null and rejects an empty string.
          checkout_opens_at: toCheckoutInstant(config.checkout_opens_at),
        }),
      }, getLiveToken() ?? token);
      setMessage('Attendance configuration saved.');
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Unable to save attendance configuration');
    } finally { setBusy(false); }
  };

  const CheckRow = ({ label, field, description, disabled }: { label: string; field: keyof Config; description?: string; disabled?: boolean }) => (
    <label style={{ display: 'flex', alignItems: 'flex-start', gap: '.75rem', padding: '.75rem 0', borderTop: '1px solid var(--tv-border)', margin: 0, cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.6 : 1 }}>
      <input
        type="checkbox"
        checked={config[field] as boolean}
        disabled={disabled}
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
        <legend>Participant self service</legend>
        <p className="text-muted text-sm" style={{ marginBottom: '.5rem' }}>
          Let participants record their own attendance from their ticket instead of an organizer scanning it.
          Both are off unless they are switched on here.
        </p>
        <CheckRow
          label="Allow participant self check-in"
          field="self_check_in_enabled"
          description="Participants can check themselves in from their own ticket. Turning this off also turns self checkout off."
        />
        <CheckRow
          label="Allow participant self checkout"
          field="self_checkout_enabled"
          disabled={!config.self_check_in_enabled}
          description={config.self_check_in_enabled
            ? 'Participants can finalize their own attendance after checking in.'
            : 'Self checkout needs self check-in: nobody can check out who was never checked in.'}
        />
        {config.self_checkout_enabled && (
          <label style={{ display: 'block', padding: '.25rem 0 0' }}>
            <span className="label-text">Checkout opens at</span>
            <input
              type="datetime-local"
              value={config.checkout_opens_at ?? ''}
              onChange={e => setConfig({ ...config, checkout_opens_at: e.target.value })}
            />
            <small style={{ display: 'block', color: 'var(--tv-muted)', fontSize: '.8rem' }}>
              Optional, in your local time. Leave blank to allow checkout as soon as a participant has checked in.
            </small>
          </label>
        )}
      </fieldset>

      {config.geofence_enabled && <fieldset><legend>Attendance location</legend>
        <p>Click the map or drag its marker to the exact venue. The shaded circle is the permitted check-in area.</p>
        <Suspense fallback={<p className="info-msg">Loading venue map…</p>}>
          <MapboxVenuePicker
            latitude={config.latitude === '' || config.latitude == null ? null : Number(config.latitude)}
            longitude={config.longitude === '' || config.longitude == null ? null : Number(config.longitude)}
            radiusMeters={config.geofence_radius_meters}
            onChange={(latitude, longitude) => setConfig(current => ({ ...current, latitude: latitude.toFixed(6), longitude: longitude.toFixed(6) }))}
          />
        </Suspense>
        <div className="form-row"><label>Latitude<input type="number" required min={-90} max={90} step="any" value={config.latitude ?? ''} onChange={e => setConfig({ ...config, latitude: e.target.value })} /></label><label>Longitude<input type="number" required min={-180} max={180} step="any" value={config.longitude ?? ''} onChange={e => setConfig({ ...config, longitude: e.target.value })} /></label></div>
      </fieldset>}
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
        <fieldset style={{ marginBottom: '1rem' }}>
          <legend>Location verification thresholds</legend>
          <div className="form-row">
            <label><span className="label-text">Allowed distance from venue (meters)</span>
              <input type="number" min="10" max="10000" value={config.geofence_radius_meters} onChange={e => setConfig({ ...config, geofence_radius_meters: Number(e.target.value) })} />
              <small>Participants outside this radius cannot self-check in.</small>
            </label>
            <label><span className="label-text">Maximum device accuracy for automatic verification (meters)</span>
              <input type="number" min="5" max="10000" value={config.geofence_max_accuracy_meters} onChange={e => setConfig({ ...config, geofence_max_accuracy_meters: Number(e.target.value) })} />
              <small>In-range readings less precise than this go to organizer review.</small>
            </label>
          </div>
        </fieldset>
      )}

      {config.peer_confirmation_enabled && (
        <div style={{ marginBottom: '1rem' }}>
          <label>
            <span className="label-text">Minimum confirmations each attendee must receive</span>
            <input type="number" min="0" max="100" value={config.confirmations_required} onChange={e => setConfig({ ...config, confirmations_required: Number(e.target.value) })} />
            <small>Confirmations must come from distinct eligible peers. Each peer can confirm a particular attendee only once.</small>
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
