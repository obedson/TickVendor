# TickEven Build Status

## Recovery Audit — 2026-08-31

- Recovery checkpoint: Git initialized; pre-repair state committed as `f8206db`.
- Valid and preserved: authoritative documents, the small database engine/session/Base
  scaffold, and the project virtual environment.
- Corrupt/incomplete at takeover: `src/config.py` imported a nonexistent
  `src.config.tickeven_settings` package; `src/main.py` had no FastAPI application;
  no model package, API routes, migrations, tests, dependency manifest, `.env.example`,
  logging, error envelope, or validation architecture existed. The local SQLite database
  contained no schema.
- Environment: `venv/Scripts/python.exe` is Python 3.13.14 and imports the declared
  foundation dependencies. Dependencies are now declared in `pyproject.toml`.
- Architecture finding: the takeover state did not match the specification beyond a
  minimal SQLAlchemy foundation. `src/database.py` is now restricted to engine, session,
  Base, foreign-key enforcement, and initialization helpers; models are modular under
  `src/models/`.
- Verification: automated tests pass (16), Ruff passes, source compilation passes,
  SQLite foreign keys are enabled, and `/health` plus standardized validation errors work.
- Remaining warning: FastAPI's current TestClient emits an upstream Starlette/httpx
  deprecation warning; it does not fail tests.

## Implementation Checklist — Grouped by Dependency-Aware Subsystem

### Foundation / Architecture
- [x] Project structure and configuration (venv, validated settings, declared packages)
- [x] Application structure establishment (FastAPI factory, health endpoint, model registry)
- [x] Initial 31-table model schema and Alembic migration (clean upgrade/check verified; 60 foreign keys, 88 indexes including SQLite auto-indexes)
- [ ] API structure definition
- [ ] Authentication architecture (User identity schema exists; password hashing, verification, reset, and sessions pending)
- [ ] Authorization architecture (RBAC: Guest, Participant/Member, Organizer, Community Admin, Super Admin)
- [x] User/Profile schema: UUIDs, email/password hash, platform role, verification/activity state, name, username, photo, bio, location, interests, skills, privacy
- [x] Organization schema (owner, identity, verification, active state)
- [x] Community/Membership schema (organization tenancy, multi-community users, scoped roles/status, uniqueness)
- [x] Configuration/environment files (`Settings`, `.env.example`, deployment-secret guard)
- [x] Error handling architecture (stable validation/internal-error envelopes)
- [x] Logging architecture (central standard-library configuration; sensitive data policy pending security pass)
- [x] Validation architecture (Pydantic settings and FastAPI request validation)
- [ ] Shared types/interfaces

### Events Subsystem
- [x] Event/Venue/EventStaff schema (publishing states, physical/online/hybrid location, attendance configuration, scoped staff roles)
- [ ] Event creation (multi-step form: basic info, date/time, location, attendance settings)
- [ ] Event editing
- [ ] Event publishing/unpublishing
- [ ] Event discovery (browse, search, filter, sort)
- [ ] Event filtering by category, location, price, etc.
- [ ] Event sorting
- [ ] Nearby events support
- [ ] Upcoming events view
- [ ] Free vs paid events filtering
- [ ] Event categories (configurable: technology, education, business, community, agriculture, entertainment, sports, training, conference, workshop, networking, volunteer, fundraising)
- [ ] Event tags
- [ ] Organizer profiles
- [ ] Event images/cover photos

### Ticketing Subsystem
- [x] TicketType/Ticket/Order/Payment schema (inventory constraints, secure public/QR IDs, lifecycle states, provider references, idempotency)
- [ ] Ticket types creation (free, regular, VIP, student, early bird, group, sponsor, volunteer)
- [ ] Ticket type properties: name, description, price, quantity, sales start/end, visibility, max per user
- [ ] Ticket generation: unique ticket ID, QR code, attendee info, event info, ticket type, status
- [ ] Ticket statuses: reserved, pending payment, paid, active, used, cancelled, expired
- [ ] Duplicate ticket use prevention (atomic validation)
- [ ] Order creation and management
- [ ] Payment integration architecture (paystack, flutterwave, stripe — server-side verification, webhooks)
- [ ] Payment states: pending, successful, failed, cancelled, refunded
- [ ] Ticket issuance upon payment confirmation
- [ ] Ticket activation flow
- [ ] Refund processing
- [ ] Ticket cancellation

