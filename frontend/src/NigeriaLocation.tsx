import { useEffect, useState } from 'react';
import { apiJson } from './api';

export function NigeriaLocation({ region, lga, onChange }: { region: string; lga: string; onChange: (region: string, lga: string) => void }) {
  const [locations, setLocations] = useState<Record<string, string[]>>({});
  const [error, setError] = useState(''); const [retry, setRetry] = useState(0);
  useEffect(() => { let active = true; apiJson<Record<string, string[]>>('events/locations/nigeria').then(data => { if (active) { setLocations(data); setError(''); } }).catch(() => { if (active) setError('Unable to load State/LGA options. Your existing location is unchanged.'); }); return () => { active = false; }; }, [retry]);
  return <fieldset><legend>Nigerian State and LGA</legend>{error && <p role="alert">{error} <button type="button" onClick={() => setRetry(value => value + 1)}>Retry locations</button></p>}<div className="form-row">
    <label>State / FCT<select value={region} disabled={!Object.keys(locations).length} onChange={e => onChange(e.target.value, '')}><option value="">Choose state</option>{region && !locations[region] && <option value={region}>{region} (existing region)</option>}{Object.keys(locations).sort().map(state => <option key={state}>{state}</option>)}</select></label>
    <label>LGA / Area council<select value={lga} disabled={!locations[region]} onChange={e => onChange(region, e.target.value)}><option value="">Choose LGA</option>{(locations[region] || []).map(area => <option key={area}>{area}</option>)}</select></label>
  </div><small>City/Town is entered separately. Existing unstructured locations are retained until you select a State/LGA.</small></fieldset>;
}
