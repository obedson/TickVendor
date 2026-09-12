import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';

export interface BeforeInstallPromptEvent extends Event { prompt: () => Promise<void>; userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }> }
type NavItem = { id: string; label: string; icon: string };
export type WorkspaceCommunity = { id: string; name: string; role: string; status: string };

export const participantNav: NavItem[] = [
  { id: 'home', label: 'Home', icon: '⌂' },
  { id: 'events', label: 'Discover', icon: '◎' },
  { id: 'opportunities', label: 'Opportunities', icon: '◇' },
  { id: 'tickets', label: 'My tickets', icon: '▤' },
  { id: 'activity', label: 'Attendance', icon: '◒' },
  { id: 'achievements', label: 'Achievements', icon: '✦' },
];

export const secondaryNav: NavItem[] = [
  { id: 'tasks', label: 'Tasks', icon: '✓' },
  { id: 'communities', label: 'Communities', icon: '♧' },
  { id: 'notifications', label: 'Notifications', icon: '◌' },
  { id: 'profile', label: 'Profile', icon: '◉' },
];

const managementGroups: { label: string; ids: string[] }[] = [
  { label: 'Overview', ids: ['organizer-dashboard'] },
  { label: 'Programs', ids: ['organizer-events', 'organizer-opportunities', 'organizer-tasks'] },
  { label: 'People', ids: ['organizer-members', 'organizer-review', 'organizer-attendance'] },
  { label: 'Impact', ids: ['admin-leaderboards', 'admin-recognition', 'admin-adjustments'] },
  { label: 'Settings', ids: ['admin-rules', 'admin-bands', 'admin-notifications', 'admin-analytics', 'admin-audit'] },
  // Super Admin only — shown when the platform-admin nav item is present.
  { label: 'Platform', ids: ['platform-admin'] },
];

const VIEW_ALIAS: Record<string, string> = {
  home: 'home',
  activity: 'attendance',
  achievements: 'recognition',
};

export function EmptyState({
  title,
  description,
  action,
  onAction,
}: {
  title: string;
  description: string;
  action?: string;
  onAction?: () => void;
}) {
  return (
    <div className="empty-state">
      <span className="empty-state-icon" aria-hidden="true">◈</span>
      <h3>{title}</h3>
      <p>{description}</p>
      {action && onAction && (
        <button className="secondary" onClick={onAction}>{action}</button>
      )}
    </div>
  );
}

export function AccountMenu({
  user,
  installPrompt,
  onInstall,
  onSignOut,
  onProfile,
}: {
  user: { display_name: string; email: string; role: string };
  installPrompt: BeforeInstallPromptEvent | null;
  onInstall: () => void;
  onSignOut: () => void;
  onProfile: () => void;
}) {
  return (
    <details className="account-menu">
      <summary aria-label={`Account menu for ${user.display_name}`}>
        <span className="avatar" aria-hidden="true">{user.display_name.slice(0, 1).toUpperCase()}</span>
        <span className="account-name">{user.display_name}</span>
        <span aria-hidden="true" style={{ color: 'var(--tv-muted)', fontSize: '.75rem' }}>▾</span>
      </summary>
      <div className="account-popover">
        <div className="account-popover-header">
          <strong>{user.display_name}</strong>
          <small>{user.email}</small>
          <span className="role-label">{user.role.replaceAll('_', ' ')}</span>
        </div>
        <button className="menu-action" onClick={onProfile}>
          <span aria-hidden="true">◉</span> Profile &amp; settings
        </button>
        {installPrompt && (
          <button className="menu-action" onClick={onInstall}>
            <span aria-hidden="true">⊕</span> Install TickVendor
          </button>
        )}
        <button className="menu-action danger" onClick={onSignOut}>
          <span aria-hidden="true">→</span> Sign out
        </button>
      </div>
    </details>
  );
}

