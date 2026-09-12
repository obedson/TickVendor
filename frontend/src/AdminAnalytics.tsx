import { useEffect, useState } from 'react';
import './management.css';
import { apiJson, ApiError, getLiveToken } from './api';

type Summary = {
  community_id: string;
  members: number;
  active_members: number;
  events: number;
  tickets: number;
  attendance: number;
  tasks: number;
  contributions: number;
  impact_points: number;
  revenue: string;
  badge_distribution: { name: string; awards: number }[];
  rank_distribution: { name: string; members: number }[];
  participation_trends: { period: string; attendances: number }[];
  retention: {
    eligible_members: number;
    retained_members: number;
    rate: number;
  };
};

type MetricGroup = { label: string; metrics: { label: string; value: number; icon: string }[] };

export function AdminAnalytics({ token, communityId }: { token: string; communityId?: string }) {
  const [community, setCommunity] = useState(communityId ?? '');
  const [data, setData] = useState<Summary | null>(null);
  const [error, setError] = useState('');
  const liveToken = () => getLiveToken() ?? token;

  useEffect(() => {
    (async () => {
      try {
        const id = community || (await apiJson<any[]>('communities/me', {}, liveToken()))[0]?.id;
        if (!id) throw Error('No community is available for analytics.');
        setCommunity(id);
        setData(await apiJson<Summary>(`communities/${id}/analytics`, {}, liveToken()));
      } catch (cause) { setError(cause instanceof ApiError && cause.status === 403 ? 'Administrator access required.' : cause instanceof Error ? cause.message : 'Unable to load community analytics.'); }
    })();
  }, [token, communityId]);

  if (error) {
    return (
      <div className="management-screen">
        <div className="page-header"><div className="page-header-text"><p className="eyebrow">Administration</p><h1>Community analytics</h1></div></div>
        <p role="alert" className="error">{error}</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="management-screen">
        <div className="page-header"><div className="page-header-text"><p className="eyebrow">Administration</p><h1>Community analytics</h1></div></div>
        <p role="status" className="text-muted">Loading analytics…</p>
      </div>
    );
  }

  const groups: MetricGroup[] = [
  {
    label: 'Membership',
    metrics: [
      { label: 'Total members', value: data.members, icon: '👥' },
      { label: 'Active members', value: data.active_members, icon: '✅' },
    ],
  },
  {
    label: 'Events & tickets',
    metrics: [
      { label: 'Events', value: data.events, icon: '📅' },
      { label: 'Tickets issued', value: data.tickets, icon: '🎟️' },
      { label: 'Attendance records', value: data.attendance, icon: '👤' },
    ],
  },
  {
    label: 'Tasks & contributions',
    metrics: [
      { label: 'Total tasks', value: data.tasks, icon: '📋' },
      { label: 'Contributions', value: data.contributions, icon: '🤝' },
    ],
  },
  {
    label: 'Recognition',
    metrics: [
      { label: 'Impact Points awarded', value: data.impact_points, icon: '⚡' },
    ],
  },
];

  return (
    <div className="management-screen">
      <div className="page-header">
        <div className="page-header-text">
          <p className="eyebrow">Administration</p>
          <h1>Community analytics</h1>
          <p>Overview of community engagement, participation, and recognition.</p>
        </div>
      </div>

      <div style={{ display: 'grid', gap: '1.5rem' }}>
        {groups.map(group => (
          <div key={group.label}>
            <h2 style={{ fontSize: '1rem', color: 'var(--tv-muted)', textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: '.75rem' }}>{group.label}</h2>
            <div className="grid">
              {group.metrics.map(({ label, value, icon }) => (
                <article className="card" key={label}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '.5rem' }}>
                    <h3 style={{ margin: 0, fontSize: '.8rem', color: 'var(--tv-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.06em' }}>{label}</h3>
                    <span style={{ fontSize: '1.1rem' }} aria-hidden="true">{icon}</span>
                  </div>
                  <p className="metric" style={{ fontSize: '1.75rem' }}>{value.toLocaleString()}</p>
                </article>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
