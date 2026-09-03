import { useEffect, useState } from 'react';

type Summary = { community_id: string; members: number; active_members: number; events: number; tickets: number; attendees: number; verified_attendance: number; tasks: number; completed_tasks: number; contributions: number; impact_points: number; badges: number; milestones: number };
export function AdminAnalytics({ token, communityId }: { token: string; communityId?: string }) {
  const [community, setCommunity] = useState(communityId ?? '');
  const [data, setData] = useState<Summary | null>(null);
  const [error, setError] = useState('');
  const headers = { Authorization: `Bearer ${token}` };
  useEffect(() => {
    (async () => {
      try {
        const id = community || (await (await fetch('/api/v1/communities/me', { headers })).json())[0]?.id;
        if (!id) throw Error('No community is available for analytics.');
        setCommunity(id);
        const response = await fetch(`/api/v1/communities/${id}/analytics`, { headers });
        if (!response.ok) throw Error(response.status === 403 ? 'Administrator access required.' : 'Unable to load community analytics.');
        setData(await response.json());
      } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to load community analytics.'); }
    })();
  }, [token, communityId]);
  if (error) return <section className="panel"><h2>Community analytics</h2><p role="alert" className="error">{error}</p></section>;
  if (!data) return <section className="panel"><h2>Community analytics</h2><p role="status">Loading community analytics…</p></section>;
  const metrics = [['Members', data.members], ['Active members', data.active_members], ['Events', data.events], ['Tickets', data.tickets], ['Attendees', data.attendees], ['Verified attendance', data.verified_attendance], ['Tasks', data.tasks], ['Completed tasks', data.completed_tasks], ['Contributions', data.contributions], ['Impact Points', data.impact_points], ['Badges', data.badges], ['Milestones', data.milestones]];
  return <section aria-labelledby="admin-analytics-title"><p className="eyebrow">Administration</p><h2 id="admin-analytics-title">Community analytics</h2><div className="grid">{metrics.map(([label, value]) => <article className="panel card" key={String(label)}><h3>{label}</h3><p className="metric">{value}</p></article>)}</div></section>;
}
