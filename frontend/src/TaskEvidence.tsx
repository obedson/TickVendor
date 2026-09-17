import { useState } from 'react';
import { apiJson } from './api';

export type EvidenceFile = { id: string; filename: string; size_bytes: number };
export function EvidenceFiles({ token, ids }: { token: string; ids: string[] }) {
  const [links, setLinks] = useState<Record<string, { url: string; filename: string }>>({});
  const [error, setError] = useState('');
  return <div>{ids.map(id => links[id] ? <p key={id}><a href={links[id].url} target="_blank" rel="noopener noreferrer">{links[id].filename}</a> <button type="button" onClick={() => setLinks({})}>Refresh expired links</button></p> : <button key={id} type="button" onClick={async () => {
    try { const link = await apiJson<{ url: string; filename: string }>(`task-attachments/${id}`, {}, token); setLinks(v => ({ ...v, [id]: link })); setError(''); }
    catch (e) { setError(e instanceof Error ? e.message : 'Unable to open attachment'); }
  }}>Get private attachment link</button>)}{error && <p role="alert">{error}</p>}</div>;
}

export function EvidenceUpload({ token, assignmentId, files, onChange, onBusy }: { token: string; assignmentId: string; files: EvidenceFile[]; onChange: (files: EvidenceFile[]) => void; onBusy: (value: boolean) => void }) {
  const [error, setError] = useState('');
  const [uploading, setUploading] = useState(false);
  return <section><label>Upload photo or file (JPEG, PNG, WebP or PDF; 5 MB each; up to 10)
    <input type="file" accept="image/jpeg,image/png,image/webp,application/pdf" multiple disabled={uploading || files.length >= 10} onChange={async e => {
      const selected = Array.from(e.target.files || []); e.target.value = '';
      if (selected.length + files.length > 10 || selected.some(f => f.size > 5 * 1024 * 1024)) { setError('Choose up to 10 files, each no larger than 5 MB.'); return; }
      setUploading(true); onBusy(true); setError(''); const next = [...files];
      try { for (const file of selected) { const body = new FormData(); body.append('upload', file); const saved = await apiJson<EvidenceFile>(`task-assignments/${assignmentId}/attachments`, { method: 'POST', body }, token); if (!next.some(f => f.id === saved.id)) next.push(saved); onChange([...next]); } }
      // Keep the specific cause AND say the batch was partially saved: `next` is committed per file,
      // so re-picking everything would be wasted work. Never collapse one into the other.
      catch (e) { setError(`${e instanceof Error ? e.message : 'Upload failed.'} Files already uploaded in this batch have been kept; retry only the remaining ones.`); }
      finally { setUploading(false); onBusy(false); }
    }} /></label>{uploading && <p role="status">Uploading privately…</p>}{error && <p role="alert">{error}</p>}
    {files.map(file => <p key={file.id}>{file.filename} ({Math.ceil(file.size_bytes / 1024)} KB) <button type="button" disabled={uploading} onClick={() => onChange(files.filter(f => f.id !== file.id))}>Remove from submission</button></p>)}
    <p>Files are private to you and authorized reviewers. Removing a file from this draft does not delete an uploaded evidence record.</p></section>;
}

/** Distinguishes a located GPS failure from an unrelated submission failure so callers keep the specific message. */
export class GeolocationError extends Error {
  constructor(message: string) { super(message); this.name = 'GeolocationError'; }
}

export type TaskPosition = { latitude: number; longitude: number; accuracy_meters: number; captured_at: string };

export async function taskPosition(): Promise<TaskPosition> {
  if (!navigator.geolocation) throw new GeolocationError('Geolocation is unavailable in this browser. This task requires valid GPS evidence.');
  const position = await new Promise<GeolocationPosition>((resolve, reject) => {
    try {
      navigator.geolocation.getCurrentPosition(resolve, error => reject(new GeolocationError(error.code === 1 ? 'Location permission was denied. Allow location access to submit this task.' : error.code === 3 ? 'Location lookup timed out. Try again outdoors or with a better signal.' : 'Your device could not determine its location. Try again with location services enabled.')), { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 });
    } catch {
      reject(new GeolocationError('This browser refused the location request. Try again, or ask the organizer to verify this task manually.'));
    }
  });
  return { latitude: position.coords.latitude, longitude: position.coords.longitude, accuracy_meters: position.coords.accuracy, captured_at: new Date(position.timestamp).toISOString() };
}
