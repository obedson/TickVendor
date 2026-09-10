import { useEffect, useState } from 'react';
import { apiJson, ApiError, getLiveToken } from './api';

type Summary = {
  upcoming_events: number;
  total_events: number;
  ticket_sales: number;
  revenue: string;
  registrations: number;
  attendance: number;
  verified_attendance: number;
  pending_tasks: number;
  contributions: number;
  engagement: number;
};

type MetricCard = { label: string; value: string | number; icon: string; color?: string };

export function OrganizerDashboard({ token }: { token: string }) {
  const [data, setData] = useState<Summary | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    apiJson<Summary>('communities/organizer/dashboard', {}, getLiveToken() ?? token)
      .then(setData)
      .catch((cause: Error) => setError(cause instanceof ApiError && cause.status === 403 ? 'Organizer access required.' : cause.message));
  }, [token]);

  if (error) {
    return (
      <div>
        <div className="page-header">
          <div className="page-header-text">
            <p className="eyebrow">Operations</p>
            <h1>Organizer dashboard</h1>
          </div>
        </div>
        <p role="alert" className="error">{error}</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div>
        <div className="page-header">
          <div className="page-header-text">
            <p className="eyebrow">Operations</p>
            <h1>Organizer dashboard</h1>
          </div>
        </div>
        <p role="status" className="text-muted">Loading dashboard…</p>
      </div>
    );
  }

  const metrics: MetricCard[] = [
    { label: 'Upcoming events', value: data.upcoming_events, icon: '📅' },
    { label: 'Total events', value: data.total_events, icon: '◈' },
    { label: 'Ticket sales', value: data.ticket_sales, icon: '🎟️' },
    { label: 'Revenue', value: data.revenue, icon: '💰' },
    { label: 'Registrations', value: data.registrations, icon: '📋' },
    { label: 'Attendance', value: data.attendance, icon: '✓' },
    { label: 'Verified attendance', value: data.verified_attendance, icon: '✅' },
    { label: 'Pending tasks', value: data.pending_tasks, icon: '⏳', color: data.pending_tasks > 0 ? 'var(--tv-warning)' : undefined },
    { label: 'Contributions', value: data.contributions, icon: '🤝' },
    { label: 'Engagement points', value: data.engagement, icon: '⚡' },
  ];

  return (
    <div>
      <div className="page-header">
        <div className="page-header-text">
          <p className="eyebrow">Operations</p>
          <h1>Organizer dashboard</h1>
          <p>Overview of your community's events, attendance, and engagement.</p>
        </div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))' }}>
        {metrics.map(({ label, value, icon, color }) => (
          <article className="card" key={label}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '.5rem' }}>
              <h3 style={{ margin: 0, fontSize: '.85rem', color: 'var(--tv-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.06em' }}>{label}</h3>
              <span style={{ fontSize: '1.25rem' }} aria-hidden="true">{icon}</span>
            </div>
            <p className="metric" style={{ fontSize: '1.75rem', color: color || 'var(--tv-ink)' }}>{value}</p>
          </article>
        ))}
      </div>
    </div>
  );
}
