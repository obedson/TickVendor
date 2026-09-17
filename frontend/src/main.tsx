import { StrictMode, Suspense, lazy, useEffect, useState, useCallback } from 'react';
import { createRoot } from 'react-dom/client';
import { fetchWithRetry } from './fetchWithRetry';
import { API_BASE, ApiError, apiJson, addAuthListener, persistSession, clearSession, getLiveToken, type SessionData } from './api';
const Notifications = lazy(() => import('./Notifications').then(m => ({ default: m.Notifications })));
const Communities = lazy(() => import('./Communities').then(m => ({ default: m.Communities })));
const OrganizerDashboard = lazy(() => import('./OrganizerDashboard').then(m => ({ default: m.OrganizerDashboard })));
const OrganizerEvents = lazy(() => import('./OrganizerEvents').then(m => ({ default: m.OrganizerEvents })));
const OrganizerTaskQueue = lazy(() => import('./OrganizerTaskQueue').then(m => ({ default: m.OrganizerTaskQueue })));
const OrganizerOpportunities = lazy(() => import('./OrganizerOpportunities').then(m => ({ default: m.OrganizerOpportunities })));
const OrganizerMembers = lazy(() => import('./OrganizerMembers').then(m => ({ default: m.OrganizerMembers })));
const OrganizerAttendanceReview = lazy(() => import('./OrganizerAttendanceReview').then(m => ({ default: m.OrganizerAttendanceReview })));
const OrganizerAttendanceOperations = lazy(() => import('./OrganizerAttendanceOperations').then(m => ({ default: m.OrganizerAttendanceOperations })));
const AdminPointRules = lazy(() => import('./AdminPointRules').then(m => ({ default: m.AdminPointRules })));
const AdminRecognition = lazy(() => import('./AdminRecognition').then(m => ({ default: m.AdminRecognition })));
const AdminLeaderboards = lazy(() => import('./AdminLeaderboards').then(m => ({ default: m.AdminLeaderboards })));
const AdminContributionBands = lazy(() => import('./AdminContributionBands').then(m => ({ default: m.AdminContributionBands })));
const AdminImpactAdjustment = lazy(() => import('./AdminImpactAdjustment').then(m => ({ default: m.AdminImpactAdjustment })));
const AdminAuditLogs = lazy(() => import('./AdminAuditLogs').then(m => ({ default: m.AdminAuditLogs })));
const AdminNotificationRules = lazy(() => import('./AdminNotificationRules').then(m => ({ default: m.AdminNotificationRules })));
const AdminAnalytics = lazy(() => import('./AdminAnalytics').then(m => ({ default: m.AdminAnalytics })));
const PlatformAdmin = lazy(() => import('./PlatformAdmin').then(m => ({ default: m.PlatformAdmin })));
const Attendance = lazy(() => import('./Attendance').then(m => ({ default: m.Attendance })));
const Tasks = lazy(() => import('./Tasks').then(m => ({ default: m.Tasks })));
const Opportunities = lazy(() => import('./Opportunities').then(m => ({ default: m.Opportunities })));
const Recognition = lazy(() => import('./Recognition').then(m => ({ default: m.Recognition })));
const ProfileEditor = lazy(() => import('./ProfileEditor').then(m => ({ default: m.ProfileEditor })));
const PaymentReturn = lazy(() => import('./PaymentReturn').then(m => ({ default: m.PaymentReturn })));
import { cacheTicketWallet, clearCachedTicketWallet, loadCachedTicketWallet, type OfflineTicket } from './offlineTickets';
import './designTokens.css';
import './styles.css';
import './workspace-selector.css';
import './management.css';
import { AppShell, EmptyState, type WorkspaceCommunity } from './AppShell';
import { HomeDashboard } from './HomeDashboard';
import { EventCover } from './EventCover';
import { SponsoredPlacement } from './SponsoredPlacement';
import { EventSupport } from './EventSupport';
import { ManagedEventSelector } from './ManagedEventSelector';
import { PasswordInput } from './PasswordInput';
import { GoogleButton, GoogleReturn, PasswordRecovery } from './AuthRecovery';
import { useRevealFocus } from './RevealFocus';
import { archiveItem, usePersonalArchive } from './PersonalHistory';

interface BeforeInstallPromptEvent extends Event { prompt: () => Promise<void>; userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }> }
type EventItem = { id: string; title: string; description: string; category: string; cover_image_url?: string | null; starts_at: string; ends_at?: string; venue?: { name: string; city?: string } | null };
type Session = SessionData;
type TicketType = { id: string; name: string; description?: string; price: string; currency: string; availability: number; max_per_user: number };

const API = API_BASE;