### Attendance Subsystem
- [x] Attendance/Verification/PeerConfirmation schema (independent attendance, layered signals, confidence/review fields, duplicate prevention)
- [ ] Attendance record creation (separate from ticket purchase)
- [ ] Attendance states: not checked in, checked in, GPS verified, QR verified, peer verified, organizer verified, rejected
- [ ] Geofenced attendance: latitude, longitude, radius, start/end time
- [ ] GPS/geolocation verification (browser/device, Haversine distance calculation)
- [ ] QR code attendance check-in
- [ ] Manual/ organizer verification
- [ ] Peer confirmation system
- [ ] Attendance verification confidence/status calculation from layered signals
- [ ] Anti-abuse: duplicate QR scans, multiple check-ins, check-in outside event time, location outside radius, suspicious peer confirmations, reciprocal confirmations, impossible location changes
- [ ] GPS fallback methods (QR, organizer verification)
- [ ] Location permission handling (denied, timeout, unavailable, low accuracy)
- [ ] Explanation messaging for location requests

### Activities / Tasks Subsystem
- [x] Task/TaskAssignment/TaskSubmission schema (priority, lifecycle, evidence, verification, assignment uniqueness)
- [x] Activity/Contribution schema (five engagement dimensions, monetary/non-monetary types, verification state)
- [ ] Task creation (title, description, assignee, due date, priority, impact point reward, attachments, verification requirement)
- [ ] Task assignment to participants
- [ ] Task states: assigned, accepted, in progress, submitted, verified, rejected, overdue
- [ ] Task submission with evidence
- [ ] Task verification by organizer/admin
- [ ] Impact Points awarded after verification (where configured)
- [ ] Community activities beyond attendance/tasks: volunteer work, mentoring, community service, speaking, training, organizing, content contribution, resource donation, leadership activities
- [ ] Activity types: monetary, equipment, materials, volunteer time, services, resources
- [ ] Contribution tracking with: amount, currency, purpose, date, payment/reference ID, verification status
- [ ] Configurable contribution bands (₦1-999 → 2pts, ₦1000-4999 → 5pts, ₦5000-9999 → 10pts, ₦10000+ → 15pts)
- [ ] Caps to prevent financial contributions from overwhelming participation-based achievements

### Impact Point / Reward Engine
- [x] ImpactTransaction schema (auditable status, source references, reversals, unique idempotency key)
- [ ] Centralized rules engine for Impact Points
- [ ] Point values: attendance → +10, task completion → +20, volunteer activity → +15, peer verification → +2, leadership activity → +30, contribution → configurable, special achievement → configurable
- [ ] Never hard-code point values into individual components
- [ ] Activity/reward engine: user, source activity, points, timestamp, organization/community, event/task reference, reason, status
- [ ] Immutable-ish transaction history for auditability
- [ ] Duplicate reward prevention (idempotency keys / unique reward references)
- [ ] Prevention: duplicate attendance rewards, duplicate task rewards, duplicate contribution rewards, repeated exploitation

### Multi-Dimensional Engagement
- [ ] Participation dimension: attendance/events tracking
- [ ] Execution dimension: tasks completed tracking
- [ ] Contribution dimension: financial and non-financial contributions tracking
- [ ] Service dimension: helping/community activities tracking
- [ ] Leadership dimension: organizing/facilitating/leading tracking
- [ ] Member profile shows all four dimensions

