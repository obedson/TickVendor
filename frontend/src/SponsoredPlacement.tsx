import { mediaUrl } from './EventCover';
export type Placement = { headline: string; body?: string; imageUrl?: string; href?: string; cta?: string };
export type PlacementSurface = 'home' | 'discover' | 'event-detail' | 'opportunities';
// A campaign provider can populate these slots; no fabricated campaign ships.
const placements: Partial<Record<PlacementSurface, Placement>> = {};
export function SponsoredPlacement({ surface, placement = placements[surface] }: { surface: PlacementSurface; placement?: Placement }) {
  if (!placement) return null;
  const href = placement.href && /^https?:\/\//.test(placement.href) ? placement.href : undefined;
  return <aside className="sponsored-placement" aria-label="Sponsored placement">
    {placement.imageUrl && mediaUrl(placement.imageUrl) && <img src={mediaUrl(placement.imageUrl)} alt="" loading="lazy" />}
    <div><small>Sponsored</small><h3>{placement.headline}</h3>{placement.body && <p>{placement.body}</p>}
      {href && placement.cta && <a href={href} rel="sponsored noopener">{placement.cta}</a>}
    </div>
  </aside>;
}
