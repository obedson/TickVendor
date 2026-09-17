import { useState } from 'react';
import { Tasks } from './Tasks';
import { Opportunities } from './Opportunities';
export function CommunityMember({ token, community, onClose }: { token: string; community: { id: string; name: string; description?: string }; onClose: () => void }) {
  const [view, setView] = useState('overview');
  const sections: [string, string][] = [['overview', 'Overview'], ['tasks', 'Tasks'], ['opportunities', 'Opportunities']];
  return <section><button onClick={onClose}>Back to Communities</button><h1>{community.name}</h1><p>Member space — this does not grant administrative access.</p><nav aria-label="Member community sections">{sections.map(([id, label]) => <button key={id} aria-pressed={view === id} onClick={() => setView(id)}>{label}</button>)}</nav>
    {view === 'overview' && <><p>{community.description}</p><p>Your community tasks and eligible opportunities are available here. Tickets and attendance remain in your personal workspace.</p>
      {/* Event discovery is platform-wide; there is no community-scoped events list yet, so say so rather than imply one. */}
      <button onClick={() => window.dispatchEvent(new CustomEvent('tickvendor-open-content', { detail: { content_type: 'event' } }))}>Browse all events</button></>}
    {view === 'tasks' && <Tasks token={token} communityId={community.id} />}{view === 'opportunities' && <Opportunities token={token} communityId={community.id} />}</section>;
}