function WorkspaceSelector({
  workspace,
  selectedCommunity,
  managedCommunities,
  isSuperAdmin,
  onWorkspaceChange,
  mobile = false,
}: {
  workspace: 'participant' | 'management' | 'platform';
  selectedCommunity?: WorkspaceCommunity;
  managedCommunities: WorkspaceCommunity[];
  isSuperAdmin: boolean;
  onWorkspaceChange: (workspace: 'participant' | 'management' | 'platform', communityId?: string) => void;
  mobile?: boolean;
}) {
  const value = workspace === 'management' && selectedCommunity ? selectedCommunity.id : workspace;
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const optionRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const options = [
    { id: 'participant', name: 'My Space' },
    ...managedCommunities.map(item => ({ id: item.id, name: item.name })),
    ...(isSuperAdmin ? [{ id: 'platform', name: 'Platform Admin' }] : []),
  ];
  const selectedName = options.find(item => item.id === value)?.name || 'My Space';

  useEffect(() => {
    const close = (event: MouseEvent) => { if (!rootRef.current?.contains(event.target as Node)) setOpen(false); };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  const choose = (id: string) => {
  setOpen(false);
  buttonRef.current?.focus();

  if (id === 'participant' || id === 'platform') {
    onWorkspaceChange(id);
  } else {
    onWorkspaceChange('management', id);
  }
};

  const handleTriggerKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === 'Escape') { setOpen(false); return; }
    if (['ArrowDown', 'Enter', ' '].includes(event.key)) {
      event.preventDefault();
      setOpen(true);
      window.requestAnimationFrame(() => optionRefs.current[Math.max(0, options.findIndex(item => item.id === value))]?.focus());
    }
  };

  const handleOptionKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number, id: string) => {
    if (event.key === 'Escape') { setOpen(false); buttonRef.current?.focus(); return; }
    if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); choose(id); return; }
    if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? options.length - 1 : (index + (event.key === 'ArrowDown' ? 1 : -1) + options.length) % options.length;
    optionRefs.current[next]?.focus();
  };

  return (
    <div ref={rootRef} className={`workspace-selector${mobile ? ' workspace-selector-mobile' : ''}`}>
      <span className="workspace-selector-label">Space</span>
      <button
        ref={buttonRef}
        className="space-trigger"
        type="button"
        aria-label="Select workspace"
        aria-haspopup="listbox"
        aria-expanded={open}
        title={selectedName}
        onClick={() => setOpen(!open)}
        onKeyDown={handleTriggerKeyDown}
      >
        <span className="space-trigger-value">{selectedName}</span>
        <span className="space-chevron" aria-hidden="true">▾</span>
      </button>
      {open && (
        <div className="space-menu" role="listbox" aria-label="Select workspace">
          <button
            ref={el => { optionRefs.current[0] = el; }}
            className={`space-option${value === 'participant' ? ' selected' : ''}`}
            type="button"
            role="option"
            aria-selected={value === 'participant'}
            onClick={() => choose('participant')}
            onKeyDown={event => handleOptionKeyDown(event, 0, 'participant')}
          >
            <span>My Space</span>
            {value === 'participant' && <span aria-hidden="true">✓</span>}
          </button>
          {managedCommunities.length > 0 && (
            <div className="space-menu-group" role="presentation">Manage</div>
          )}
          {managedCommunities.map((item, index) => (
            <button
              ref={el => { optionRefs.current[index + 1] = el; }}
              className={`space-option${value === item.id ? ' selected' : ''}`}
              type="button"
              role="option"
              aria-selected={value === item.id}
              key={item.id}
              onClick={() => choose(item.id)}
              onKeyDown={event => handleOptionKeyDown(event, index + 1, item.id)}
            >
              <span>{item.name}</span>
              {value === item.id && <span aria-hidden="true">✓</span>}
            </button>
          ))}
          {isSuperAdmin && (
            <button
              ref={el => { optionRefs.current[managedCommunities.length + 1] = el; }}
              className={`space-option${value === 'platform' ? ' selected' : ''}`}
              type="button"
              role="option"
              aria-selected={value === 'platform'}
              onClick={() => choose('platform')}
              onKeyDown={event => handleOptionKeyDown(event, managedCommunities.length + 1, 'platform')}
            >
              <span>Platform Admin</span>
              {value === 'platform' && <span aria-hidden="true">✓</span>}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export function AppShell({
  children,
  user,
  view,
  setView,
  installPrompt,
  onInstall,
  onSignOut,
  onProfile,
  roleItems,
  workspace,
  selectedCommunity,
  managedCommunities,
  isSuperAdmin,
  onWorkspaceChange,
}: {
  children: ReactNode;
  user: { display_name: string; email: string; role: string };
  view: string;
  setView: (view: string) => void;
  installPrompt: BeforeInstallPromptEvent | null;
  onInstall: () => void;
  onSignOut: () => void;
  onProfile: () => void;
  roleItems: NavItem[];
  workspace: 'participant' | 'management' | 'platform';
  selectedCommunity?: WorkspaceCommunity;
  managedCommunities: WorkspaceCommunity[];
  isSuperAdmin: boolean;
  onWorkspaceChange: (workspace: 'participant' | 'management' | 'platform', communityId?: string) => void;
}) {
  const [moreOpen, setMoreOpen] = useState(false);
  const sheetRef = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!moreOpen) return;
    const previous = document.activeElement as HTMLElement | null;
    sheetRef.current?.querySelector<HTMLButtonElement>('button')?.focus();
    const keyboard = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape') { setMoreOpen(false); return; }
      if (event.key !== 'Tab') return;
      const buttons = sheetRef.current?.querySelectorAll<HTMLButtonElement>('button');
      if (!buttons?.length) return;
      const first = buttons[0], last = buttons[buttons.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', keyboard);
    return () => { document.removeEventListener('keydown', keyboard); previous?.focus(); };
  }, [moreOpen]);
  const [collapsedGroups, setCollapsedGroups] = useState<string[]>(['Impact', 'Settings']);

  const go = (id: string) => {
    const target = VIEW_ALIAS[id] ?? id;
    setView(target);
    setMoreOpen(false);
  };

  const isActive = (id: string) => view === (VIEW_ALIAS[id] ?? id);

  const management = workspace === 'management' && Boolean(selectedCommunity);
  const platform = workspace === 'platform';
  const workspaceLabel = platform ? 'Platform Admin' : management ? selectedCommunity?.name : 'My Space';
  const availableItems = new Map(roleItems.map(item => [item.id, item]));

  // Mobile nav: show first 4 participant items + More, or first 3 management + More
  const mobileNavItems = platform ? roleItems.filter(item => item.id === 'platform-admin') : management ? roleItems.slice(0, 4) : participantNav.slice(0, 4);
  const moreItems = platform ? [] : management ? roleItems.slice(4) : [...participantNav.slice(4), ...secondaryNav];

  return (
    <div className="app-shell">
      <a className="skip" href="#main">Skip to main content</a>

      {/* Header */}
      <header className="app-header">
        <a className="brand" href="#home" onClick={e => { e.preventDefault(); go('home'); }}>
          <span className="brand-logo" aria-hidden="true">TV</span>
          <span>TickVendor</span>
        </a>
        <div className="header-context">
          <span className="workspace-label" title={workspaceLabel}>{workspaceLabel}</span>
          <button
            className="notification-button"
            aria-label="Notifications"
            onClick={() => go('notifications')}
          >
            <span aria-hidden="true">🔔</span>
          </button>
          <AccountMenu
            user={user}
            installPrompt={installPrompt}
            onInstall={onInstall}
            onSignOut={onSignOut}
            onProfile={onProfile}
          />
        </div>
      </header>

      {/* Mobile workspace selector */}
      <WorkspaceSelector
        workspace={workspace}
        selectedCommunity={selectedCommunity}
        managedCommunities={managedCommunities}
        isSuperAdmin={isSuperAdmin}
        onWorkspaceChange={onWorkspaceChange}
        mobile
      />

      {/* Main layout */}
      <div className="app-layout">
        {/* Sidebar */}
        <aside className="sidebar" aria-label="Workspace navigation">
          <WorkspaceSelector
            workspace={workspace}
            selectedCommunity={selectedCommunity}
            managedCommunities={managedCommunities}
            isSuperAdmin={isSuperAdmin}
            onWorkspaceChange={onWorkspaceChange}
          />
          <nav>
            {!management && !platform && (
              <>
                {participantNav.map(item => (
                  <button
                    key={item.id}
                    className={isActive(item.id) ? 'active' : ''}
                    onClick={() => go(item.id)}
                    aria-current={isActive(item.id) ? 'page' : undefined}
                  >
                    <span aria-hidden="true">{item.icon}</span>
                    <span>{item.label}</span>
                  </button>
                ))}
                <p className="sidebar-title">More</p>
                {secondaryNav.map(item => (
                  <button
                    key={item.id}
                    className={isActive(item.id) ? 'active' : ''}
                    onClick={() => go(item.id)}
                    aria-current={isActive(item.id) ? 'page' : undefined}
                  >
                    <span aria-hidden="true">{item.icon}</span>
                    <span>{item.label}</span>
                  </button>
                ))}
              </>
            )}
            {platform && (
              <div className="management-nav-group">
                <p className="sidebar-title">Platform</p>
                <button className={isActive('platform-admin') ? 'active' : ''} onClick={() => go('platform-admin')} aria-current={isActive('platform-admin') ? 'page' : undefined}>
                  <span aria-hidden="true">⚙</span>
                  <span>Platform Admin</span>
                </button>
              </div>
            )}
            {management && managementGroups.map(group => {
              const items = group.ids.map(id => availableItems.get(id)).filter((item): item is NavItem => Boolean(item));
              const expanded = group.ids.some(id => isActive(id)) || !collapsedGroups.includes(group.label);
              if (!items.length) return null;
              return (
                <div className="management-nav-group" key={group.label}>
                  {group.ids.length === 1 ? (
                    <p className="sidebar-title">{group.label}</p>
                  ) : (
                    <button
                      className="management-group-toggle"
                      type="button"
                      aria-expanded={expanded}
                      onClick={() => setCollapsedGroups(current =>
                        current.includes(group.label)
                          ? current.filter(l => l !== group.label)
                          : [...current, group.label]
                      )}
                    >
                      <span>{group.label}</span>
                      <span aria-hidden="true">{expanded ? '▴' : '▾'}</span>
                    </button>
                  )}
                  {(group.ids.length === 1 || expanded) && items.map(item => (
                    <button
                      key={item.id}
                      className={isActive(item.id) ? 'active' : ''}
                      onClick={() => go(item.id)}
                      aria-current={isActive(item.id) ? 'page' : undefined}
                    >
                      <span aria-hidden="true">{item.icon}</span>
                      <span>{item.label}</span>
                    </button>
                  ))}
                </div>
              );
            })}
          </nav>
        </aside>

        {/* Main content */}
        <div className="app-main">{children}</div>
      </div>

      {/* Mobile bottom nav */}
      <nav className="mobile-bottom-nav" aria-label="Primary navigation">
        {mobileNavItems.map(item => (
          <button
            key={item.id}
            className={isActive(item.id) ? 'active' : ''}
            onClick={() => go(item.id)}
            aria-current={isActive(item.id) ? 'page' : undefined}
          >
            <span aria-hidden="true">{item.icon}</span>
            <span>{item.label}</span>
          </button>
        ))}
        <button
          className={moreOpen ? 'active' : ''}
          onClick={() => setMoreOpen(!moreOpen)}
          aria-expanded={moreOpen}
          aria-haspopup="dialog"
        >
          <span aria-hidden="true">•••</span>
          <span>More</span>
        </button>
      </nav>

      {/* Mobile more sheet */}
      {moreOpen && (
        <div className="mobile-sheet-backdrop" onClick={() => setMoreOpen(false)}>
          <section
            ref={sheetRef}
            className="mobile-sheet"
            role="dialog"
            aria-modal="true"
            aria-labelledby="more-sheet-title"
            onClick={e => e.stopPropagation()}
          >
            <div className="sheet-handle" aria-hidden="true" />
            <h2 id="more-sheet-title">More</h2>
            <button onClick={() => setMoreOpen(false)}>Close navigation</button>
            {moreItems.map(item => (
              <button key={item.id} onClick={() => go(item.id)} className={isActive(item.id) ? 'active' : ''}>
                <span aria-hidden="true">{item.icon}</span>
                <span>{item.label}</span>
              </button>
            ))}
            <button onClick={() => { onProfile(); setMoreOpen(false); }}>
              <span aria-hidden="true">◉</span>
              <span>Profile &amp; settings</span>
            </button>
          </section>
        </div>
      )}
    </div>
  );
}
