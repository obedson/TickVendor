import { mediaUrl } from './EventCover';
export type EventPartner = { name: string; website?: string; logoUrl?: string };
// Relationships must come from an authorized event response, never ads.
export function EventSupport({ partners = [] }: { partners?: EventPartner[] }) {
  if (!partners.length) return null;
  return <section aria-label="Event supporters"><h2>Supported by</h2><div className="definition-list">
    {partners.map(partner => <div className="definition-card" key={partner.name}>
      {partner.logoUrl && <img width="80" height="60" style={{ objectFit: 'contain' }} src={mediaUrl(partner.logoUrl)} alt="" />}
      {partner.website && /^https?:\/\//.test(partner.website) ? <a href={partner.website}>{partner.name}</a> : <strong>{partner.name}</strong>}
    </div>)}
  </div></section>;
}
