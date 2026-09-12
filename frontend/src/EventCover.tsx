import { useState } from 'react';
import { API_BASE } from './api';

export function mediaUrl(value: string): string {
  if (/^https?:\/\//.test(value)) return value;
  if (value.startsWith('/') && !value.startsWith('//')) return `${API_BASE.replace(/\/api\/v1$/, '')}${value}`;
  return '';
}
export function EventCover({ url, title, category }: { url?: string | null; title: string; category?: string }) {
  const [failedUrl, setFailedUrl] = useState('');
  const src = url ? mediaUrl(url) : '';
  return src && failedUrl !== src
    ? <img className="event-cover" src={src} alt={`Cover for ${title}`} loading="lazy" onError={() => setFailedUrl(src)} />
    : <div className="event-cover event-cover-fallback" aria-label={`${title} — no cover image`}><span>{category || 'Community event'}</span></div>;
}
