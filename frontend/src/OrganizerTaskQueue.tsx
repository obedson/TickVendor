import { BulkTaskAssignment } from './BulkTaskAssignment';
import { EvidenceFiles } from './TaskEvidence';
import { useEffect, useState } from 'react';
import './management.css';
import { useDraftState } from './formRecovery';
import { useRevealFocus } from './RevealFocus';
import { LearningBuilder, buildLearning, emptyLearning, learningFromConfig } from './LearningTask';
import { GovernanceConfirm } from './GovernanceConfirm';
import { EmptyState } from './AppShell';
import { apiJson, ApiError, getLiveToken } from './api';

type Submission = {
  assignment_id: string;
  task_title: string;
  assignee_id: string;
  assignee_name?: string;
  submitted_at: string;
  evidence_text?: string;
  evidence_url?: string;
  evidence_attachments: string[];
  attachment_ids?: string[];
  location_evidence?: { verified?: boolean; distance_meters?: number };
  answers?: Record<string, unknown>;
  assessment_result?: Record<string, unknown>;
};

type Task = {
  id: string;
  title: string;
  description: string;
  due_at?: string | null;
  priority: string;
  impact_point_reward: number;
  verification_required: boolean;
  is_active?: boolean;
  task_type: string;
  task_config: Record<string, string | number>;
  required_evidence_types: string[];
};

const TASK_TYPES = [
  { value: 'general', label: 'General' },
  { value: 'video', label: 'Video / YouTube' },
  { value: 'quiz', label: 'Quiz / Assessment' },
  { value: 'social_follow', label: 'Social Follow / Subscribe' },
  { value: 'survey', label: 'Survey' },
  { value: 'referral', label: 'Referral / Invite' },
  { value: 'physical', label: 'Physical / Manual Work' },
];

const EVIDENCE_TYPES = [
  { value: 'text', label: 'Text description' },
  { value: 'url', label: 'URL link' },
  { value: 'attachment', label: 'Uploaded file or attachment URL' },
];

const emptyTaskForm = {
  title: '',
  description: '',
  due_at: '',
  priority: 'normal',
  impact_point_reward: '0',
  learning: emptyLearning,
  verification_required: true,
  task_type: 'general',
  required_evidence_types: ['text'] as string[],
  // Per-type config fields
  video_url: '',
  platform: '',
  handle: '',
  profile_url: '',
  survey_url: '',
  survey_title: '',
  referral_target: '',
  min_referrals: '1',
  location: '',
  instructions: '',
  gps_required: false, latitude: '', longitude: '', radius_meters: '100',
};

function buildTaskConfig(form: typeof emptyTaskForm): Record<string, unknown> {
  switch (form.task_type) {
    case 'video': return { ...(form.video_url && { video_url: form.video_url }), ...(form.platform && { platform: form.platform }) };
    case 'social_follow': return { ...(form.platform && { platform: form.platform }), ...(form.handle && { handle: form.handle }), ...(form.profile_url && { profile_url: form.profile_url }) };
    case 'survey': return { ...(form.survey_url && { survey_url: form.survey_url }), ...(form.survey_title && { survey_title: form.survey_title }) };
    case 'referral': return { ...(form.referral_target && { referral_target: form.referral_target }), ...(form.min_referrals && { min_referrals: Number(form.min_referrals) }) };
    case 'physical': return { ...(form.gps_required && { geofence: { required: true, address: form.location, latitude: Number(form.latitude), longitude: Number(form.longitude), radius_meters: Number(form.radius_meters) } }), ...(form.location && { location: form.location }), ...(form.instructions && { instructions: form.instructions }) };
    default: return {};
  }
}

type OrganizerView = 'queue' | 'tasks' | 'create' | 'edit';

/** What `GET /tasks/{id}?management=true` returns to an organizer: the full stored config. */
type TaskDetail = {
  id: string;
  title: string;
  description: string;
  task_type: string;
  task_config: Record<string, any>;
  due_at?: string | null;
  priority: string;
  verification_required: boolean;
  required_evidence_types: string[];
  impact_point_reward: number;
  is_active: boolean;
};