### Milestone Engine
- [x] Milestone/MilestoneRequirement schema (community-scoped configurable metrics, operators, thresholds, rewards)
- [ ] Configurable milestones
- [ ] Milestone requirements: impact points, attendance count, task count, contribution count, service activities, leadership activities, peer confirmations, event participation, consecutive activities
- [ ] Example: Community Builder — 300 Impact Points, 10 verified attendances, 5 completed tasks, 1 community contribution
- [ ] Automatic milestone award when requirements satisfied
- [ ] Milestone requirements should be configurable via admin (not hard-coded)

### Rank System
- [x] Rank/RankRequirement schema (community-scoped points, ordered progression, activity/milestone/badge references)
- [ ] Configurable ranks with name, description, icon, minimum points, required activities, required milestones, required badges
- [ ] Example rank thresholds: Starter (0–49), Active Member (50–149), Contributor (150–299), Community Builder (300–499), Community Leader (500–799), Impact Champion (800+)
- [ ] Rank qualification requirements (not just minimum points — may require specific activities/milestones/badges)
- [ ] Administrators define rank configuration without code changes
- [ ] Progress toward next rank display on profile

### Badge System
- [x] Badge/BadgeAward schema (configurable JSON requirements, visibility/rewards, idempotent award and revocation history)
- [ ] Flexible badge engine
- [ ] Badge properties: name, description, icon, category, requirements, reward, visibility
- [ ] Example badges: First Step (first verified event attendance), Regular (attend 5 events), Consistent (attend 10 events), Task Starter (complete first task), Doer (complete 10 tasks), Community Helper (help 5 members), Facilitator (organize first event), Community Builder (complete defined community requirements)
- [ ] Automatic badge award when conditions satisfied
- [ ] Admin-definable badge rules (achievement rule builder)

### Achievement Rule Builder
- [x] AchievementRule schema (versioned condition tree and reward definition for extensible operators)
- [ ] Admin interface for defining achievement logic without modifying code
- [ ] Supported logical operators: AND, OR, >=, <=, =, Count, Sum, Streak, Unique event count
- [ ] Example achievement: Community Champion — attendance >= 20, tasks >= 10, peer confirmations >= 10, leadership activities >= 3, Impact Points >= 500, reward: badge + 50 Impact Points
- [ ] Additional rule types designed for future extensibility

### Streaks (Optional)
- [ ] Optional engagement streaks: 3-event attendance streak, 5-task completion streak, 4-week activity streak
- [ ] Administrators can enable/disable streaks
- [ ] Avoid overly game-like experience

### Member Journey / Profile
- [ ] Visual milestone timeline: joined community → first event → first badge → completed 5 tasks → contributor → helped 10 members → community builder → community leader
- [ ] Member profile contains: profile photo, name, username, rank, impact points, progress toward next rank, badges, milestones, events attended, tasks completed, contributions, service activities, leadership activities, engagement dimensions, achievement timeline
- [ ] Privacy controls: users control what parts of profile are publicly visible

### Leaderboards (Optional)
- [ ] Optional leaderboard types: overall, attendance, tasks, community service, leadership, organization, event
- [ ] Administrators can disable leaderboards
- [ ] Avoid making monetary contributions the primary public leaderboard metric

### Event Engagement
- [ ] Per-event engagement summary: tickets (total), checked in (count), verified (count), tasks (count), contributions (amount/badges earned), impact points generated

### Organizer Dashboard
- [ ] Upcoming events, total events, ticket sales, revenue, registrations, attendance, verification status, pending tasks, contributions, engagement, top participants, achievement distribution

### Community Dashboard
- [ ] Total members, active members, events, attendance, tasks, contributions, engagement, rank distribution, badge distribution, participation trends, member retention/engagement

### Notifications
- [x] Notification schema (in-app payload and read state)
- [ ] In-app notifications only (no external delivery required initially)
- [ ] Notification preferences per user
- [ ] Example notifications: "Your event starts tomorrow", "Attendance is now open", "Your ticket has been confirmed", "Your task was verified", "You earned a new badge", "You're 20 Impact Points away from your next milestone", "You have attendance confirmations waiting", "Congratulations! You reached Community Builder"
- [ ] Email notification architecture (framework ready, test adapters)
- [ ] Push notification architecture (framework ready)

