import { useEffect, useState } from 'react';
import { apiJson, ApiError, getLiveToken } from './api';

type Community = { id: string; community: { name: string } };
type SavedItem = { id: string; slug: string; name: string; is_active?: boolean };

type Props = { token: string; communityId?: string };

const api = (community: string, resource: string) =>
  `admin/communities/${community}/${resource}`;

export function AdminRecognition({ token, communityId }: Props) {
  const [community, setCommunity] = useState(communityId ?? '');
  const [rules, setRules] = useState<SavedItem[]>([]);
  const [badges, setBadges] = useState<SavedItem[]>([]);
  const [milestones, setMilestones] = useState<SavedItem[]>([]);
  const [ranks, setRanks] = useState<SavedItem[]>([]);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const headers = { Authorization: `Bearer ${token}` };

  const [rule, setRule] = useState({ name: '', slug: '', description: '', condition: '', reward: '' });
  const [badge, setBadge] = useState({ name: '', slug: '', category: '', requirements: '', rewardPoints: '0' });
  const [milestone, setMilestone] = useState({ name: '', slug: '', requirements: '', rewardPoints: '0' });
  const [rank, setRank] = useState({ name: '', slug: '', minimumPoints: '', sortOrder: '', requirements: '' });

  const liveToken = () => getLiveToken() ?? token;

  const loadCommunity = async () => {
    if (community) return community;
    const items = await apiJson<Community[]>('communities/me', {}, liveToken());
    const id = items[0]?.id;
    if (!id) throw Error('No community is available for administration.');
    setCommunity(id);
    return id;
  };

  useEffect(() => {
    if (!community) {
      loadCommunity().catch(cause => setError(cause instanceof ApiError ? cause.message : 'Unable to load communities.'));
    }
  }, [token]);

  useEffect(() => {
    if (!community) return;
    setLoading(true);
    Promise.all((['achievement-rules', 'badges', 'milestones', 'ranks'] as const).map(async resource => {
      const values = await apiJson<SavedItem[]>(api(community, resource), {}, liveToken());
      return [resource, values] as const;
    })).then(items => items.forEach(([resource, values]) => {
      if (resource === 'achievement-rules') setRules(values);
      if (resource === 'badges') setBadges(values);
      if (resource === 'milestones') setMilestones(values);
      if (resource === 'ranks') setRanks(values);
    })).catch(cause => setError(cause instanceof ApiError ? cause.message : 'Unable to load recognition configuration.')).finally(() => setLoading(false));
  }, [community, token]);

  const create = async (resource: string, body: object, label: string) => {
    setError('');
    setMessage('');
    if (busy) return;
    setBusy(true);
    try {
      const id = await loadCommunity();
      await apiJson<SavedItem>(api(id, resource), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }, liveToken());
      setMessage(`${label} saved.`);
      const values = await apiJson<SavedItem[]>(api(id, resource), {}, liveToken());
      if (resource === 'achievement-rules') setRules(values);
      if (resource === 'badges') setBadges(values);
      if (resource === 'milestones') setMilestones(values);
      if (resource === 'ranks') setRanks(values);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : `Unable to create ${label}.`);
    } finally { setBusy(false); }
  };

  const toggle = async (resource: string, item: SavedItem, active: boolean) => {
    if (!community || !item.id) return;
    setError('');
    try {
      const data = await apiJson<SavedItem>(`${api(community, resource)}/${item.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: active }),
      }, liveToken());
      const update = (items: SavedItem[]) => items.map(existing => existing.id === item.id ? { ...existing, is_active: data.is_active } : existing);
      if (resource === 'achievement-rules') setRules(update);
      if (resource === 'ranks') setRanks(update);
      setMessage('Recognition configuration updated.');
    } catch (cause) { setError(cause instanceof ApiError ? cause.message : 'Unable to update recognition configuration.'); }
  };

  const parse = (value: string, label: string) => {
    try { return JSON.parse(value); } catch { throw Error(`${label} must be valid JSON.`); }
  };

  const submitRule = (event: React.FormEvent) => {
    event.preventDefault();
    try { void create('achievement-rules', { name: rule.name, slug: rule.slug, description: rule.description || null, condition_tree: parse(rule.condition, 'Condition'), reward_definition: parse(rule.reward, 'Reward') }, 'Achievement rule'); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Invalid rule.'); }
  };
  const submitBadge = (event: React.FormEvent) => {
    event.preventDefault();
    try { void create('badges', { name: badge.name, slug: badge.slug, category: badge.category, requirements: parse(badge.requirements, 'Requirements'), reward_points: Number(badge.rewardPoints) }, 'Badge'); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Invalid badge.'); }
  };
  const submitMilestone = (event: React.FormEvent) => {
    event.preventDefault();
    try { void create('milestones', { name: milestone.name, slug: milestone.slug, reward_points: Number(milestone.rewardPoints), requirements: parse(milestone.requirements, 'Requirements') }, 'Milestone'); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Invalid milestone.'); }
  };
  const submitRank = (event: React.FormEvent) => {
    event.preventDefault();
    try { void create('ranks', { name: rank.name, slug: rank.slug, minimum_points: Number(rank.minimumPoints), sort_order: Number(rank.sortOrder), requirements: parse(rank.requirements || '[]', 'Requirements') }, 'Rank'); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Invalid rank.'); }
  };

  const input = (label: string, value: string, onChange: (value: string) => void, required = true) => <label>{label}<input required={required} value={value} onChange={event => onChange(event.target.value)} /></label>;
  const json = (label: string, value: string, onChange: (value: string) => void, placeholder: string) => <label>{label}<textarea required value={value} onChange={event => onChange(event.target.value)} placeholder={placeholder} rows={3} /></label>;
  const list = (title: string, items: SavedItem[], resource: string, canToggle: boolean) => <><h3>{title}</h3>{items.length ? items.map(item => <p key={item.id}>{item.name} ({item.slug}) {canToggle && <button type="button" className="secondary" onClick={() => void toggle(resource, item, item.is_active === false)}>{item.is_active === false ? 'Enable' : 'Disable'}</button>}</p>) : <p className="empty">No {title.toLowerCase()} configured in this session.</p>}</>;

  return <section className="panel"><h2>Recognition configuration</h2><p>Configure achievement rules, badges, milestones, and ranks for community <code>{community || 'loading'}</code>.</p>{loading && <p role="status">Loading recognition configuration…</p>}{error && <p role="alert" className="error">{error}</p>}{message && <p role="status">{message}</p>}
    <form onSubmit={submitRule}><h3>Achievement rule</h3>{input('Name', rule.name, value => setRule({ ...rule, name: value }))}{input('Slug', rule.slug, value => setRule({ ...rule, slug: value }))}{json('Condition tree', rule.condition, value => setRule({ ...rule, condition: value }), '{"metric":"impact_points","operator":">=","threshold":100}')}{json('Reward definition', rule.reward, value => setRule({ ...rule, reward: value }), '{"impact_points":10}') }<button disabled={busy}>Create achievement rule</button></form>
    <form onSubmit={submitBadge}><h3>Badge</h3>{input('Name', badge.name, value => setBadge({ ...badge, name: value }))}{input('Slug', badge.slug, value => setBadge({ ...badge, slug: value }))}{input('Category', badge.category, value => setBadge({ ...badge, category: value }))}{json('Requirements', badge.requirements, value => setBadge({ ...badge, requirements: value }), '{"metric":"attendance_count","operator":">=","threshold":1}')}{input('Reward points', badge.rewardPoints, value => setBadge({ ...badge, rewardPoints: value }))}<button>Create badge</button></form>
    <form onSubmit={submitMilestone}><h3>Milestone</h3>{input('Name', milestone.name, value => setMilestone({ ...milestone, name: value }))}{input('Slug', milestone.slug, value => setMilestone({ ...milestone, slug: value }))}{json('Requirements', milestone.requirements, value => setMilestone({ ...milestone, requirements: value }), '[{"metric":"contribution_count","operator":">=","threshold":5}]')}{input('Reward points', milestone.rewardPoints, value => setMilestone({ ...milestone, rewardPoints: value }))}<button>Create milestone</button></form>
    <form onSubmit={submitRank}><h3>Rank</h3>{input('Name', rank.name, value => setRank({ ...rank, name: value }))}{input('Slug', rank.slug, value => setRank({ ...rank, slug: value }))}{input('Minimum points', rank.minimumPoints, value => setRank({ ...rank, minimumPoints: value }))}{input('Sort order', rank.sortOrder, value => setRank({ ...rank, sortOrder: value }))}{json('Requirements', rank.requirements, value => setRank({ ...rank, requirements: value }), '[{"requirement_type":"attendance_count","threshold":3}]')}<button>Create rank</button></form>
    {list('Achievement rules', rules, 'achievement-rules', true)}{list('Badges', badges, 'badges', false)}{list('Milestones', milestones, 'milestones', false)}{list('Ranks', ranks, 'ranks', true)}
  </section>;
}