/**
 * Re-open a stored task in the same form that created it.
 *
 * Quiz and checkpoint answers are read here because this screen is the organizer editor, and the
 * same config is what the participant payload strips. Nothing on this path is participant-facing.
 */
function taskFormFromDetail(detail: TaskDetail): typeof emptyTaskForm {
  const config = detail.task_config ?? {};
  const geofence = config.geofence ?? {};
  return {
    ...emptyTaskForm,
    title: detail.title,
    description: detail.description,
    due_at: detail.due_at ? localInput(detail.due_at) : '',
    priority: detail.priority,
    impact_point_reward: String(detail.impact_point_reward),
    verification_required: detail.verification_required,
    task_type: detail.task_type,
    required_evidence_types: detail.required_evidence_types?.length ? detail.required_evidence_types : ['text'],
    learning: learningFromConfig(config),
    video_url: config.video_url ?? '',
    platform: config.platform ?? '',
    handle: config.handle ?? '',
    profile_url: config.profile_url ?? '',
    survey_url: config.survey_url ?? '',
    survey_title: config.survey_title ?? '',
    referral_target: config.referral_target ?? '',
    min_referrals: String(config.min_referrals ?? 1),
    location: config.location ?? '',
    instructions: config.instructions ?? '',
    gps_required: Boolean(geofence.required),
    latitude: geofence.latitude == null ? '' : String(geofence.latitude),
    longitude: geofence.longitude == null ? '' : String(geofence.longitude),
    radius_meters: String(geofence.radius_meters ?? 100),
  };
}

function localInput(value: string) { const date = new Date(value); return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16); }

