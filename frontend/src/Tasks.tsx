import { useEffect, useState } from 'react';
import { apiJson, ApiError, getLiveToken } from './api';
import { useDraftState } from './formRecovery';
import { TaskDialog, useRevealFocus } from './RevealFocus';
import { LearningAnswers, type LearningConfig } from './LearningTask';
import { GovernanceConfirm } from './GovernanceConfirm';
import { EmptyState } from './AppShell';
import { PersonalHistory, usePersonalArchive } from './PersonalHistory';

type TaskConfig = LearningConfig & {
  video_url?: string;
  platform?: string;
  handle?: string;
  profile_url?: string;
  survey_url?: string;
  survey_title?: string;
  referral_target?: string;
  min_referrals?: number;
  location?: string;
  instructions?: string;
};

type Task = {
  id: string;
  title: string;
  community_id: string;
  description: string;
  due_at?: string | null;
  priority: string;
  impact_point_reward: number;
  verification_required: boolean;
  event_id?: string | null;
  status: string;
  task_type?: string;
  task_config?: TaskConfig;
  required_evidence_types?: string[];
};
type Assignment = { assessment_result?: { passed?: boolean; score?: number; attempt?: number; attempts_remaining?: number }; id: string; task_id: string; status: string; due_at?: string | null };

const PRIORITY_COLORS: Record<string, string> = {
  high: 'chip-red',
  medium: 'chip-yellow',
  low: 'chip-blue',
};

const STATUS_COLORS: Record<string, string> = {
  assigned: 'chip-blue',
  submitted: 'chip-yellow',
  verified: 'chip-green',
  rejected: 'chip-red',
};

