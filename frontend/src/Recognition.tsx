import { useEffect, useState } from 'react';
import { apiJson, ApiError } from './api';
import { EmptyState } from './AppShell';

type Badge = { id: string; name: string; slug: string; category?: string; awarded_at?: string };
type Milestone = { id: string; name: string; slug: string; awarded_at?: string };
type RankHistory = { name: string; achieved_at: string };
type LeaderboardEntry = { user_id: string; username?: string; display_name?: string; score: number; rank: number };
type ProfileData = {
  display_name?: string;
  impact_points?: number;
  rank?: { name: string; slug: string } | null;
  next_rank?: { name: string; points_remaining: number } | null;
  badges?: Badge[];
  milestones?: Milestone[];
  rank_history?: RankHistory[];
  events_attended?: number;
  tasks_completed?: number;
};
type Leaderboard = { entries?: LeaderboardEntry[] };

type RecognitionProps = { token: string; communityId?: string };

export function Recognition({ token, communityId }: RecognitionProps) {
  const [data, setData] = useState<ProfileData | null>(null);
  const [leaderboard, setLeaderboard] = useState<Leaderboard | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'overview' | 'badges' | 'milestones' | 'leaderboard'>('overview');

  useEffect(() => {
    setLoading(true);
    const profilePath = communityId ? `profiles/me?community_id=${communityId}` : 'profiles/me';
    const promises: Promise<unknown>[] = [
      apiJson<ProfileData>(profilePath, {}, token).then(setData),
    ];
    if (communityId) {
      promises.push(
        apiJson<Leaderboard>(`leaderboards/${communityId}`, {}, token)
          .then(setLeaderboard)
          .catch(() => setLeaderboard(null))
      );
    }
    Promise.all(promises)
      .catch(e => setError(e instanceof ApiError ? e.message : 'Unable to load achievements'))
      .finally(() => setLoading(false));
  }, [token, communityId]);

  if (loading) {
    return (
      <div>
        <div className="page-header">
          <div className="page-header-text">
            <p className="eyebrow">Recognition</p>
            <h1>Achievements</h1>
          </div>
        </div>
        <p role="status" className="text-muted">Loading your achievements…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <div className="page-header">
          <div className="page-header-text">
            <p className="eyebrow">Recognition</p>
            <h1>Achievements</h1>
          </div>
        </div>
        <p role="alert" className="error">{error}</p>
      </div>
    );
  }

  if (!data) return null;

  const nextRankPct = data.next_rank
    ? Math.max(0, Math.min(100, 100 - Math.round((data.next_rank.points_remaining / ((data.impact_points ?? 0) + data.next_rank.points_remaining)) * 100)))
    : 100;

  const tabs = [
    { id: 'overview' as const, label: 'Overview' },
    { id: 'badges' as const, label: `Badges (${data.badges?.length ?? 0})` },
    { id: 'milestones' as const, label: `Milestones (${data.milestones?.length ?? 0})` },
    ...(communityId ? [{ id: 'leaderboard' as const, label: 'Leaderboard' }] : []),
  ];

  return (
    <div>
      <div className="page-header">
        <div className="page-header-text">
          <p className="eyebrow">Recognition</p>
          <h1>Achievements</h1>
          <p>Your impact, badges, milestones, and rank progression.</p>
        </div>
      </div>

      {/* Impact Points hero */}
      <div className="panel" style={{ background: 'linear-gradient(135deg, var(--tv-ink) 0%, var(--tv-ink-secondary) 100%)', color: '#fff', marginBottom: '1.5rem', borderRadius: 'var(--tv-radius-xl)' }}>
        <p style={{ color: 'rgba(255,255,255,.7)', fontSize: '.85rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.1em', margin: '0 0 .5rem' }}>Total Impact Points</p>
        <p style={{ fontSize: 'clamp(2.5rem,6vw,4rem)', fontWeight: 900, letterSpacing: '-.04em', margin: '0 0 .5rem', color: '#fff' }}>
          {(data.impact_points ?? 0).toLocaleString()}
        </p>
        {data.rank && (
          <span style={{ display: 'inline-block', background: 'rgba(255,255,255,.15)', color: '#fff', padding: '.25rem .75rem', borderRadius: 'var(--tv-radius-full)', fontSize: '.85rem', fontWeight: 700 }}>
            {data.rank.name}
          </span>
        )}
        {data.next_rank && (
          <div style={{ marginTop: '1rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '.8rem', color: 'rgba(255,255,255,.7)', marginBottom: '.35rem' }}>
              <span>Progress to {data.next_rank.name}</span>
              <span>{data.next_rank.points_remaining.toLocaleString()} pts remaining</span>
            </div>
            <div style={{ height: '.4rem', background: 'rgba(255,255,255,.2)', borderRadius: 'var(--tv-radius-full)', overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${nextRankPct}%`, background: 'var(--tv-accent-mid)', borderRadius: 'var(--tv-radius-full)', transition: 'width .5s ease' }} />
            </div>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '.5rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
        {tabs.map(tab => (
          <button
            key={tab.id}
            className={activeTab === tab.id ? 'accent sm' : 'secondary sm'}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Overview tab */}
      {activeTab === 'overview' && (
        <div style={{ display: 'grid', gap: '1.25rem' }}>
          <div className="grid-2">
            <div className="card">
              <h3 style={{ fontSize: '.85rem', color: 'var(--tv-muted)', textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: '.5rem' }}>Current rank</h3>
              {data.rank ? (
                <p style={{ fontSize: '1.5rem', fontWeight: 800, margin: 0 }}>{data.rank.name}</p>
              ) : (
                <p className="text-muted">No rank yet — keep participating!</p>
              )}
              {data.next_rank && <p className="text-muted text-sm" style={{ marginTop: '.25rem' }}>Next: {data.next_rank.name}</p>}
            </div>
            <div className="card">
              <h3 style={{ fontSize: '.85rem', color: 'var(--tv-muted)', textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: '.5rem' }}>Participation</h3>
              <p style={{ fontSize: '1.5rem', fontWeight: 800, margin: 0 }}>{data.events_attended ?? 0}</p>
              <p className="text-muted text-sm" style={{ marginTop: '.25rem' }}>events attended · {data.tasks_completed ?? 0} tasks done</p>
            </div>
          </div>

          {/* Rank history */}
          <div className="panel">
            <h2 style={{ fontSize: '1.1rem', marginBottom: '1rem' }}>Rank progression</h2>
            {!data.rank_history?.length ? (
              <EmptyState
                title="No rank history yet"
                description="Earn Impact Points to progress through ranks. Your journey will be recorded here."
              />
            ) : (
              <div className="stack">
                {data.rank_history.map((item, i) => (
                  <div key={`${item.name}-${item.achieved_at}`} style={{ display: 'flex', alignItems: 'center', gap: '1rem', padding: '.65rem .85rem', background: i === 0 ? 'var(--tv-accent-light)' : 'var(--tv-surface-sunken)', borderRadius: 'var(--tv-radius-md)' }}>
                    <span style={{ fontSize: '1.25rem' }}>{i === 0 ? '🏆' : '⬆️'}</span>
                    <div>
                      <strong style={{ fontSize: '.9rem' }}>{item.name}</strong>
                      <p className="text-muted text-xs" style={{ margin: 0 }}>{new Date(item.achieved_at).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Badges tab */}
      {activeTab === 'badges' && (
        <div>
          {!data.badges?.length ? (
            <EmptyState
              title="No badges yet"
              description="Complete activities and reach milestones to earn badges. They'll appear here."
            />
          ) : (
            <div className="badge-grid">
              {data.badges.map(badge => (
                <div key={badge.id} className="badge-item">
                  <div className="badge-icon" aria-hidden="true">🏅</div>
                  <strong style={{ fontSize: '.85rem' }}>{badge.name}</strong>
                  {badge.category && <span className="chip chip-teal" style={{ fontSize: '.7rem' }}>{badge.category}</span>}
                  {badge.awarded_at && (
                    <span className="text-xs text-muted">{new Date(badge.awarded_at).toLocaleDateString()}</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Milestones tab */}
      {activeTab === 'milestones' && (
        <div>
          {!data.milestones?.length ? (
            <EmptyState
              title="No milestones yet"
              description="Milestones are awarded for significant participation achievements. Keep going!"
            />
          ) : (
            <div className="stack">
              {data.milestones.map(milestone => (
                <div key={milestone.id} style={{ display: 'flex', alignItems: 'center', gap: '1rem', padding: '.85rem 1rem', background: 'var(--tv-surface)', border: '1px solid var(--tv-border)', borderRadius: 'var(--tv-radius-md)' }}>
                  <span style={{ fontSize: '1.5rem' }}>🎯</span>
                  <div style={{ flex: 1 }}>
                    <strong>{milestone.name}</strong>
                    {milestone.awarded_at && (
                      <p className="text-muted text-sm" style={{ margin: 0 }}>
                        Achieved {new Date(milestone.awarded_at).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Leaderboard tab */}
      {activeTab === 'leaderboard' && communityId && (
        <div>
          {!leaderboard?.entries?.length ? (
            <EmptyState
              title="Leaderboard not available"
              description="The community leaderboard will appear here once it has been configured and participants have earned points."
            />
          ) : (
            <div className="leaderboard-list">
              {leaderboard.entries.map((entry, i) => (
                <div key={entry.user_id} className="leaderboard-entry">
                  <span className={`leaderboard-rank ${i === 0 ? 'gold' : i === 1 ? 'silver' : i === 2 ? 'bronze' : ''}`}>
                    {i + 1}
                  </span>
                  <span className="leaderboard-name">{entry.display_name || entry.username || 'Anonymous'}</span>
                  <span className="leaderboard-score">{entry.score.toLocaleString()} pts</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