/* ── Auth screen ─────────────────────────────────────────── */
function Auth({ onLogin }: { onLogin: (session: Session) => void }) {
  const [mode, setMode] = useState<'login' | 'register' | 'resend'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [username, setUsername] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  useRevealFocus(error || message, '#auth-result');

  const switchMode = (next: typeof mode) => { setMode(next); setPassword(''); setError(''); setMessage(''); };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError(''); setMessage('');
    try {
      const endpoint = mode === 'login' ? '/auth/login' : mode === 'register' ? '/auth/register' : '/auth/verification/resend';
      const body = mode === 'login' ? { email, password } : mode === 'register' ? { email, password, username, display_name: name } : { email };
      const response = await fetch(`${API}${endpoint}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(
          response.status === 401 ? 'Invalid email or password.' :
          response.status === 409 ? 'Email or username is already registered.' :
          response.status === 503 ? (data?.detail || 'Verification email could not be sent. Please try again.') :
          data?.detail || 'Unable to complete request.'
        );
      }
      const data = await response.json();
      if (mode === 'login') onLogin(data);
      else if (mode === 'register') { switchMode('login'); setMessage('Account created! Check your email to verify, then sign in.'); }
      else setMessage('If the account needs verification, a new email was sent.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Network error. Please try again.');
    } finally { setBusy(false); }
  };

  const titles: Record<typeof mode, string> = {
    login: 'Welcome back',
    register: 'Create your account',
    resend: 'Resend verification',
  };
  const subtitles: Record<typeof mode, string> = {
    login: 'Sign in to discover events and track your impact.',
    register: 'Join your community and start earning Impact Points.',
    resend: 'Enter your email to receive a new verification link.',
  };

  return (
    <main className="auth">
      <section className="panel" aria-labelledby="auth-title">
        <div className="auth-brand">
          <div className="auth-brand-logo" aria-hidden="true">TV</div>
          <span className="auth-brand-name">TickVendor</span>
        </div>
        <h1 id="auth-title">{titles[mode]}</h1>
        <p>{subtitles[mode]}</p>

        {message && <p id="auth-result" role="status" className="success-msg">{message}</p>}
        {error && <p id="auth-result" role="alert" className="error">{error}</p>}

        <form onSubmit={submit}>
          <label>
            <span className="label-text">Email address</span>
            <input required type="email" autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" />
          </label>
          {mode !== 'resend' && (
            <PasswordInput key={mode} required minLength={mode === 'login' ? 1 : 12} maxLength={72} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} value={password} onChange={e => setPassword(e.target.value)} aria-describedby={error ? 'auth-result' : undefined} placeholder={mode === 'login' ? 'Your password' : 'At least 12 characters'} />
          )}
          {mode === 'register' && (
            <div className="form-row">
              <label>
                <span className="label-text">Username</span>
                <input required minLength={3} autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} placeholder="yourhandle" />
              </label>
              <label>
                <span className="label-text">Display name</span>
                <input required autoComplete="name" value={name} onChange={e => setName(e.target.value)} placeholder="Your Name" />
              </label>
            </div>
          )}
          <div className="form-actions">
            <button type="submit" className="primary" disabled={busy} style={{ width: '100%' }}>
              {busy ? 'Working…' : mode === 'login' ? 'Sign in' : mode === 'register' ? 'Create account' : 'Send verification email'}
            </button>
          </div>
        </form>

        {mode !== 'resend' && <GoogleButton />}

        <div className="auth-footer">
          {mode === 'login' && (
            <>
              <button className="link" onClick={() => switchMode('register')}>Don't have an account? Create one</button>
              <button className="link" onClick={() => switchMode('resend')}>Resend verification email</button>
              <a href="/forgot-password">Forgot password?</a>
            </>
          )}
          {mode === 'register' && (
            <button className="link" onClick={() => switchMode('login')}>Already have an account? Sign in</button>
          )}
          {mode === 'resend' && (
            <button className="link" onClick={() => switchMode('login')}>Back to sign in</button>
          )}
        </div>
      </section>
    </main>
  );
}

/* ── Email verification screen ───────────────────────────── */
function Verification({ token }: { token: string }) {
  const [state, setState] = useState<'checking' | 'success' | 'error'>('checking');
  const [seconds, setSeconds] = useState(4);
  const goToSignIn = () => window.location.assign('/');

  useEffect(() => {
    let timer: number | undefined;
    fetch(`${API}/auth/verify-email`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token }) })
      .then(response => {
        if (!response.ok) throw Error('invalid');
        setState('success');
        timer = window.setInterval(() => setSeconds(current => {
          if (current <= 1) { window.clearInterval(timer); goToSignIn(); return 0; }
          return current - 1;
        }), 1000);
      })
      .catch(() => setState('error'));
    return () => { if (timer) window.clearInterval(timer); };
  }, [token]);

  return (
    <main className="auth">
      <section className="panel" aria-labelledby="verify-title">
        <div className="auth-brand">
          <div className="auth-brand-logo" aria-hidden="true">TV</div>
          <span className="auth-brand-name">TickVendor</span>
        </div>
        {state === 'checking' && <p role="status">Verifying your email address…</p>}
        {state === 'success' && (
          <>
            <h1 id="verify-title">Email verified ✓</h1>
            <p className="success-msg">Your email address has been verified. You can now sign in.</p>
            <p role="status" aria-live="polite" className="text-muted text-sm">Redirecting to sign in in {seconds} seconds…</p>
            <div className="form-actions" style={{ marginTop: '1rem' }}>
              <button className="primary" onClick={goToSignIn}>Sign in now</button>
            </div>
          </>
        )}
        {state === 'error' && (
          <>
            <h1 id="verify-title">Verification unavailable</h1>
            <p className="error">This link is invalid, expired, or has already been used.</p>
            <div className="form-actions" style={{ marginTop: '1rem' }}>
              <button className="secondary" onClick={goToSignIn}>Back to sign in</button>
            </div>
          </>
        )}
      </section>
    </main>
  );
}

/* ── Ticket QR card ──────────────────────────────────────── */
function TicketQr({ ticket }: { ticket: OfflineTicket }) {
  const [src, setSrc] = useState('');
  const [qrError, setQrError] = useState(false);

  useEffect(() => {
    let active = true;
    import('qrcode')
      .then(({ default: QRCode }) => QRCode.toDataURL(ticket.qr_token, { width: 240, margin: 2, color: { dark: '#172554', light: '#ffffff' } }))
      .then(data => { if (active) setSrc(data); })
      .catch(() => { if (active) setQrError(true); });
    return () => { active = false; };
  }, [ticket.qr_token]);

  const statusColor = ticket.status === 'active' ? 'chip-green' : ticket.status === 'used' ? 'chip-default' : 'chip-yellow';

  return (
    <article className="ticket-card" aria-label={`Ticket for ${ticket.event_title || ticket.public_id}`}>
      <div className="ticket-card-header">
        <h3>{ticket.event_title || `Ticket ${ticket.public_id}`}</h3>
        {ticket.ticket_type_name && <p>{ticket.ticket_type_name}</p>}
      </div>
      <div className="ticket-card-body">
        {src && !qrError ? (
          <img src={src} alt={`QR code for ticket ${ticket.public_id}`} />
        ) : qrError ? (
          <p className="text-muted text-sm">QR code unavailable</p>
        ) : (
          <p role="status" className="text-muted text-sm">Generating QR code…</p>
        )}
        {ticket.event_starts_at && (
          <time dateTime={ticket.event_starts_at} style={{ display: 'block', fontSize: '.85rem', color: 'var(--tv-muted)', marginTop: '.5rem' }}>
            {new Date(ticket.event_starts_at).toLocaleString()}
          </time>
        )}
        {ticket.venue_name && <p style={{ fontSize: '.85rem', color: 'var(--tv-muted)', margin: '.25rem 0 0' }}>{ticket.venue_name}</p>}
      </div>
      <div className="ticket-card-footer">
        <code style={{ fontSize: '.75rem', color: 'var(--tv-muted)' }}>{ticket.public_id}</code>
        <span className={`chip ${statusColor}`}>{ticket.status}</span>
      </div>
    </article>
  );
}

/* ── Events discovery view ───────────────────────────────── */
function EventsView({
  events, loading, error, query, setQuery, selected, setSelected,
  types, typesError, purchase, purchaseError, purchasingTypeId, acquire, onRetry, offset, setOffset,
}: {
  events: EventItem[]; loading: boolean; error: string; query: string;
  setQuery: (q: string) => void; selected: EventItem | null;
  setSelected: (e: EventItem | null) => void; types: TicketType[];
  typesError: string; purchase: string; purchaseError: string; purchasingTypeId: string;
  acquire: (t: TicketType) => void;
  onRetry: () => void;
  offset: number; setOffset: (value: number) => void;
}) {
  if (selected) {
    return (
      <div>
        <EventCover url={selected.cover_image_url} title={selected.title} category={selected.category} />
        <div className="page-header">
          <div className="page-header-text">
            <button className="link" onClick={() => setSelected(null)} style={{ marginBottom: '.75rem', display: 'inline-flex', alignItems: 'center', gap: '.35rem' }}>
              ← Back to events
            </button>
            <p className="eyebrow">{selected.category}</p>
            <h1>{selected.title}</h1>
          </div>
        </div>

        <div className="content-with-aside">
          <div>
            <div className="panel" style={{ marginBottom: '1rem' }}>
              <h2 style={{ fontSize: '1.1rem', marginBottom: '.75rem' }}>About this event</h2>
              <p className="event-story">{selected.description}</p>
              <EventSupport />
              <SponsoredPlacement surface="event-detail" />
            </div>
            <div className="panel">
              <h2 style={{ fontSize: '1.1rem', marginBottom: '.75rem' }}>Date &amp; location</h2>
              <p>
                <strong>Starts:</strong>{' '}
                <time dateTime={selected.starts_at}>{new Date(selected.starts_at).toLocaleString()}</time>
              </p>
              {selected.ends_at && (
                <p>
                  <strong>Ends:</strong>{' '}
                  <time dateTime={selected.ends_at}>{new Date(selected.ends_at).toLocaleString()}</time>
                </p>
              )}
              <p>
                <strong>Location:</strong>{' '}
                {selected.venue?.name || 'Online event'}
                {selected.venue?.city ? `, ${selected.venue.city}` : ''}
              </p>
            </div>
          </div>

          <div>
            <div className="panel">
              <h2 style={{ fontSize: '1.1rem', marginBottom: '1rem' }}>Get tickets</h2>
              {typesError && <p role="alert" className="error">{typesError}</p>}
              {!typesError && !types.length && <p role="status" className="text-muted text-sm">Loading ticket options…</p>}
              {purchase && <p role="status" className="success-msg" style={{ marginBottom: '1rem' }}>{purchase}</p>}
              {purchaseError && <p role="alert" className="error" style={{ marginBottom: '1rem' }}>{purchaseError}</p>}
              <div className="stack">
                {types.map(type => (
                  <div key={type.id} style={{ padding: '1rem', border: '1.5px solid var(--tv-border)', borderRadius: 'var(--tv-radius-md)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '.5rem', marginBottom: '.5rem' }}>
                      <strong style={{ fontSize: '.95rem' }}>{type.name}</strong>
                      <span style={{ fontWeight: 800, color: 'var(--tv-ink)', whiteSpace: 'nowrap' }}>
                        {Number(type.price) === 0 ? 'Free' : `${type.currency} ${Number(type.price).toLocaleString()}`}
                      </span>
                    </div>
                    {type.description && <p style={{ fontSize: '.85rem', color: 'var(--tv-muted)', margin: '0 0 .75rem' }}>{type.description}</p>}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '.5rem' }}>
                      <span className={`chip ${type.availability > 0 ? 'chip-green' : 'chip-red'}`}>
                        {type.availability > 0 ? `${type.availability} available` : 'Sold out'}
                      </span>
                      <button
                        className="accent sm"
                        disabled={!type.availability || Boolean(purchasingTypeId) || Boolean(purchase)}
                        onClick={() => acquire(type)}
                      >
                        {purchasingTypeId === type.id ? 'Starting checkout…' : type.availability ? 'Get ticket' : 'Sold out'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <div className="page-header-text">
          <p className="eyebrow">Discover</p>
          <h1>Find your next event</h1>
          <p>Explore opportunities to participate, connect, and make an impact.</p>
        </div>
        <div className="page-header-actions">
          <div className="search-input">
            <span className="search-icon" aria-hidden="true">⌕</span>
            <input
              type="search"
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Search events…"
              aria-label="Search events"
              style={{ width: 'min(100%, 22rem)' }}
            />
          </div>
        </div>
      </div>

      {loading && <p role="status" className="text-muted">Loading events…</p>}
      {error && (
        <p role="alert" className="error">
          {error}{' '}
          <button className="link" onClick={onRetry}>Retry</button>
        </p>
      )}
      {!loading && !error && !events.length && (
        <EmptyState
          title={query ? 'No events match your search' : 'No events available'}
          description={query ? 'Try a different search term or clear your search to see all events.' : 'No published upcoming or ongoing events match this page. Past, cancelled and suspended events are excluded.'}
          action={query ? 'Clear search' : undefined}
          onAction={query ? () => setQuery('') : undefined}
        />
      )}
      <div className="form-actions"><button disabled={!offset || loading} onClick={() => setOffset(Math.max(0, offset - 20))}>Previous events</button><button disabled={events.length < 20 || loading} onClick={() => setOffset(offset + 20)}>Next events</button></div>
      <SponsoredPlacement surface="discover" />
      <div className="grid">
        {events.map(event => (
          <article className="card event-card" key={event.id} style={{ display: 'flex', flexDirection: 'column', gap: '.5rem' }}>
            <EventCover url={event.cover_image_url} title={event.title} category={event.category} />
            <p className="eyebrow" style={{ marginBottom: 0 }}>{event.category}</p>
            <h3 style={{ margin: 0 }}>{event.title}</h3>
            <p style={{ color: 'var(--tv-muted)', fontSize: '.875rem', flex: 1, margin: 0 }}>
              {event.description.length > 120 ? event.description.slice(0, 120) + '…' : event.description}
            </p>
            <time style={{ fontSize: '.8rem', color: 'var(--tv-muted-light)', display: 'block' }}>
              {new Date(event.starts_at).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })}
            </time>
            {event.venue?.name && (
              <p style={{ fontSize: '.8rem', color: 'var(--tv-muted-light)', margin: 0 }}>
                📍 {event.venue.name}{event.venue.city ? `, ${event.venue.city}` : ''}
              </p>
            )}
            <button className="secondary sm" onClick={() => setSelected(event)} style={{ marginTop: '.25rem', alignSelf: 'flex-start' }}>
              View event
            </button>
          </article>
        ))}
      </div>
    </div>
  );
}

/* ── Tickets view ────────────────────────────────────────── */
function TicketsView({ tickets, token }: { tickets: OfflineTicket[]; token: string }) {
  const [view, setView] = useState('active');
  const [archiveError, setArchiveError] = useState('');
  const [busy, setBusy] = useState(false);
  const archive = usePersonalArchive(token, 'ticket');
  const historical = (ticket: OfflineTicket) => ['used', 'cancelled', 'refunded', 'expired'].includes(ticket.status) || Boolean(ticket.event_ends_at && new Date(ticket.event_ends_at).getTime() < Date.now());
  const visible = tickets.filter(ticket => view === 'archived' ? archive.ids.has(ticket.id || '') : !archive.ids.has(ticket.id || '') && (view === 'history' ? historical(ticket) : !historical(ticket)));
  return (
    <div>
      <div className="page-header">
        <div className="page-header-text">
          <p className="eyebrow">My tickets</p>
          <h1>Ticket wallet</h1>
          <p>Your event tickets with QR codes for check-in.</p>
        </div>
      </div>
      <nav className="section-tabs" aria-label="Ticket wallet filters">{['active', 'history', 'archived'].map(value => <button key={value} className="secondary" aria-pressed={view === value} onClick={() => setView(value)}>{value === 'active' ? 'Active / Upcoming' : value === 'history' ? 'History' : 'Archived'}</button>)}</nav>
      {(archive.error || archiveError) && <p className="error" role="alert">{archive.error || archiveError}</p>}
      {!visible.length ? (
        <EmptyState
          title={tickets.length ? 'No tickets in this view' : 'No tickets yet'}
          description={tickets.length ? 'Check Active / Upcoming, History or Archived for your other tickets.' : 'Acquire a ticket from an event to see it here. Your tickets are stored securely on this device.'}
        />
      ) : (
        <div className="ticket-wallet">
          {visible.map(ticket => <div key={ticket.public_id}><TicketQr ticket={ticket} />{(historical(ticket) || archive.ids.has(ticket.id || '')) && <button className="secondary" disabled={busy || !ticket.id} onClick={async () => { setBusy(true); setArchiveError(''); try { await archiveItem(token, 'ticket', ticket.id!, !archive.ids.has(ticket.id || '')); } catch (cause) { setArchiveError(cause instanceof Error ? cause.message : 'Archive action failed.'); } finally { setBusy(false); } }}>{archive.ids.has(ticket.id || '') ? 'Restore to wallet' : 'Archive ticket'}</button>}</div>)}
        </div>
      )}
    </div>
  );
}

/* ── Page loading fallback ───────────────────────────────── */
function PageLoader({ label = 'Loading…' }: { label?: string }) {
  return (
    <div style={{ padding: '3rem 1rem', textAlign: 'center' }}>
      <p role="status" className="text-muted">{label}</p>
    </div>
  );
}

/* ── Main App ────────────────────────────────────────────── */
function App() {
  const [session, setSession] = useState<Session | null>(() => {
    try { return JSON.parse(sessionStorage.getItem('tickvendor.session') || 'null'); } catch { return null; }
  });

  // Subscribe to auth state changes (token refresh, sign-out) so React state
  // stays in sync with the canonical session in sessionStorage.
  useEffect(() => {
    return addAuthListener(updated => setSession(updated));
  }, []);
  const [paymentReturn] = useState(() => {
    const params = new URLSearchParams(location.search);
    return {
      paymentId: params.get('payment_id'),
      providerReference: params.get('reference') || params.get('trxref'),
    };
  });
  const [events, setEvents] = useState<EventItem[]>([]);
  const [tickets, setTickets] = useState<OfflineTicket[]>([]);
  const [query, setQuery] = useState('');
  const [eventOffset, setEventOffset] = useState(0);
  const [eventsError, setEventsError] = useState('');
  const [eventsLoading, setEventsLoading] = useState(false);
  const [view, setView] = useState<
    'home' | 'events' | 'opportunities' | 'tickets' | 'attendance' | 'tasks' |
    'recognition' | 'profile' | 'communities' | 'notifications' |
    'organizer-dashboard' | 'organizer-events' | 'organizer-opportunities' |
    'organizer-tasks' | 'organizer-members' | 'organizer-review' | 'organizer-attendance' |
    'admin-rules' | 'admin-bands' | 'admin-leaderboards' | 'admin-adjustments' |
    'admin-recognition' | 'admin-notifications' | 'admin-analytics' | 'admin-audit' |
    'platform-admin'
  >('home');
  const [promotedTaskId, setPromotedTaskId] = useState<string | undefined>();
  const [promotedOpportunityId, setPromotedOpportunityId] = useState<string | undefined>();
  const [selectedEvent, setSelectedEvent] = useState<EventItem | null>(null);
  const [types, setTypes] = useState<TicketType[]>([]);
  const [typesError, setTypesError] = useState('');
  const [purchase, setPurchase] = useState('');
  const [purchaseError, setPurchaseError] = useState('');
  const [purchasingTypeId, setPurchasingTypeId] = useState('');
  const [installPrompt, setInstallPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [workspace, setWorkspace] = useState<'participant' | 'management' | 'platform'>('participant');
  useEffect(() => { const open = (event: Event) => { const item = (event as CustomEvent).detail; if (!['community', 'event', 'opportunity', 'task'].includes(item?.content_type)) return;
    setWorkspace('participant');
    if (item.content_type === 'event') { setView('events'); if (item.content_id) apiJson<EventItem>(`events/${item.content_id}`).then(setSelectedEvent).catch(e => setEventsError(e.message)); }
    else if (item.content_type === 'task') { setPromotedTaskId(item.content_id); setView('tasks'); }
    else if (item.content_type === 'opportunity') { setPromotedOpportunityId(item.content_id); setView('opportunities'); }
    else setView('communities');
  }; window.addEventListener('tickvendor-open-content', open); return () => window.removeEventListener('tickvendor-open-content', open); }, []);
  const [managedCommunities, setManagedCommunities] = useState<WorkspaceCommunity[]>([]);
  const [selectedCommunityId, setSelectedCommunityId] = useState('');
  const [membershipRevision, setMembershipRevision] = useState(0);
  useEffect(() => {
    const changed = () => setMembershipRevision(value => value + 1);
    window.addEventListener('tickvendor-memberships-changed', changed);
    return () => window.removeEventListener('tickvendor-memberships-changed', changed);
  }, []);

  const isSuperAdmin = session?.user?.role === 'super_admin';

  const roleItems = [
    { id: 'organizer-dashboard', label: 'Dashboard', icon: '⌂' },
    { id: 'organizer-events', label: 'Events', icon: '◈' },
    { id: 'organizer-opportunities', label: 'Opportunities', icon: '◇' },
    { id: 'organizer-tasks', label: 'Tasks', icon: '✓' },
    { id: 'organizer-members', label: 'Members', icon: '♧' },
    { id: 'organizer-review', label: 'Attendance review', icon: '◎' },
    { id: 'organizer-attendance', label: 'Check-in', icon: '▣' },
    { id: 'admin-rules', label: 'Point rules', icon: '◆' },
    { id: 'admin-bands', label: 'Contribution Tiers', icon: '◫' },
    { id: 'admin-leaderboards', label: 'Leaderboard', icon: '▥' },
    { id: 'admin-adjustments', label: 'Adjustments', icon: '±' },
    { id: 'admin-recognition', label: 'Recognition', icon: '★' },
    { id: 'admin-notifications', label: 'Notifications', icon: '◌' },
    { id: 'admin-analytics', label: 'Analytics', icon: '▤' },
    { id: 'admin-audit', label: 'Audit log', icon: '≡' },
    // Super Admin only — platform-wide administration.
    ...(isSuperAdmin ? [{ id: 'platform-admin', label: 'Platform Admin', icon: '⚙' }] : []),
  ];

  // Service worker + install prompt
  useEffect(() => {
    const handler = (event: Event) => { event.preventDefault(); setInstallPrompt(event as BeforeInstallPromptEvent); };
    window.addEventListener('beforeinstallprompt', handler);
    if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {});
    return () => window.removeEventListener('beforeinstallprompt', handler);
  }, []);

  // Validate session on mount — use live token so a prior refresh is honoured.
  useEffect(() => {
    if (!session) return;
    const token = getLiveToken() ?? session.access_token;
    fetch(`${API}/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => { if (!r.ok) throw Error('expired'); })
      .catch(() => clearSession());
  }, []);

  // Load managed communities — include admin AND organizer roles per spec.
  // Uses apiJson so a 401 triggers refresh before failing.
  useEffect(() => {
    if (!session) return;
    apiJson<any[]>('communities/me', {}, getLiveToken() ?? session.access_token)
      .then(items => {
        const manageable = items
          .filter(item => item.membership?.status === 'active' && item.community?.is_active !== false &&
            (item.membership?.role === 'admin' || item.membership?.role === 'organizer'))
          .map(item => ({ id: item.id, name: item.community?.name ?? item.name, role: item.membership.role, status: item.membership.status }));
        setManagedCommunities(manageable);
        if (selectedCommunityId && !manageable.some(item => item.id === selectedCommunityId)) {
          setSelectedCommunityId(''); setWorkspace('participant'); setView('home');
        }
      })
      .catch(() => setManagedCommunities([]));
  }, [session?.access_token, membershipRevision]);

  // Load events — public endpoint, no auth required, but use fetchWithRetry for resilience.
  const loadEvents = useCallback(() => {
    if (!session) return;
    setEventsLoading(true); setEventsError('');
    fetchWithRetry(`${API}/events?search=${encodeURIComponent(query)}&limit=20&offset=${eventOffset}`)
      .then(r => { if (!r.ok) throw Error('Unable to load events'); return r.json(); })
      .then(setEvents)
      .catch((e: Error) => setEventsError(e.message))
      .finally(() => setEventsLoading(false));
  }, [session?.access_token, query, eventOffset]);

  useEffect(() => { loadEvents(); }, [loadEvents]);

  // Load ticket wallet — uses apiJson for refresh-on-401.
  useEffect(() => {
    if (!session) return;
    apiJson<OfflineTicket[]>('tickets/me', {}, getLiveToken() ?? session.access_token)
      .then(async data => { setTickets(data); await cacheTicketWallet(data); })
      .catch(async () => setTickets(await loadCachedTicketWallet()));
  }, [session?.access_token]);

  // Load ticket types for selected event — uses apiJson for refresh-on-401.
  useEffect(() => {
    if (!selectedEvent || !session) return;
    setTypes([]); setTypesError('');
    apiJson<TicketType[]>(`events/${selectedEvent.id}/ticket-types`, {}, getLiveToken() ?? session.access_token)
      .then(setTypes)
      .catch((e: Error) => setTypesError(e.message));
  }, [selectedEvent?.id, session?.access_token]);

  // Auth gate
  if (location.pathname === '/forgot-password') return <PasswordRecovery />;
  if (location.pathname === '/reset-password') return <PasswordRecovery reset />;
  if (location.pathname === '/auth/google/return') return <GoogleReturn onLogin={data => { persistSession(data); setSession(data); }} />;
  if (!session) {
    const verificationToken = new URLSearchParams(location.search).get('token');
    if (location.pathname === '/verify-email' && verificationToken) return <Verification token={verificationToken} />;
    return <Auth onLogin={data => { persistSession(data); setSession(data); }} />;
  }

  // Payment return
  if (paymentReturn.paymentId || paymentReturn.providerReference) {
    return (
      <Suspense fallback={<PageLoader label="Loading payment status…" />}>
        <PaymentReturn
          token={session.access_token}
          paymentId={paymentReturn.paymentId}
          providerReference={paymentReturn.providerReference}
        />
      </Suspense>
    );
  }

  const logout = async () => { clearSession(); await clearCachedTicketWallet(); };
  const install = async () => { if (installPrompt) { await installPrompt.prompt(); await installPrompt.userChoice; setInstallPrompt(null); } };

  const acquire = async (type: TicketType) => {
    if (!session) return;
    setPurchase('');
    setPurchaseError('');
    setPurchasingTypeId(type.id);
    try {
      // Always use the live token (may have been refreshed since component mounted).
      const liveToken = getLiveToken() ?? session.access_token;
      const order = await apiJson<{ id: string }>(
        `events/${selectedEvent?.id}/orders`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ticket_type_id: type.id, quantity: 1, idempotency_key: `web-order-${crypto.randomUUID()}` }),
        },
        liveToken,
      );
      if (Number(type.price) === 0) {
        // Free ticket: no Paystack checkout. Refresh wallet immediately.
        setPurchase('Ticket confirmed! Open My Tickets to view your QR code.');
        const wallet = await apiJson<OfflineTicket[]>('tickets/me', {}, getLiveToken() ?? liveToken);
        setTickets(wallet); await cacheTicketWallet(wallet);
        return;
      }
      // Paid ticket: initialize Paystack checkout.
      const payment = await apiJson<{ checkout_url: string }>(
        'payments/initialize',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ order_id: order.id, idempotency_key: `web-payment-${order.id}` }),
        },
        getLiveToken() ?? liveToken,
      );
      window.location.assign(payment.checkout_url);
    } catch (err) {
      const message = err instanceof ApiError
        ? err.message
        : 'Ticket checkout could not be started. Please try again.';
      setPurchaseError(message);
      if (selectedEvent) {
        apiJson<TicketType[]>(`events/${selectedEvent.id}/ticket-types`, {}, getLiveToken() ?? session.access_token)
          .then(setTypes)
          .catch(() => {});
      }
    } finally {
      setPurchasingTypeId('');
    }
  };

  const navigateTo = (next: typeof view) => {
    setView(next);
    // Reset event selection when leaving events view
    if (next !== 'events') setSelectedEvent(null);
  };

  return (
    <AppShell
      user={session.user}
      view={view}
      setView={next => navigateTo(next as typeof view)}
      installPrompt={installPrompt}
      onInstall={install}
      onSignOut={logout}
      onProfile={() => navigateTo('profile')}
      roleItems={roleItems}
      workspace={workspace}
      isSuperAdmin={isSuperAdmin}
      selectedCommunity={managedCommunities.find(item => item.id === selectedCommunityId)}
      managedCommunities={managedCommunities}
      onWorkspaceChange={(next, communityId) => {
        if (next === 'management' && !managedCommunities.some(item => item.id === communityId)) return;
        if (next === 'platform' && !isSuperAdmin) return;
        setWorkspace(next);
        if (next === 'participant') { navigateTo('home'); }
        else if (next === 'platform' && isSuperAdmin) { navigateTo('platform-admin'); }
        else { setSelectedCommunityId(communityId!); navigateTo('organizer-dashboard'); }
      }}
    >
      <Suspense key={`${workspace}:${selectedCommunityId}`} fallback={<PageLoader />}>
        <main id="main">
          {view === 'home' && <HomeDashboard token={session.access_token} onDiscover={() => navigateTo('events')} onTasks={() => navigateTo('tasks')} onTickets={() => navigateTo('tickets')} />}
          {view === 'events' && (
            <EventsView
              events={events} loading={eventsLoading} error={eventsError}
              query={query} setQuery={value => { setQuery(value); setEventOffset(0); }} offset={eventOffset} setOffset={setEventOffset}
              selected={selectedEvent} setSelected={setSelectedEvent}
              types={types} typesError={typesError}
              purchase={purchase} purchaseError={purchaseError}
              purchasingTypeId={purchasingTypeId} acquire={acquire}
              onRetry={loadEvents}
            />
          )}
          {view === 'tickets' && <TicketsView tickets={tickets} token={session.access_token} />}
          {view === 'opportunities' && <Opportunities initialId={promotedOpportunityId} token={session.access_token} />}
          {view === 'attendance' && <Attendance token={session.access_token} tickets={tickets} />}
          {view === 'tasks' && <Tasks initialTaskId={promotedTaskId} token={session.access_token} />}
          {view === 'recognition' && <Recognition token={session.access_token} />}
          {view === 'profile' && <ProfileEditor token={session.access_token} />}
          {view === 'communities' && <Communities isSuperAdmin={isSuperAdmin} token={session.access_token} />}
          {view === 'notifications' && <Notifications token={session.access_token} />}
          {view === 'organizer-dashboard' && <OrganizerDashboard token={session.access_token} />}
          {view === 'organizer-events' && <OrganizerEvents token={session.access_token} communityId={selectedCommunityId} />}
          {view === 'organizer-opportunities' && <OrganizerOpportunities token={session.access_token} communityId={selectedCommunityId} />}
          {view === 'organizer-tasks' && <OrganizerTaskQueue token={session.access_token} communityId={selectedCommunityId} />}
          {view === 'organizer-members' && <OrganizerMembers token={session.access_token} communityId={selectedCommunityId} />}
          {view === 'organizer-review' && <ManagedEventSelector token={session.access_token} communityId={selectedCommunityId}>{eventId => <OrganizerAttendanceReview token={session.access_token} eventId={eventId} />}</ManagedEventSelector>}
          {view === 'organizer-attendance' && <ManagedEventSelector token={session.access_token} communityId={selectedCommunityId}>{eventId => <OrganizerAttendanceOperations token={session.access_token} eventId={eventId} />}</ManagedEventSelector>}
          {view === 'admin-rules' && workspace === 'management' && <AdminPointRules token={session.access_token} communityId={selectedCommunityId} />}
          {view === 'admin-bands' && workspace === 'management' && <AdminContributionBands token={session.access_token} communityId={selectedCommunityId} />}
          {view === 'admin-leaderboards' && workspace === 'management' && <AdminLeaderboards token={session.access_token} communityId={selectedCommunityId} />}
          {view === 'admin-adjustments' && workspace === 'management' && <AdminImpactAdjustment token={session.access_token} communityId={selectedCommunityId} />}
          {view === 'admin-recognition' && workspace === 'management' && <AdminRecognition token={session.access_token} communityId={selectedCommunityId} />}
          {view === 'admin-notifications' && workspace === 'management' && <AdminNotificationRules token={session.access_token} communityId={selectedCommunityId} />}
          {view === 'admin-analytics' && workspace === 'management' && <AdminAnalytics token={session.access_token} communityId={selectedCommunityId} />}
          {view === 'admin-audit' && workspace === 'management' && <AdminAuditLogs token={session.access_token} communityId={selectedCommunityId} />}
          {view === 'platform-admin' && isSuperAdmin && <PlatformAdmin token={session.access_token} userRole={session.user.role} />}
        </main>
      </Suspense>
    </AppShell>
  );
}

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>);