export function Tasks({ token, communityId }: { token: string; communityId?: string }) {
  const archive = usePersonalArchive(token, 'task');
  const [tasks, setTasks] = useState<Task[]>([]);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [selected, setSelected] = useState<Task | null>(null);
  const draft = useDraftState(selected ? `community:${selected.community_id}:task:${selected.id}:evidence` : '', { evidence: '', url: '', attachments: [''], answers: {} as Record<string, any>, requestKey: '' });
  const evidence = draft.value.evidence; const evidenceUrl = draft.value.url; const evidenceAttachments = draft.value.attachments;
  const setEvidence = (evidence: string) => draft.set(value => ({ ...value, evidence, requestKey: '' }));
  const setEvidenceUrl = (url: string) => draft.set(value => ({ ...value, url, requestKey: '' }));
  const setEvidenceAttachments = (attachments: string[]) => draft.set(value => ({ ...value, attachments, requestKey: '' }));
  const [discardDraft, setDiscardDraft] = useState(false);
  const [urlError, setUrlError] = useState('');
  const [statusMsg, setStatusMsg] = useState('');
  const [error, setError] = useState('');
  useRevealFocus(error, 'dialog[open] [role="alert"]');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [noCommunity, setNoCommunity] = useState(false);
  const [filter, setFilter] = useState<'all' | 'active' | 'completed'>('active');

  const liveToken = () => getLiveToken() ?? token;

  const load = async () => {
    setLoading(true);
    setNoCommunity(false);
    try {
      const communities = communityId ? [{ id: communityId }] : await apiJson<{ id: string }[]>('communities/me', {}, liveToken());
      const id = communityId || communities.find((item: any) => item.membership?.status === 'active' && item.community?.is_active !== false)?.id;
      if (!id) { setNoCommunity(true); setTasks([]); setAssignments([]); return; }
      const [a, t] = await Promise.all([
        apiJson<Assignment[]>('task-assignments/me', {}, liveToken()),
        apiJson<Task[]>(`communities/${id}/tasks`, {}, liveToken()),
      ]);
      setAssignments(a);
      setTasks(t);
      setError('');
    } catch (e) {
      setError(e instanceof ApiError ? e.message : e instanceof Error ? e.message : 'Unable to load tasks');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [token, communityId]);

  const validateUrl = (url: string): boolean => {
    if (!url) return true;
    try { new URL(url); return true; } catch { return false; }
  };

  const submit = async () => {
    if (!selected) return;
    const assignment = assignments.find(item => item.task_id === selected.id);
    if (!assignment) { setError('This task is not assigned to you.'); return; }

    // Client-side validation per required_evidence_types
    const required = selected.required_evidence_types || ['text'];
    if (required.includes('text') && !evidence.trim()) {
      setError('Please provide a text description of your evidence.'); return;
    }
    if (required.includes('url') && !evidenceUrl.trim()) {
      setError('Please provide a URL as evidence.'); return;
    }
    if (evidenceUrl && !validateUrl(evidenceUrl)) {
      setError('Please enter a valid URL (e.g. https://example.com).'); return;
    }
    const validAttachments = evidenceAttachments.filter(a => a.trim());
    if (required.includes('attachment') && validAttachments.length === 0) {
      setError('Please provide at least one attachment URL.'); return;
    }
    for (const att of validAttachments) {
      if (!validateUrl(att)) { setError(`Invalid attachment URL: ${att}`); return; }
    }

    setBusy(true);
    setError('');
    try {
      const requestKey = draft.value.requestKey || crypto.randomUUID();
      draft.set(value => ({ ...value, requestKey }));
      await draft.flush();
      const result = await apiJson<{ assessment_result?: { passed?: boolean; score?: number; attempts_remaining?: number } }>(`task-assignments/${assignment.id}/submissions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          answers: draft.value.answers,
          idempotency_key: requestKey,
          evidence_text: evidence.trim() || null,
          evidence_url: evidenceUrl.trim() || null,
          evidence_attachments: validAttachments,
        }),
      }, liveToken());
      if (result.assessment_result?.passed === false) { setError(`Assessment score: ${result.assessment_result.score}%. Attempts remaining: ${result.assessment_result.attempts_remaining}. Review and try again.`); draft.set(value => ({ ...value, requestKey: '' })); return; }
      await draft.clear();
      setStatusMsg(`${selected.verification_required ? 'Submitted for verification.' : 'Task completed!'}${result.assessment_result?.score !== undefined ? ` Assessment passed: ${result.assessment_result.score}%.` : ''}`);
      setSelected(null);

      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Unable to submit task');
    } finally {
      setBusy(false);
    }
  };

  const filteredTasks = tasks.filter(task => {
    const assignment = assignments.find(a => a.task_id === task.id);
    if (assignment && archive.ids.has(assignment.id)) return false;
    const status = assignment?.status || 'available';
    if (filter === 'active') return !['verified', 'rejected'].includes(status);
    if (filter === 'completed') return ['verified', 'rejected'].includes(status);
    return true;
  });

  return (
    <div>
      <div className="page-header">
        <div className="page-header-text">
          <p className="eyebrow">Participation</p>
          <h1>Tasks</h1>
          <p>Complete tasks to earn Impact Points and contribute to your community.</p>
        </div>
      </div>

      <PersonalHistory token={token} kind="task" title="Completed, history and archived assignments" />
      {archive.error && <p role="alert" className="error">{archive.error}</p>}
      {loading && <p role="status" className="text-muted">Loading tasks…</p>}
      {error && <p role="alert" className="error">{error}</p>}
      {statusMsg && <p role="status" className="success-msg" style={{ marginBottom: '1rem' }}>{statusMsg}</p>}

      {!loading && !error && noCommunity && (
        <EmptyState
          title="Join a community to view tasks"
          description="Tasks are created within communities. Join a community to see available tasks."
        />
      )}

      {!loading && !error && !noCommunity && (
        <>
          {/* Filter tabs */}
          <div style={{ display: 'flex', gap: '.5rem', marginBottom: '1.25rem', flexWrap: 'wrap' }}>
            {(['active', 'all', 'completed'] as const).map(f => (
              <button
                key={f}
                className={filter === f ? 'accent sm' : 'secondary sm'}
                onClick={() => setFilter(f)}
              >
                {f === 'active' ? 'Active' : f === 'all' ? 'All tasks' : 'Completed'}
              </button>
            ))}
          </div>

          {!filteredTasks.length && (
            <EmptyState
              title={filter === 'active' ? 'No active tasks' : filter === 'completed' ? 'No completed tasks' : 'No tasks available'}
              description="There are no tasks matching this filter for your community right now."
            />
          )}

          <div className="grid">
            {filteredTasks.map(task => {
              const assignment = assignments.find(a => a.task_id === task.id);
              const status = assignment?.status || 'available';
              const canSubmit = assignment && !['submitted', 'verified', 'rejected'].includes(status);

              const taskTypeLabel: Record<string, string> = {
                video: '▶ Video', social_follow: '♡ Social', survey: '📋 Survey',
                referral: '👥 Referral', physical: '🔧 Physical', general: '',
              };
              const config = task.task_config || {};

              return (
                <article className="card" key={task.id} style={{ display: 'flex', flexDirection: 'column', gap: '.5rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '.5rem' }}>
                    <h3 style={{ margin: 0, fontSize: '1rem' }}>{task.title}</h3>
                    <span className={`chip ${PRIORITY_COLORS[task.priority] || 'chip-default'}`}>{task.priority}</span>
                  </div>
                  <p style={{ color: 'var(--tv-muted)', fontSize: '.875rem', flex: 1, margin: 0 }}>
                    {task.description.length > 100 ? task.description.slice(0, 100) + '…' : task.description}
                  </p>

                  {/* Task-type-specific quick info */}
                  {task.task_type === 'video' && config.video_url && (
                    <a href={config.video_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: '.8rem' }}>
                      ▶ Watch video
                    </a>
                  )}
                  {task.task_type === 'social_follow' && (config.profile_url || config.handle) && (
                    <a href={config.profile_url || '#'} target="_blank" rel="noopener noreferrer" style={{ fontSize: '.8rem' }}>
                      ♡ Follow {config.handle || 'on ' + config.platform}
                    </a>
                  )}
                  {task.task_type === 'survey' && config.survey_url && (
                    <a href={config.survey_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: '.8rem' }}>
                      📋 {config.survey_title || 'Take survey'}
                    </a>
                  )}
                  {task.task_type === 'referral' && (
                    <p style={{ fontSize: '.8rem', color: 'var(--tv-muted)', margin: 0 }}>
                      👥 Invite{config.min_referrals ? ` ${config.min_referrals}+` : ''} new member(s)
                    </p>
                  )}
                  {task.task_type === 'physical' && config.location && (
                    <p style={{ fontSize: '.8rem', color: 'var(--tv-muted)', margin: 0 }}>📍 {config.location}</p>
                  )}

                  <div style={{ display: 'flex', gap: '.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
                    <span className={`chip ${STATUS_COLORS[status] || 'chip-default'}`}>{status}</span>
                    <span className="chip chip-teal">+{task.impact_point_reward} pts</span>
                    {assignment?.assessment_result?.passed !== undefined && <p>Last assessment: {assignment.assessment_result.passed ? 'passed' : 'not passed'}{assignment.assessment_result.score !== undefined ? ` (${assignment.assessment_result.score}%)` : ''}. Attempt {assignment.assessment_result.attempt}.{assignment.assessment_result.attempts_remaining !== undefined ? ` ${assignment.assessment_result.attempts_remaining} attempts remaining.` : ''}</p>}
                    {task.task_type && task.task_type !== 'general' && (
                      <span className="chip chip-default">{taskTypeLabel[task.task_type] || task.task_type}</span>
                    )}
                    {task.verification_required && <span className="chip chip-default">Needs review</span>}
                  </div>
                  {task.due_at && (
                    <time style={{ fontSize: '.8rem', color: 'var(--tv-muted)' }}>
                      Due {new Date(task.due_at).toLocaleDateString()}
                    </time>
                  )}
                  {canSubmit && (
                    <button
                      className="secondary sm"
                      onClick={() => {
                        setSelected(task);

                        setError('');
                        setUrlError('');
                      }}
                      style={{ alignSelf: 'flex-start', marginTop: '.25rem' }}
                    >
                      Submit evidence
                    </button>
                  )}
                </article>
              );
            })}
          </div>
        </>
      )}

      {/* Evidence submission modal */}
      {selected && (() => {
        const required = selected.required_evidence_types || ['text'];
        const config = selected.task_config || {};
        const needsText = required.includes('text');
        const needsUrl = required.includes('url');
        const needsAttachment = required.includes('attachment');
        const canSubmit = !busy && draft.ready &&
          (!needsText || evidence.trim()) &&
          (!needsUrl || evidenceUrl.trim()) &&
          (!needsAttachment || evidenceAttachments.some(a => a.trim()));
        return (
          <TaskDialog title="Submit task evidence" onClose={() => { if (!busy) { setSelected(null); setError(''); } }}>
            <div
              className="panel"
              style={{ width: 'min(100%, 40rem)', maxHeight: '90vh', overflow: 'auto' }}
              onClick={e => e.stopPropagation()}
            >
              <h2 style={{ fontSize: '1.25rem', marginBottom: '.25rem' }}>Submit task evidence</h2>
              <p style={{ color: 'var(--tv-muted)', fontSize: '.875rem', marginBottom: '1rem' }}>{selected.title}</p>

              {/* Task-type-specific instructions */}
              {selected.task_type === 'video' && config.video_url && (
                <div style={{ background: 'var(--tv-surface-sunken)', borderRadius: 'var(--tv-radius-md)', padding: '.75rem 1rem', marginBottom: '1rem', fontSize: '.875rem' }}>
                  <strong>Watch this video:</strong>{' '}
                  <a href={config.video_url} target="_blank" rel="noopener noreferrer">{config.video_url}</a>
                  {config.platform && <span style={{ color: 'var(--tv-muted)', marginLeft: '.5rem' }}>({config.platform})</span>}
                </div>
              )}
              {selected.task_type === 'social_follow' && (
                <div style={{ background: 'var(--tv-surface-sunken)', borderRadius: 'var(--tv-radius-md)', padding: '.75rem 1rem', marginBottom: '1rem', fontSize: '.875rem' }}>
                  <strong>Follow/subscribe:</strong>{' '}
                  {config.profile_url ? (
                    <a href={config.profile_url} target="_blank" rel="noopener noreferrer">
                      {config.handle || config.profile_url}
                    </a>
                  ) : config.handle}
                  {config.platform && <span style={{ color: 'var(--tv-muted)', marginLeft: '.5rem' }}>on {config.platform}</span>}
                </div>
              )}
              {selected.task_type === 'survey' && config.survey_url && (
                <div style={{ background: 'var(--tv-surface-sunken)', borderRadius: 'var(--tv-radius-md)', padding: '.75rem 1rem', marginBottom: '1rem', fontSize: '.875rem' }}>
                  <strong>Complete this survey:</strong>{' '}
                  <a href={config.survey_url} target="_blank" rel="noopener noreferrer">
                    {config.survey_title || config.survey_url}
                  </a>
                </div>
              )}
              {selected.task_type === 'referral' && (
                <div style={{ background: 'var(--tv-surface-sunken)', borderRadius: 'var(--tv-radius-md)', padding: '.75rem 1rem', marginBottom: '1rem', fontSize: '.875rem' }}>
                  <strong>Referral task:</strong> Invite{config.min_referrals ? ` at least ${config.min_referrals}` : ''} new member(s)
                  {config.referral_target ? ` to ${config.referral_target}` : ''}.
                  <p style={{ margin: '.5rem 0 0', color: 'var(--tv-muted)', fontSize: '.8rem' }}>
                    Anti-abuse: referred users must be new, verified accounts. Self-referrals are not counted.
                  </p>
                </div>
              )}
              {selected.task_type === 'physical' && (
                <div style={{ background: 'var(--tv-surface-sunken)', borderRadius: 'var(--tv-radius-md)', padding: '.75rem 1rem', marginBottom: '1rem', fontSize: '.875rem' }}>
                  {config.location && <p style={{ margin: '0 0 .25rem' }}><strong>Location:</strong> {config.location}</p>}
                  {config.instructions && <p style={{ margin: 0 }}><strong>Instructions:</strong> {config.instructions}</p>}
                </div>
              )}

              {error && <p role="alert" className="error" style={{ marginBottom: '1rem' }}>{error}</p>}

              <p role="status">{draft.ready ? 'Draft autosaves privately on this browser. Closing keeps it for recovery.' : 'Recovering draft…'}</p>{draft.error && <p role="alert">{draft.error}</p>}
              {(config.assessment || config.checkpoints) && <LearningAnswers config={config} answers={draft.value.answers} onChange={answers => draft.set(value => ({ ...value, answers, requestKey: '' }))} />}
              {/* Text evidence */}
              <label>
                <span className="label-text">
                  Evidence description{needsText ? ' *' : ' (optional)'}
                </span>
                <textarea
                  value={evidence}
                  onChange={e => setEvidence(e.target.value)}
                  maxLength={10000}
                  rows={5}
                  placeholder="Describe what you did, include details or references…"
                  aria-required={needsText}
                />
              </label>
              <p style={{ fontSize: '.8rem', color: 'var(--tv-muted)', marginTop: '.25rem', marginBottom: '1rem' }}>
                {evidence.length}/10,000 characters
              </p>

              {/* URL evidence */}
              <label>
                <span className="label-text">
                  Evidence URL{needsUrl ? ' *' : ' (optional)'}
                </span>
                <input
                  type="url"
                  value={evidenceUrl}
                  onChange={e => { setEvidenceUrl(e.target.value); setUrlError(''); }}
                  onBlur={() => {
                    if (evidenceUrl && !validateUrl(evidenceUrl)) setUrlError('Please enter a valid URL.');
                  }}
                  placeholder="https://example.com/proof"
                  aria-required={needsUrl}
                />
                {urlError && <span role="alert" style={{ color: 'var(--tv-error)', fontSize: '.8rem' }}>{urlError}</span>}
              </label>

              {/* Attachment URLs */}
              <div style={{ marginTop: '1rem' }}>
                <span className="label-text">
                  Attachment URLs{needsAttachment ? ' *' : ' (optional)'}
                </span>
                {evidenceAttachments.map((att, idx) => (
                  <div key={idx} style={{ display: 'flex', gap: '.5rem', marginTop: '.5rem' }}>
                    <input
                      type="url"
                      value={att}
                      onChange={e => {
                        const next = [...evidenceAttachments];
                        next[idx] = e.target.value;
                        setEvidenceAttachments(next);
                      }}
                      placeholder="https://example.com/attachment"
                      style={{ flex: 1 }}
                      aria-label={`Attachment URL ${idx + 1}`}
                    />
                    {evidenceAttachments.length > 1 && (
                      <button
                        type="button"
                        className="secondary sm"
                        onClick={() => setEvidenceAttachments(evidenceAttachments.filter((_, i) => i !== idx))}
                        aria-label="Remove attachment"
                      >✕</button>
                    )}
                  </div>
                ))}
                {evidenceAttachments.length < 10 && (
                  <button
                    type="button"
                    className="link"
                    style={{ marginTop: '.5rem', fontSize: '.875rem' }}
                    onClick={() => setEvidenceAttachments([...evidenceAttachments, ''])}
                  >
                    + Add another attachment
                  </button>
                )}
              </div>

              <div className="form-actions" style={{ marginTop: '1.5rem' }}>
                <button
                  className="accent"
                  disabled={!canSubmit}
                  onClick={submit}
                >
                  {busy ? 'Submitting…' : 'Submit task'}
                </button>
                <button className="secondary" onClick={() => { setSelected(null); setError(''); }}>Close and keep draft</button>
                <button className="secondary" disabled={busy} onClick={() => setDiscardDraft(true)}>Discard draft</button>
              </div>
            </div>
          </TaskDialog>
        );
      })()}
      {discardDraft && <GovernanceConfirm title="Discard evidence draft?" consequence="Your unsent answers and evidence will be removed from this browser." requireReason={false} onClose={() => setDiscardDraft(false)} onConfirm={async () => { await draft.clear(); setDiscardDraft(false); setSelected(null); }} />}
    </div>
  );
}