export function OrganizerTaskQueue({ token, communityId }: { token: string; communityId?: string }) {
  const [view, setView] = useState<OrganizerView>('queue');
  const [items, setItems] = useState<Submission[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState('');
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [editingTask, setEditingTask] = useState<TaskDetail | null>(null);
  const [taskSeed, setTaskSeed] = useState(emptyTaskForm);
  const [taskActive, setTaskActive] = useState(true);
  const draft = useDraftState(communityId ? `community:${communityId}:task:${editingTask ? editingTask.id : 'create'}` : '', taskSeed);
  const taskForm = draft.value; const setTaskForm = draft.set;
  const [discard, setDiscard] = useState(false);
  const [policy, setPolicy] = useState<{ community_points: number; platform_maximum: number | null; warning: string | null } | null>(null);
  useRevealFocus(['create', 'edit'].includes(view) ? view : '', '[data-task-editor]');
  useRevealFocus(expanded, `[data-task-reveal="${expanded}"]`);
  useRevealFocus(rejectingId, `[data-task-rejection="${rejectingId}"]`);
  useRevealFocus(error, '.management-screen [role="alert"]');
  useEffect(() => { if (communityId) apiJson<any>(`communities/${communityId}/task-point-policy`, {}, token).then(setPolicy).catch(() => setPolicy(null)); }, [communityId, token, view]);
  const [savingTask, setSavingTask] = useState(false);
  const [assigningTask, setAssigningTask] = useState<Task | null>(null);
  const liveToken = () => getLiveToken() ?? token;

  const getCommunityId = async (): Promise<string> => {
    if (communityId) return communityId;
    const memberships = await apiJson<any[]>('communities/me', {}, liveToken());
    const id = memberships[0]?.id;
    if (!id) throw new Error('No active community selected');
    return id;
  };

  const loadQueue = async () => {
    setLoading(true); setError('');
    try {
      const id = await getCommunityId();
      setItems(await apiJson<Submission[]>(`communities/${id}/task-verification-queue`, {}, liveToken()));
    } catch (cause) {
      setError(cause instanceof ApiError && cause.status === 403 ? 'Organizer access required' : cause instanceof Error ? cause.message : 'Unable to load task queue');
    } finally { setLoading(false); }
  };

  const loadTasks = async () => {
    setLoading(true); setError('');
    try {
      const id = await getCommunityId();
      setTasks(await apiJson<Task[]>(`communities/${id}/tasks?management=true`, {}, liveToken()));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to load tasks');
    } finally { setLoading(false); }
  };

  useEffect(() => {
    if (view === 'queue') loadQueue();
    else if (view === 'tasks') loadTasks();
  }, [token, communityId, view]);

  const verify = async (assignmentId: string, approve: boolean, reason?: string) => {
    try {
      await apiJson<unknown>(`task-assignments/${assignmentId}/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approve, ...(reason && { reason }) }),
      }, liveToken());
      setMessage(approve ? 'Task verified. The participant notification reports the actual award.' : 'Task submission rejected.');
      setExpanded(null);
      setRejectingId(null);
      setRejectReason('');
      await loadQueue();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Unable to update submission');
    }
  };

  const beginTaskEdit = async (task: Task) => {
    setError('');
    setMessage('');
    try {
      const detail = await apiJson<TaskDetail>(`tasks/${task.id}?management=true`, {}, liveToken());
      setTaskSeed(taskFormFromDetail(detail));
      setEditingTask(detail);
      setTaskActive(detail.is_active);
      setView('edit');
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Unable to open this task for editing');
    }
  };

  /**
   * Create and edit share one payload.
   *
   * An edit only ever carries configuration: assignments, submissions, graded answers and the
   * Impact already awarded are not part of this body, so the backend cannot restate them.
   */
  const saveTask = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingTask(true); setError('');
    try {
      const id = await getCommunityId();
      const body = {
        title: taskForm.title,
        description: taskForm.description,
        due_at: taskForm.due_at ? new Date(taskForm.due_at).toISOString() : null,
        priority: taskForm.priority,
        impact_point_reward: Number(taskForm.impact_point_reward),
        verification_required: taskForm.verification_required,
        task_type: taskForm.task_type,
        task_config: { ...buildTaskConfig(taskForm), ...buildLearning(taskForm.task_type, taskForm.learning) },
        required_evidence_types: taskForm.required_evidence_types,
      };
      if (editingTask) {
        await apiJson<unknown>(`tasks/${editingTask.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ...body, is_active: taskActive }),
        }, liveToken());
        setMessage('Task updated. Assignments, submissions and awarded Impact are unchanged.');
        setEditingTask(null);
        await draft.clear();
        setView('tasks');
      } else {
        await apiJson<unknown>(`communities/${id}/tasks`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        }, liveToken());
        setMessage('Task created successfully.');
        await draft.clear();
        setView('tasks');
      }
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message
        : editingTask ? 'Unable to update task' : 'Unable to create task');
    } finally { setSavingTask(false); }
  };

  const leaveEditor = () => { setEditingTask(null); setDiscard(true); };

  const toggleEvidenceType = (type: string) => {
    setTaskForm(prev => ({
      ...prev,
      required_evidence_types: prev.required_evidence_types.includes(type)
        ? prev.required_evidence_types.filter(t => t !== type)
        : [...prev.required_evidence_types, type],
    }));
  };

  return (
    <div className="management-screen">
      <div className="page-header">
        <div className="page-header-text">
          <p className="eyebrow">Operations</p>
          <h1>Tasks</h1>
          <p>Create tasks, manage assignments, and verify submissions.</p>
        </div>
        <div className="page-header-actions">
          {items.length > 0 && view === 'queue' && (
            <span className="chip chip-yellow">{items.length} pending</span>
          )}
          <button className={view === 'queue' ? 'accent sm' : 'secondary sm'} onClick={() => setView('queue')}>
            Verification queue
          </button>
          <button className={view === 'tasks' ? 'accent sm' : 'secondary sm'} onClick={() => setView('tasks')}>
            All tasks
          </button>
          <button className={view === 'create' ? 'accent sm' : 'secondary sm'} onClick={() => { setEditingTask(null); setTaskSeed(emptyTaskForm); setTaskActive(true); setView('create'); }}>
            + Create task
          </button>
        </div>
      </div>

      {error && <p role="alert" className="error" style={{ marginBottom: '1rem' }}>{error}</p>}
      {message && <p role="status" className="success-msg" style={{ marginBottom: '1rem' }}>{message}</p>}
      {loading && <p role="status" className="text-muted">Loading…</p>}

      {/* ── Verification queue ── */}
      {view === 'queue' && !loading && (
        <>
          {!items.length && (
            <EmptyState
              title="Queue is clear"
              description="No task submissions are waiting for review. Check back when members submit their work."
            />
          )}
          <div className="stack">
            {items.map(item => (
              <article key={item.assignment_id} className="card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', flexWrap: 'wrap' }}>
                  <div>
                    <h3 style={{ margin: '0 0 .25rem' }}>{item.task_title}</h3>
                    <p style={{ margin: 0, fontSize: '.875rem', color: 'var(--tv-muted)' }}>
                      {item.assignee_name || item.assignee_id.slice(0, 8) + '…'} ·{' '}
                      <time>{new Date(item.submitted_at).toLocaleString()}</time>
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: '.5rem', flexShrink: 0, flexWrap: 'wrap' }}>
                    <button
                      className="secondary sm"
                      onClick={() => setExpanded(expanded === item.assignment_id ? null : item.assignment_id)}
                    >
                      {expanded === item.assignment_id ? 'Hide evidence' : 'View evidence'}
                    </button>
                    <button className="accent sm" onClick={() => verify(item.assignment_id, true)}>Verify</button>
                    <button className="danger sm" onClick={() => setRejectingId(item.assignment_id)}>Reject</button>
                  </div>
                </div>

                {expanded === item.assignment_id && (
                  <div data-task-reveal={item.assignment_id} style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--tv-border)' }}>
                    {item.assessment_result && <p>Assessment: {Object.entries(item.assessment_result).map(([key, value]) => `${key}: ${String(value)}`).join(' · ')}</p>}
                    {item.answers && <ul>{Object.entries(item.answers).map(([key, value]) => <li key={key}>{key}: {Array.isArray(value) ? value.join(', ') : String(value)}</li>)}</ul>}
                    {item.evidence_text ? (
                      <div style={{ background: 'var(--tv-surface-sunken)', borderRadius: 'var(--tv-radius-md)', padding: '1rem', fontSize: '.875rem', lineHeight: '1.6' }}>
                        {item.evidence_text}
                      </div>
                    ) : (
                      <p className="text-muted text-sm">No text evidence provided.</p>
                    )}
                    {item.evidence_url && (
                      <p style={{ marginTop: '.75rem' }}>
                        <a href={item.evidence_url} target="_blank" rel="noopener noreferrer">View evidence link →</a>
                      </p>
                    )}
                    <EvidenceFiles token={liveToken()} ids={item.attachment_ids || []} />
                    {item.location_evidence?.verified && <p>GPS verified: {item.location_evidence.distance_meters} metres from task location.</p>}
                    {item.evidence_attachments?.length > 0 && (
                      <div style={{ marginTop: '.75rem' }}>
                        <strong style={{ fontSize: '.875rem' }}>Attachments:</strong>
                        <ul style={{ margin: '.25rem 0 0', paddingLeft: '1.25rem', fontSize: '.875rem' }}>
                          {item.evidence_attachments.map((att, i) => (
                            <li key={i}><a href={att} target="_blank" rel="noopener noreferrer">{att}</a></li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}

                {/* Reject with reason */}
                {rejectingId === item.assignment_id && (
                  <div data-task-rejection={item.assignment_id} style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--tv-border)' }}>
                    <label>
                      <span className="label-text">Participant-visible revision reason</span>
                      <textarea
                        value={rejectReason}
                        onChange={e => setRejectReason(e.target.value)}
                        rows={3}
                        placeholder="Explain why this submission is being rejected…"
                      />
                    </label>
                    <div className="form-actions" style={{ marginTop: '.75rem' }}>
                      <button className="danger sm" onClick={() => verify(item.assignment_id, false, rejectReason)}>
                        Confirm rejection
                      </button>
                      <button className="secondary sm" onClick={() => { setRejectingId(null); setRejectReason(''); }}>
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </article>
            ))}
          </div>
        </>
      )}

      {/* ── All tasks list ── */}
      {view === 'tasks' && !loading && (
        <>
          {!tasks.length && (
            <EmptyState
              title="No tasks yet"
              description="Create your first task to assign to community members."
              action="Create task"
              onAction={() => setView('create')}
            />
          )}
          <div className="stack">
            {tasks.map(task => (
              <article key={task.id} className="card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', flexWrap: 'wrap' }}>
                  <div>
                    <h3 style={{ margin: '0 0 .25rem' }}>{task.title}</h3>
                    <p style={{ margin: 0, fontSize: '.875rem', color: 'var(--tv-muted)' }}>
                      {task.description.length > 120 ? task.description.slice(0, 120) + '…' : task.description}
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: '.5rem', flexWrap: 'wrap', flexShrink: 0 }}>
                    <button className="secondary sm" onClick={() => beginTaskEdit(task)}>
                      Edit
                    </button>
                    <button className="secondary sm" onClick={() => setAssigningTask(task)}>
                      Assign
                    </button>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '.5rem', flexWrap: 'wrap', marginTop: '.5rem' }}>
                  <span className="chip chip-default">{task.priority}</span>
                  <span className="chip chip-teal">+{task.impact_point_reward} pts</span>
                  {task.task_type !== 'general' && <span className="chip chip-default">{task.task_type}</span>}
                  {task.verification_required && <span className="chip chip-default">Needs review</span>}
                  {task.due_at && (
                    <span className="chip chip-default">Due {new Date(task.due_at).toLocaleDateString()}</span>
                  )}
                </div>
              </article>
            ))}
          </div>

          {/* Assign task modal */}
          {assigningTask && <BulkTaskAssignment token={liveToken()} task={assigningTask} onClose={() => setAssigningTask(null)} onDone={setMessage} />}
        </>
      )}

      {/* ── Create or edit task ── */}
      {(view === 'create' || view === 'edit') && (
        <div className="panel" data-task-editor>
          <h2 style={{ fontSize: '1.1rem', marginBottom: '1.25rem' }}>{editingTask ? `Configure "${editingTask.title}"` : 'Create new task'}</h2>
          {editingTask && (
            <p className="text-sm text-muted">
              Editing configuration only. Assignments, submissions, graded answers and Impact already
              awarded are never rewritten by this form.
            </p>
          )}
          <p role="status">{draft.ready ? 'Unfinished work is autosaved privately on this browser.' : 'Loading draft…'}</p>{draft.error && <p role="alert">{draft.error}</p>}
          <p>{policy ? `Community award: ${policy.community_points} points. Platform maximum: ${policy.platform_maximum ?? 'not configured'}. ${policy.warning || 'Actual reward cannot exceed the effective community rule.'}` : 'Point guidance unavailable. Use zero points or retry before promising a reward.'}</p>
          <form onSubmit={saveTask} style={{ display: 'grid', gap: '1rem' }}>
            <label>
              <span className="label-text">Task title *</span>
              <input required minLength={2} maxLength={200} value={taskForm.title}
                onChange={e => setTaskForm({ ...taskForm, title: e.target.value })}
                placeholder="e.g. Set up chairs for the event" />
            </label>
            <label>
              <span className="label-text">Description *</span>
              <textarea required minLength={2} maxLength={5000} rows={4} value={taskForm.description}
                onChange={e => setTaskForm({ ...taskForm, description: e.target.value })}
                placeholder="Describe what needs to be done…" />
            </label>

            <label>
              <span className="label-text">Task type</span>
              <select value={taskForm.task_type} onChange={e => setTaskForm({ ...taskForm, task_type: e.target.value, learning: { ...taskForm.learning, attempts: e.target.value === 'survey' ? 1 : 3 } })}>
                {TASK_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </label>

            <LearningBuilder kind={taskForm.task_type} data={taskForm.learning} onChange={learning => setTaskForm({ ...taskForm, learning })} />
            {/* Per-type config fields */}
            {taskForm.task_type === 'video' && (
              <div style={{ background: 'var(--tv-surface-sunken)', padding: '1rem', borderRadius: 'var(--tv-radius-md)', display: 'grid', gap: '.75rem' }}>
                <label>
                  <span className="label-text">Video URL</span>
                  <input type="url" value={taskForm.video_url} onChange={e => setTaskForm({ ...taskForm, video_url: e.target.value })} placeholder="https://youtube.com/watch?v=..." />
                </label>
                <label>
                  <span className="label-text">Platform (e.g. YouTube)</span>
                  <input value={taskForm.platform} onChange={e => setTaskForm({ ...taskForm, platform: e.target.value })} placeholder="YouTube" />
                </label>
              </div>
            )}
            {taskForm.task_type === 'social_follow' && (
              <div style={{ background: 'var(--tv-surface-sunken)', padding: '1rem', borderRadius: 'var(--tv-radius-md)', display: 'grid', gap: '.75rem' }}>
                <label>
                  <span className="label-text">Platform (e.g. Twitter, Instagram)</span>
                  <input value={taskForm.platform} onChange={e => setTaskForm({ ...taskForm, platform: e.target.value })} placeholder="Twitter" />
                </label>
                <label>
                  <span className="label-text">Handle / username</span>
                  <input value={taskForm.handle} onChange={e => setTaskForm({ ...taskForm, handle: e.target.value })} placeholder="@handle" />
                </label>
                <label>
                  <span className="label-text">Profile URL</span>
                  <input type="url" value={taskForm.profile_url} onChange={e => setTaskForm({ ...taskForm, profile_url: e.target.value })} placeholder="https://twitter.com/handle" />
                </label>
              </div>
            )}
            {taskForm.task_type === 'survey' && (
              <div style={{ background: 'var(--tv-surface-sunken)', padding: '1rem', borderRadius: 'var(--tv-radius-md)', display: 'grid', gap: '.75rem' }}>
                <label>
                  <span className="label-text">Survey URL *</span>
                  <input type="url" value={taskForm.survey_url} onChange={e => setTaskForm({ ...taskForm, survey_url: e.target.value })} placeholder="https://forms.google.com/..." />
                </label>
                <label>
                  <span className="label-text">Survey title (optional)</span>
                  <input value={taskForm.survey_title} onChange={e => setTaskForm({ ...taskForm, survey_title: e.target.value })} placeholder="Community Feedback Survey" />
                </label>
              </div>
            )}
            {taskForm.task_type === 'referral' && (
              <div style={{ background: 'var(--tv-surface-sunken)', padding: '1rem', borderRadius: 'var(--tv-radius-md)', display: 'grid', gap: '.75rem' }}>
                <label>
                  <span className="label-text">Referral target (optional description)</span>
                  <input value={taskForm.referral_target} onChange={e => setTaskForm({ ...taskForm, referral_target: e.target.value })} placeholder="e.g. TickVendor community" />
                </label>
                <label>
                  <span className="label-text">Minimum referrals required</span>
                  <input type="number" min="1" value={taskForm.min_referrals} onChange={e => setTaskForm({ ...taskForm, min_referrals: e.target.value })} />
                </label>
                <p style={{ margin: 0, fontSize: '.8rem', color: 'var(--tv-muted)' }}>
                  Anti-abuse: referred users must be new, verified accounts. Self-referrals are not counted. Verification is manual/organizer-based.
                </p>
              </div>
            )}
            {taskForm.task_type === 'physical' && (
              <div style={{ background: 'var(--tv-surface-sunken)', padding: '1rem', borderRadius: 'var(--tv-radius-md)', display: 'grid', gap: '.75rem' }}>
                <label>
                  <span className="label-text">Location</span>
                  <input value={taskForm.location} onChange={e => setTaskForm({ ...taskForm, location: e.target.value })} placeholder="e.g. Main hall, Building A" />
                </label>
                <label>
                  <span className="label-text">Instructions</span>
                  <textarea rows={3} value={taskForm.instructions} onChange={e => setTaskForm({ ...taskForm, instructions: e.target.value })} placeholder="Detailed instructions for the physical task…" />
                </label>
              </div>
            )}

            {taskForm.task_type === 'physical' && <fieldset><legend>Task geofence</legend><label><input type="checkbox" checked={taskForm.gps_required} onChange={e => setTaskForm({ ...taskForm, gps_required: e.target.checked })} />Require fresh GPS at submission</label>{taskForm.gps_required && <>{(['latitude', 'longitude', 'radius_meters'] as const).map(key => <label key={key}>{key.replace('_', ' ')}<input type="number" required step={key === 'radius_meters' ? 1 : 'any'} min={key === 'latitude' ? -90 : key === 'longitude' ? -180 : 10} max={key === 'latitude' ? 90 : key === 'longitude' ? 180 : 10000} value={taskForm[key]} onChange={e => setTaskForm({ ...taskForm, [key]: e.target.value })} /></label>)}<p>GPS is required in addition to the selected evidence and organizer review. It is requested only on submission.</p></>}</fieldset>}
            <div className="form-row">
              <label>
                <span className="label-text">Priority</span>
                <select value={taskForm.priority} onChange={e => setTaskForm({ ...taskForm, priority: e.target.value })}>
                  <option value="low">Low</option>
                  <option value="normal">Normal</option>
                  <option value="high">High</option>
                  <option value="urgent">Urgent</option>
                </select>
              </label>
              <label>
                <span className="label-text">Impact Points reward</span>
                <input type="number" min="0" max={policy?.community_points ?? 0} value={taskForm.impact_point_reward}
                  onChange={e => setTaskForm({ ...taskForm, impact_point_reward: e.target.value })} />
              </label>
              <label>
                <span className="label-text">Due date (optional)</span>
                <input type="datetime-local" value={taskForm.due_at}
                  onChange={e => setTaskForm({ ...taskForm, due_at: e.target.value })} />
              </label>
            </div>

            <div>
              <span className="label-text">Required evidence types</span>
              <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', marginTop: '.5rem' }}>
                {EVIDENCE_TYPES.map(et => (
                  <label key={et.value} style={{ display: 'flex', alignItems: 'center', gap: '.4rem', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={taskForm.required_evidence_types.includes(et.value)}
                      onChange={() => toggleEvidenceType(et.value)}
                    />
                    {et.label}
                  </label>
                ))}
              </div>
            </div>

            <label style={{ display: 'flex', alignItems: 'center', gap: '.5rem', cursor: 'pointer' }}>
              <input type="checkbox" checked={taskForm.verification_required}
                onChange={e => setTaskForm({ ...taskForm, verification_required: e.target.checked })} />
              <span>Require organizer verification before awarding points</span>
            </label>

            {editingTask && (
              <>
                <label style={{ display: 'flex', alignItems: 'center', gap: '.5rem', cursor: 'pointer' }}>
                  <input type="checkbox" checked={taskActive} onChange={e => setTaskActive(e.target.checked)} />
                  <span>Active — participants can accept and submit this task</span>
                </label>
                <p className="text-sm text-muted">
                  A task that already has submissions cannot change its type; the save will be refused
                  and the existing submissions left untouched.
                </p>
              </>
            )}

            <div className="form-actions">
              <button type="submit" className="accent" disabled={savingTask || !draft.ready}>
                {savingTask ? 'Saving…' : editingTask ? 'Save changes' : 'Create task'}
              </button>
              <button type="button" className="secondary" onClick={leaveEditor}>
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}
      {discard && <GovernanceConfirm
        title={editingTask ? 'Discard task changes?' : 'Discard task draft?'}
        consequence={editingTask
          ? 'Your unsaved changes to this task are lost. The task and everything already recorded against it stay as they are.'
          : 'This removes your saved unfinished task.'}
        requireReason={false}
        onClose={() => setDiscard(false)}
        onConfirm={async () => { await draft.clear(); setTaskSeed(emptyTaskForm); setEditingTask(null); setView('tasks'); }}
      />}
    </div>
  );
}
