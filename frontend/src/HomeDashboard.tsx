import { useEffect, useState } from 'react';
import { EmptyState } from './AppShell';
import { apiJson, ApiError } from './api';
import { SponsoredPlacement } from './SponsoredPlacement';

type HomeData = {
  display_name?: string;
  impact_points?: number;
  rank?: { name: string } | null;
  next_rank?: { name: string; points_remaining: number } | null;
  badges?: { id: string; name: string }[];
  milestones?: { id: string; name: string }[];
  events_attended?: number;
  tasks_completed?: number;
};
type Ticket = { public_id: string; event_title?: string; event_starts_at?: string; status: string };
type Task = { id: string; title: string; status: string; due_at?: string | null };

export function HomeDashboard({
  token,
  onDiscover,
  onTasks,
  onTickets,
}: {
  token: string;
  onDiscover: () => void;
  onTasks?: () => void;
  onTickets?: () => void;
}) {
  const [profile, setProfile] = useState<HomeData | null>(null);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      apiJson<HomeData>('profiles/me', {}, token),
      apiJson<Ticket[]>('tickets/me', {}, token),
      apiJson<Task[]>('task-assignments/me/details', {}, token),
    ])
      .then(([p, t, a]) => { setProfile(p); setTickets(t); setTasks(a); })
      .catch(cause => setError(cause instanceof ApiError ? cause.message : 'Unable to load your dashboard.'))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) {
    return (
      <div className="home-dashboard">
        <div className="home-hero panel">
          <p className="home-welcome">Loading your dashboard…</p>
          <h1 id="home-title">Make your presence count.</h1>
        </div>
        <p role="status" className="text-muted">Loading your progress…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="home-dashboard">
        <div className="home-hero panel">
          <h1 id="home-title">Make your presence count.</h1>
        </div>
        <p role="alert" className="error">{error}</p>
      </div>
    );
  }

  if (!profile) return null;

  const activeTasks = tasks.filter(task => !['verified', 'rejected'].includes(task.status));
  const upcomingTickets = tickets.filter(t => t.status === 'active');
  const nextRankPct = profile.next_rank
    ? Math.max(0, Math.min(100, 100 - Math.round((profile.next_rank.points_remaining / ((profile.impact_points ?? 0) + profile.next_rank.points_remaining)) * 100)))
    : 100;

  return (
    <div className="home-dashboard" aria-labelledby="home-title">
      {/* Hero */}
      <section className="home-hero panel">
        <p className="home-welcome">Welcome back, {profile.display_name || 'participant'} 👋</p>
        <p className="eyebrow">Your participation journey</p>
        <h1 id="home-title">Make your presence count.</h1>
        <p>Track your impact, earn recognition, and grow with your community.</p>
        <div style={{ display: 'flex', gap: '.75rem', flexWrap: 'wrap', marginTop: '1rem' }}>
          <button className="accent" onClick={onDiscover}>Discover events</button>
          {onTasks && <button className="secondary" onClick={onTasks}>View tasks</button>}
        </div>
      </section>

      {/* Metrics */}
      <section aria-labelledby="progress-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Your progress</p>
            <h2 id="progress-title">Impact &amp; recognition</h2>
          </div>
        </div>
        <div className="grid home-metrics">
          <article className="card">
            <h3>Impact Points</h3>
            <p className="metric">{(profile.impact_points ?? 0).toLocaleString()}</p>
            {profile.next_rank && (
              <>
                <div className="progress-bar" aria-label={`${nextRankPct}% to next rank`}>
                  <div className="progress-fill" style={{ width: `${nextRankPct}%` }} />
                </div>
                <small className="text-muted">{profile.next_rank.points_remaining.toLocaleString()} pts to {profile.next_rank.name}</small>
              </>
            )}
          </article>
          <article className="card">
            <h3>Current rank</h3>
            {profile.rank ? (
              <p className="metric" style={{ fontSize: '1.5rem' }}>{profile.rank.name}</p>
            ) : (
              <p style={{ color: 'var(--tv-muted)', fontSize: '.9rem' }}>No rank yet</p>
            )}
            {profile.next_rank && (
              <small className="text-muted">Next: {profile.next_rank.name}</small>
            )}
            {!profile.next_rank && profile.rank && (
              <small className="text-muted">Top rank achieved!</small>
            )}
          </article>
          <article className="card">
            <h3>Achievements</h3>
            <p className="metric" style={{ fontSize: '1.5rem' }}>
              {(profile.badges?.length ?? 0) + (profile.milestones?.length ?? 0)}
            </p>
            <small className="text-muted">
              {profile.badges?.length ?? 0} badge{(profile.badges?.length ?? 0) !== 1 ? 's' : ''} · {profile.milestones?.length ?? 0} milestone{(profile.milestones?.length ?? 0) !== 1 ? 's' : ''}
            </small>
          </article>
          <article className="card">
            <h3>Participation</h3>
            <p className="metric" style={{ fontSize: '1.5rem' }}>{profile.events_attended ?? 0}</p>
            <small className="text-muted">
              events attended · {profile.tasks_completed ?? 0} tasks done
            </small>
          </article>
        </div>
      </section>

      {/* Two-column action area */}
      <SponsoredPlacement surface="home" />
      <section className="home-columns" aria-label="Next actions and upcoming tickets">
        <article className="panel">
          <p className="eyebrow">Next actions</p>
          <h2>Active tasks</h2>
          {activeTasks.length ? (
            <ul>
              {activeTasks.slice(0, 4).map(task => (
                <li key={task.id}>
                  <span style={{ flex: 1, fontWeight: 600, fontSize: '.875rem' }}>{task.title}</span>
                  <span className={`chip ${task.status === 'submitted' ? 'chip-yellow' : 'chip-blue'}`}>{task.status}</span>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState
              title="All caught up"
              description="No active tasks right now. Discover events to find new opportunities."
              action="Discover events"
              onAction={onDiscover}
            />
          )}
          {activeTasks.length > 0 && onTasks && (
            <button className="link" onClick={onTasks} style={{ marginTop: '.75rem' }}>View all tasks →</button>
          )}
        </article>

        <article className="panel">
          <p className="eyebrow">Upcoming participation</p>
          <h2>Your tickets</h2>
          {upcomingTickets.length ? (
            <ul>
              {upcomingTickets.slice(0, 4).map(ticket => (
                <li key={ticket.public_id}>
                  <span style={{ flex: 1, fontWeight: 600, fontSize: '.875rem' }}>
                    {ticket.event_title || ticket.public_id}
                  </span>
                  {ticket.event_starts_at && (
                    <span style={{ fontSize: '.75rem', color: 'var(--tv-muted)', whiteSpace: 'nowrap' }}>
                      {new Date(ticket.event_starts_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="empty" style={{ marginTop: '.75rem' }}>No upcoming tickets. Discover an event to get started.</p>
          )}
          {upcomingTickets.length > 0 && onTickets && (
            <button className="link" onClick={onTickets} style={{ marginTop: '.75rem' }}>View ticket wallet →</button>
          )}
          {!upcomingTickets.length && (
            <button className="secondary sm" onClick={onDiscover} style={{ marginTop: '.75rem' }}>Browse events</button>
          )}
        </article>
      </section>
    </div>
  );
}
