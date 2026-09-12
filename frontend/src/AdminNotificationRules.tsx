import { useEffect, useState } from 'react';
import './management.css';
import { apiJson, ApiError, getLiveToken } from './api';

type Rule = { id: string; notification_type: string; in_app_enabled: boolean; email_enabled: boolean; push_enabled: boolean; is_active: boolean };
export function AdminNotificationRules({ token, communityId }: { token: string; communityId?: string }) {
  const [community, setCommunity] = useState(communityId ?? '');
  const [rules, setRules] = useState<Rule[]>([]);
  const [type, setType] = useState('event_reminder');
  const [inApp, setInApp] = useState(true);
  const [email, setEmail] = useState(false);
  const [push, setPush] = useState(false);
  const [active, setActive] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const liveToken = () => getLiveToken() ?? token;
  const load = async (id: string) => {
    setRules(await apiJson<Rule[]>(`admin/communities/${id}/notification-rules`, {}, liveToken()));
  };
  useEffect(() => {
    (async () => {
      try {
        const id = community || (await apiJson<any[]>('communities/me', {}, liveToken()))[0]?.id;
        if (!id) throw Error('No community is available for administration.');
        setCommunity(id); await load(id);
      } catch (cause) { setError(cause instanceof ApiError ? cause.message : 'Unable to load notification rules.'); }
    })();
  }, [token]);
  const save = async (event: React.FormEvent) => {
    event.preventDefault(); if (!community) return; setError(''); setMessage('');
    try {
      await apiJson<Rule>(`admin/communities/${community}/notification-rules`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ notification_type: type, in_app_enabled: inApp, email_enabled: email, push_enabled: push, is_active: active }) }, liveToken());
      setMessage('Notification rule saved.'); await load(community);
    } catch (cause) { setError(cause instanceof ApiError ? cause.message : 'Unable to save notification rule.'); }
  };
  return <section className="panel management-screen"><h2>Notification rules</h2><p>Configure delivery channels for this community.</p>{error && <p role="alert" className="error">{error}</p>}{message && <p role="status">{message}</p>}<form onSubmit={save}><label>Notification type<input required value={type} onChange={event => setType(event.target.value)} /></label><label><input type="checkbox" checked={inApp} onChange={event => setInApp(event.target.checked)} /> In-app enabled</label><label><input type="checkbox" checked={email} onChange={event => setEmail(event.target.checked)} /> Email enabled</label><label><input type="checkbox" checked={push} onChange={event => setPush(event.target.checked)} /> Push enabled</label><label><input type="checkbox" checked={active} onChange={event => setActive(event.target.checked)} /> Rule active</label><button>Save notification rule</button></form><h3>Configured rules</h3>{rules.length ? rules.map(rule => <p key={rule.id}>{rule.notification_type} · {rule.is_active ? 'Active' : 'Disabled'} · {rule.email_enabled ? 'Email' : 'No email'} · {rule.push_enabled ? 'Push' : 'No push'}</p>) : <p className="empty">No notification rules configured.</p>}</section>;
}
