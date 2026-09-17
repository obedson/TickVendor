import { useEffect, useState } from 'react';
import { apiJson } from './api';
import { TaskDialog } from './RevealFocus';
import { EvidenceFiles } from './TaskEvidence';

export function TaskDetail({ token, taskId, onClose, onSubmit, onChanged }: { token: string; taskId: string; onClose: () => void; onSubmit: () => void; onChanged: () => void }) {
  const [detail, setDetail] = useState<any>(null); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  const load = () => apiJson<any>(`tasks/${taskId}`, {}, token).then(setDetail).catch(e => setError(e.message));
  useEffect(() => { load(); }, [taskId, token]);
  const transition = async (action: string) => { setBusy(true); setError(''); try { await apiJson(`task-assignments/${detail.assignment.id}/${action}`, { method: 'POST' }, token); await load(); onChanged(); } catch (e) { setError(e instanceof Error ? e.message : 'Unable to update task'); } finally { setBusy(false); } };
  return <TaskDialog title={detail?.title || 'Task details'} onClose={onClose}><section className="panel" style={{ maxWidth: '45rem' }}>
    {error && <p role="alert">{error} <button onClick={load}>Retry</button></p>}{!detail && !error && <p role="status">Loading task…</p>}
    {detail && <><h2>{detail.title}</h2><p style={{ whiteSpace: 'pre-wrap' }}>{detail.description}</p><p>{detail.task_type} · {detail.priority} · {detail.impact_point_reward} effective Impact Points</p><p>{detail.due_at ? `Due ${new Date(detail.due_at).toLocaleString()}` : 'No deadline'}</p>
      <p>{detail.verification_required ? 'Organizer approval required after submission.' : 'Valid submissions complete automatically.'} Evidence: {detail.required_evidence_types.join(', ') || 'No text, URL or file evidence required'}.</p>
      {detail.task_config?.instructions && <p>{detail.task_config.instructions}</p>}{detail.task_config?.location && <p>Location: {detail.task_config.location}</p>}
      {detail.task_config?.geofence?.required && <p>Fresh GPS evidence required within {detail.task_config.geofence.radius_meters} metres of {detail.task_config.geofence.address || 'the configured location'} ({detail.task_config.geofence.latitude}, {detail.task_config.geofence.longitude}).</p>}
      {['video_url', 'profile_url', 'survey_url'].map(key => /^https?:\/\//i.test(detail.task_config?.[key] || '') && <p key={key}><a href={detail.task_config[key]} target="_blank" rel="noopener noreferrer">Open {key.replace('_url', '')}</a></p>)}
      {(detail.attachments || []).map((url: string) => /^https?:\/\//i.test(url) && <p key={url}><a href={url} target="_blank" rel="noopener noreferrer">Task resource</a></p>)}
      <p>Status: {detail.assignment?.status || 'Not assigned to you'}</p>{detail.assignment?.rejection_reason && <p>Reviewer feedback: {detail.assignment.rejection_reason}</p>}
      <div className="form-actions">{detail.assignment?.status === 'assigned' && <button disabled={busy} onClick={() => transition('accept')}>Accept task</button>}{detail.assignment?.status === 'accepted' && <button disabled={busy} onClick={() => transition('start')}>Start task</button>}{['assigned', 'accepted', 'in_progress', 'rejected'].includes(detail.assignment?.status) && <button disabled={busy} onClick={onSubmit}>Submit evidence</button>}</div>
      <h3>Your submission history (latest 20)</h3>{!detail.history.length && <p>No submissions yet.</p>}{detail.history.map((row: any) => <article key={row.id}><p>{new Date(row.submitted_at).toLocaleString()}</p><p>{row.evidence_text}</p>{row.result?.passed !== undefined && <p>Assessment {row.result.passed ? 'passed' : 'not passed'}; attempt {row.result.attempt}{row.result.score !== undefined ? `; score ${row.result.score}%` : ''}</p>}{row.location_evidence?.verified && <p>GPS verified at submission{row.location_evidence.distance_meters !== undefined ? `; ${row.location_evidence.distance_meters} metres from the task location` : ''}.</p>}
        {/^https?:\/\//i.test(row.evidence_url || '') && <p><a href={row.evidence_url} target="_blank" rel="noopener noreferrer">View evidence link →</a></p>}
        <EvidenceFiles token={token} ids={row.attachment_ids || []} />
        {(row.evidence_attachments || []).length > 0 && <><p>Attachment links:</p><ul>{row.evidence_attachments.map((url: string, index: number) => <li key={index}>{/^https?:\/\//i.test(url) ? <a href={url} target="_blank" rel="noopener noreferrer">{url}</a> : url}</li>)}</ul></>}
      </article>)}</>}
    <button onClick={onClose}>Close</button></section></TaskDialog>;
}
