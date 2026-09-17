import { useEffect, useRef, useState } from 'react';
import { apiJson, getLiveToken } from './api';
import { mediaUrl } from './EventCover';
export type Placement = { headline: string; body?: string; imageUrl?: string; href?: string; cta?: string; id?: string; classification?: 'featured' | 'sponsored'; content_type?: string; content_id?: string };
export type PlacementSurface = 'home' | 'discover' | 'event-detail' | 'opportunities' | 'communities' | 'tasks';
export function SponsoredPlacement({ surface, placement }: { surface: PlacementSurface; placement?: Placement }) {
  const [items, setItems] = useState<Placement[]>([]); const track = useRef<HTMLDivElement>(null);
  useEffect(() => { let active = true; if (placement) return; const token = getLiveToken(); apiJson<Placement[]>(`promotions/${token ? 'me' : 'public'}?surface=${surface}`, {}, token).then(rows => { if (active) setItems(rows); }).catch(() => { if (active) setItems([]); }); return () => { active = false; }; }, [surface, placement]);
  const rows = placement ? [placement] : items;
  if (!rows.length) return null;
  return <aside aria-label="Featured and Sponsored content"><div className="form-actions"><h2>Featured &amp; Sponsored</h2>{rows.length > 1 && <><button aria-label="Previous placements" onClick={() => track.current?.scrollBy({ left: -320 })}>Previous</button><button aria-label="Next placements" onClick={() => track.current?.scrollBy({ left: 320 })}>Next</button></>}</div>
    <div ref={track} role="region" aria-label="Promoted content carousel" tabIndex={0} style={{ display: 'flex', overflowX: 'auto', gap: '1rem', scrollSnapType: 'x proximity', paddingBottom: '.5rem' }}>
      {rows.map((item, i) => { const href = item.href && /^https?:\/\//.test(item.href) ? item.href : undefined; return <article className="sponsored-placement" key={item.id || i} style={{ flex: '0 0 min(85%, 24rem)', scrollSnapAlign: 'start', overflowWrap: 'anywhere' }}>
        {item.imageUrl && mediaUrl(item.imageUrl) && <img src={mediaUrl(item.imageUrl)} alt="" loading="lazy" />}
        <div><small>{item.classification === 'featured' ? 'Featured' : 'Sponsored'}</small><h3>{item.headline}</h3>{item.body && <p>{item.body}</p>}{href && item.cta && <a href={href} rel="sponsored noopener">{item.cta}</a>}{item.content_type && <button onClick={() => window.dispatchEvent(new CustomEvent('tickvendor-open-content', { detail: item }))}>Explore {item.content_type}</button>}</div>
      </article>; })}
    </div>
  </aside>;
}
