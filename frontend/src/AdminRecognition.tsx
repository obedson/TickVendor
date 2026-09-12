import { useEffect, useRef, useState } from 'react';
import { apiJson, getLiveToken } from './api';
import './management.css';
import { serializeRequirements, validateRequirements, type Condition } from './recognitionForm';

const sections = ['achievement-rules', 'badges', 'milestones', 'ranks'] as const;
type Section = typeof sections[number];
const titles = { 'achievement-rules': 'Achievement Rules', badges: 'Badges', milestones: 'Milestones', ranks: 'Ranks' };
type Definition = { id: string; name: string; slug: string; is_active?: boolean; minimum_points?: number };
const metrics: Record<string, string> = { attendance_count: 'Events attended', impact_points: 'Impact Points', task_count: 'Tasks completed', contribution_count: 'Contributions verified', service_activities: 'Service activities', leadership_activities: 'Leadership activities', peer_confirmations: 'Peer confirmations received', consecutive_activities: 'Consecutive activity days' };
const initial = { metric: 'attendance_count', operator: '>=', threshold: 1 };
const empty = { name: '', slug: '', description: '', category: 'participation', reward: 0, minimum: 0, order: 0, badge: '', icon: '' };

export function AdminRecognition({ token, communityId }: { token: string; communityId?: string }) {
  const [section, setSection] = useState<Section>('achievement-rules');
  const [items, setItems] = useState<Definition[]>([]);
  const [badges, setBadges] = useState<Definition[]>([]);
  const [editor, setEditor] = useState(false);
  const [editing, setEditing] = useState<Definition | null>(null);
  const [form, setForm] = useState(empty);
  const [conditions, setConditions] = useState<Condition[]>([{ ...initial }]);
  const [advanced, setAdvanced] = useState(false);
  const [json, setJson] = useState('');
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const nameRef = useRef<HTMLInputElement>(null);
  const createRef = useRef<HTMLButtonElement>(null);
  const endpoint = 'admin/communities/' + communityId + '/' + section;
  const liveToken = () => getLiveToken() ?? token;
  useEffect(() => {
    let current = true;
    setEditor(false); setEditing(null); setItems([]); setError(''); setMessage('');
    if (!communityId) return;
    setLoading(true);
    apiJson<Definition[]>(endpoint, {}, getLiveToken() ?? token)
      .then(data => { if (current) setItems(data); })
      .catch(cause => { if (current) setError(cause instanceof Error ? cause.message : 'Unable to load recognition.'); })
      .finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, [communityId, section, token, endpoint]);
  useEffect(() => { if (editor) nameRef.current?.focus(); }, [editor]);
  useEffect(() => {
    let current = true;
    setBadges([]);
    if (communityId && section === 'achievement-rules') {
      apiJson<Definition[]>(`admin/communities/${communityId}/badges`, {}, getLiveToken() ?? token)
        .then(data => { if (current) setBadges(data.filter(item => item.is_active !== false)); })
        .catch(() => { if (current) setError('Badge rewards could not be loaded. Retry this section to select a badge.'); });
    }
    return () => { current = false; };
  }, [communityId, section, token]);
  const close = () => { setEditor(false); setEditing(null); window.requestAnimationFrame(() => createRef.current?.focus()); };
  const open = (item?: Definition) => {
    setEditing(item ?? null);
    setForm(item ? { ...empty, name: item.name, slug: item.slug, minimum: item.minimum_points ?? 0 } : empty);
    setConditions([{ ...initial }]); setAdvanced(false); setJson(''); setError(''); setMessage(''); setEditor(true);
  };
  const requirements = () => serializeRequirements(section, conditions);
  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!communityId || busy) return;
    setBusy(true); setError(''); setMessage('');
    try {
      let body: Record<string, unknown>;
      if (editing) body = { name: form.name, minimum_points: form.minimum };
      else {
        const value = advanced ? JSON.parse(json) : requirements();
        validateRequirements(section, value);
        body = { name: form.name, slug: form.slug, description: form.description || null };
        if (section === 'achievement-rules') Object.assign(body, { condition_tree: value, reward_definition: { impact_points: form.reward, ...(form.badge ? { badge: form.badge } : {}) } });
        else if (form.icon) body.icon_url = form.icon;
        if (section === 'badges') Object.assign(body, { category: form.category, requirements: value, reward_points: form.reward });
        if (section === 'milestones') Object.assign(body, { requirements: value, reward_points: form.reward });
        if (section === 'ranks') Object.assign(body, { requirements: value, minimum_points: form.minimum, sort_order: form.order });
      }
      await apiJson(endpoint + (editing ? '/' + editing.id : ''), { method: editing ? 'PATCH' : 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }, liveToken());
      setItems(await apiJson<Definition[]>(endpoint, {}, liveToken()));
      setMessage('Definition saved.'); close();
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to save recognition.'); }
    finally { setBusy(false); }
  };
  const toggle = async (item: Definition) => {
    if (busy) return;
    setBusy(true); setError('');
    try {
      const active = item.is_active === false;
      await apiJson(endpoint + '/' + item.id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ is_active: active }) }, liveToken());
      setItems(current => current.map(value => value.id === item.id ? { ...value, is_active: active } : value));
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to update definition.'); }
    finally { setBusy(false); }
  };
  const changeCondition = (index: number, values: Partial<Condition>) => setConditions(current => current.map((value, i) => i === index ? { ...value, ...values } : value));
  if (!communityId) return <section className="panel management-screen"><h1>Recognition</h1><p>Select a managed community to configure recognition.</p></section>;
  return <section className="panel management-screen">
    <div className="page-header"><div className="page-header-text"><p className="eyebrow">Community impact</p><h1>Recognition</h1><p>Celebrate participation with achievements, badges, milestones, and ranks.</p></div></div>
    <nav className="section-tabs" aria-label="Recognition sections">{sections.map(value => <button type="button" className="secondary" key={value} aria-pressed={section === value} disabled={busy} onClick={() => setSection(value)}>{titles[value]}</button>)}</nav>
    <div className="page-header"><h2>{titles[section]}</h2><button ref={createRef} className="accent" disabled={busy || editor} onClick={() => open()}>Create definition</button></div>
    {error && <p role="alert" className="error">{error}</p>}{message && <p role="status" className="success-msg">{message}</p>}
    {editor && <form className="editor-panel" onSubmit={save} onKeyDown={event => { if (event.key === 'Escape' && !busy) close(); }} aria-label={editing ? 'Edit recognition definition' : 'Create recognition definition'}>
      <h3>{editing ? 'Edit definition' : 'New definition'}</h3>
      <label>Name<input ref={nameRef} required minLength={2} maxLength={120} value={form.name} onChange={event => setForm({ ...form, name: event.target.value, slug: editing ? form.slug : event.target.value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') })} /></label>
      {!editing && <><label>Short identifier<input required minLength={2} maxLength={100} pattern="[a-z0-9]+(-[a-z0-9]+)*" value={form.slug} onChange={event => setForm({ ...form, slug: event.target.value })} /><small>Lowercase words separated by hyphens.</small></label>
        <label>Description<textarea value={form.description} maxLength={5000} onChange={event => setForm({ ...form, description: event.target.value })} /></label>
        {section !== 'achievement-rules' && <label>Icon URL (optional)<input type="url" maxLength={2048} value={form.icon} onChange={event => setForm({ ...form, icon: event.target.value })} /></label>}
        {section === 'achievement-rules' && <label>Badge reward (optional)<select value={form.badge} onChange={event => setForm({ ...form, badge: event.target.value })}><option value="">No badge reward</option>{badges.map(badge => <option key={badge.id} value={badge.slug}>{badge.name}</option>)}</select><small>Select an active badge in this community.</small></label>}
        {section === 'badges' && <label>Category<input required minLength={2} maxLength={64} value={form.category} onChange={event => setForm({ ...form, category: event.target.value })} /></label>}
        {!advanced && <fieldset><legend>Qualifying requirements</legend><p>Every requirement must be met.</p>{conditions.map((condition, index) => <div className="form-row" key={index}>
          <label>Metric<select value={condition.metric} onChange={event => changeCondition(index, { metric: event.target.value })}>{Object.entries(metrics).filter(([key]) => section !== 'ranks' || !['impact_points', 'consecutive_activities'].includes(key)).map(([key, label]) => <option value={key} key={key}>{label}</option>)}</select></label>
          <label>Condition<select disabled={section === 'ranks'} value={condition.operator} onChange={event => changeCondition(index, { operator: event.target.value })}><option value=">=">At least</option>{section !== 'ranks' && <><option value="<=">At most</option><option value="=">Exactly</option></>}</select></label>
          <label>Value<input required type="number" min={section === 'ranks' ? 1 : 0} step="1" value={condition.threshold} onChange={event => changeCondition(index, { threshold: Number(event.target.value) })} /></label>
          {conditions.length > 1 && <button type="button" className="secondary" onClick={() => setConditions(current => current.filter((_, i) => i !== index))}>Remove requirement {index + 1}</button>}
        </div>)}<button type="button" className="secondary" disabled={conditions.length >= 20} onClick={() => setConditions(current => [...current, { ...initial }])}>Add requirement</button></fieldset>}
        <details onToggle={event => { setAdvanced(event.currentTarget.open); if (event.currentTarget.open && !json) setJson(JSON.stringify(requirements(), null, 2)); }}><summary>Advanced configuration</summary><p>Use the backend condition structure for compound conditions or rank badge/milestone references. This JSON replaces the requirements above while expanded.</p><label>Requirements JSON<textarea rows={7} value={json} onChange={event => setJson(event.target.value)} /></label></details>
      </>}
      {section === 'ranks' ? <div className="form-row"><label>Minimum Impact Points<input required type="number" min="0" value={form.minimum} onChange={event => setForm({ ...form, minimum: Number(event.target.value) })} /></label>{!editing && <label>Display order<input required type="number" min="0" value={form.order} onChange={event => setForm({ ...form, order: Number(event.target.value) })} /></label>}</div>
        : <label>Reward Impact Points<input required type="number" min="0" max="100000" value={form.reward} onChange={event => setForm({ ...form, reward: Number(event.target.value) })} /></label>}
      <div className="form-actions"><button className="accent" disabled={busy}>{busy ? 'Saving…' : 'Save definition'}</button><button type="button" className="secondary" disabled={busy} onClick={close}>Cancel</button></div>
    </form>}
    {loading ? <p role="status">Loading definitions…</p> : <div className="definition-list">{items.length ? items.map(item => <article className="definition-card" key={item.id}><div><h3>{item.name}</h3><span className="chip">{item.is_active === false ? 'Inactive' : 'Active'}</span>{item.minimum_points !== undefined && <p>{item.minimum_points.toLocaleString()} minimum Impact Points</p>}<details><summary>Identifier</summary><code>{item.slug}</code></details></div><div className="form-actions">{section === 'ranks' && <button className="secondary" disabled={busy || editor} onClick={() => open(item)}>Edit</button>}{(section === 'ranks' || section === 'achievement-rules') && <button className="secondary" disabled={busy} onClick={() => void toggle(item)}>{item.is_active === false ? 'Enable' : 'Disable'}</button>}</div></article>) : <p className="empty">No {titles[section].toLowerCase()} yet. Create a definition to get started.</p>}</div>}
  </section>;
}
