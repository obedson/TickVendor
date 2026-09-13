import { useEffect, useState } from 'react';
import { apiJson, getLiveToken } from './api';
import { GovernanceConfirm } from './GovernanceConfirm';

export function PlatformPointCeilings({ token }: { token: string }) {
  const [rows, setRows] = useState<{ source_type: string; maximum_points: number }[]>([]);
  const [source, setSource] = useState('task_completion');
  const [maximum, setMaximum] = useState('');
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState('');
  const load = () => apiJson<typeof rows>('point-ceilings', {}, getLiveToken() || token).then(setRows).catch(e => setError(e.message));
  useEffect(() => { void load(); }, [token]);
  return <section className="panel"><h2>Platform award ceilings</h2><p>Limits apply to new awards, including overrides. Existing posted transactions remain unchanged. Lowering a ceiling limits subsequent rewards and the task display.</p>{error && <p role="alert">{error}</p>}
    <form onSubmit={e => { e.preventDefault(); setConfirming(true); }}><label>Source type<input required pattern="[a-z][a-z0-9_]{1,63}" value={source} onChange={e => setSource(e.target.value)} /></label><label>Maximum points<input required type="number" min={0} max={100000} value={maximum} onChange={e => setMaximum(e.target.value)} /></label><button>Set ceiling</button></form>
    <ul>{rows.map(row => <li key={row.source_type}>{row.source_type.replaceAll('_', ' ')}: {row.maximum_points} points <button className="secondary" onClick={() => { setSource(row.source_type); setMaximum(String(row.maximum_points)); }}>Edit</button></li>)}</ul>
    {confirming && <GovernanceConfirm title="Change platform ceiling" consequence="Community rules and subsequent task awards cannot exceed this value. Historical points are not rewritten." onClose={() => setConfirming(false)} onConfirm={async reason => { await apiJson('point-ceilings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ source_type: source, maximum_points: Number(maximum), reason }) }, getLiveToken() || token); await load(); }} />}
  </section>;
}