### Search
- [ ] Global search supporting: events, organizers, communities, members (where privacy permits), tasks (where authorized)
- [ ] Appropriate database indexes

### Event Categories
- [ ] Configurable categories (technology, education, business, community, agriculture, entertainment, sports, training, conference, workshop, networking, volunteer, fundraising)
- [ ] Administrators can add/edit categories

### Community System
- [ ] Communities/organizations with: name, logo, description, members, administrators, events, tasks, activities, contribution records, rank configuration, badge configuration, milestones
- [ ] Users can belong to multiple communities
- [ ] Logical isolation of community data

### Event Organizer Profile
- [ ] Organizer pages showing: name, logo/profile, description, events (past and upcoming), basic credibility/verification status

### Admin Audit Log
- [x] AuditLog schema (actor/community/action/target/timestamp/metadata; append-only design)
- [ ] Audit log tracking: event creation/changes, ticket changes, attendance override, task verification, contribution verification, point adjustments, badge awards/revocations, rank changes, user role changes
- [ ] Each entry: actor, action, target, timestamp, relevant metadata

### Manual Point Adjustments
- [ ] Authorized administrators adjust Impact Points
- [ ] Every adjustment requires: amount, reason, administrator, timestamp
- [ ] Never silently modify a user's score

### Data Model
- [ ] Normalized database architecture around entities: User, Profile, Organization, Community, Membership, Event, Venue, TicketType, Ticket, Order, Payment, Attendance, AttendanceVerification, PeerConfirmation, Task, TaskAssignment, TaskSubmission, Contribution, Activity, ImpactTransaction, Milestone, MilestoneRequirement, Badge, BadgeAward, Rank, RankRequirement, AchievementRule, Notification, AuditLog, Leaderboard, EventStaff
- [ ] UUIDs or secure unique IDs
- [ ] Created and updated timestamps
- [ ] Soft deletion where appropriate
- [ ] Proper indexes, constraints
- [ ] Do not expose internal database IDs unnecessarily

### Security
- [ ] Input validation
- [ ] Output encoding
- [ ] Authorization checks
- [ ] RBAC implementation
- [ ] Rate limiting
- [ ] CSRF protection where applicable
- [ ] Secure authentication
- [ ] Password hashing (BCRYPT_ROUNDS: 12 default)
- [ ] Secure session handling
- [ ] File upload validation
- [ ] Image validation
- [ ] Payment webhook validation
- [ ] API validation
- [ ] Audit logging
- [ ] Abuse prevention
- [ ] Never rely exclusively on frontend validation
- [ ] Every sensitive operation must be authorized server-side

### Privacy
- [ ] Location information: requested only when needed, used only for attendance verification, not continuously tracked, minimized in storage, protected from unauthorized access
- [ ] Clear consent messaging
- [ ] Users control profile visibility
- [ ] Do not expose private member information through public APIs

### Geolocation Implementation
- [ ] Browser/device geolocation where supported
- [ ] Haversine distance calculation
- [ ] GPS accuracy consideration
- [ ] Permission denied handling
- [ ] Timeout handling
- [ ] Location unavailable handling
- [ ] Low accuracy handling
- [ ] Browser restrictions handling
- [ ] Fallback methods: QR, organizer verification
- [ ] Do not prevent legitimate attendance because GPS fails

### Offline/Low Connectivity
- [ ] Cache event/ticket data
- [ ] Allow ticket QR to load from cached data
- [ ] Support PWA installation
- [ ] Queue non-sensitive actions where appropriate
- [ ] Retry failed requests safely
- [ ] Avoid large bundles
- [ ] Do not cache sensitive information insecurely

### PWA
- [ ] Progressive Web App: manifest, service worker, offline shell, app icons, install prompt, responsive mobile experience