# TICK EVEN — COMPLETE PRODUCT & ENGINEERING SPECIFICATION

## AI CODING AGENT MASTER PROMPT

You are a senior product architect, UX engineer, full-stack software engineer, security engineer, and DevOps engineer.

Build a complete, production-ready web application called **TickVendor**.

**Brand:** TickVendor
**Domain:** tickvendor.com
**Core positioning:** Ticketing + Events + Community Engagement
**Core idea:** Discover. Attend. Participate. Achieve.

TickVendor is a lightweight event ticketing, event management, attendance verification, community engagement, contribution, milestone, rank, and badge platform.

The platform must be designed as **one coherent ecosystem**, not as separate applications.

---

# 1. PRODUCT VISION

TickVendor allows people and organizations to:

* Discover events
* Create and manage events
* Create free and paid tickets
* Register attendees
* Issue digital tickets
* Validate tickets using QR codes
* Track event attendance
* Verify attendance using geofencing and peer confirmation
* Assign and complete tasks
* Record community/service activities
* Record monetary and non-monetary contributions
* Earn Impact Points
* Reach milestones
* Earn badges
* Progress through ranks
* Build a verifiable participation history
* Manage communities and members
* Measure engagement and impact

The platform should work for:

* Conferences
* Workshops
* Meetups
* Professional communities
* NGOs
* Volunteer organizations
* Associations
* Clubs
* Educational communities
* Youth organizations
* Social/community initiatives
* Corporate events
* Training programs
* Fundraising events
* Recurring community activities

---

# 2. BRAND CONCEPT

TickVendor represents:

**Tick + Events**

and can be interpreted as:

**Tick Events / Ticketing Events / Tickets + Events**

The product philosophy is:

> **Every action counts.**

The core engagement loop is:

**Discover → Ticket → Attend → Verify → Participate → Contribute → Earn Impact → Reach Milestone → Gain Recognition**

Do not allow the ticketing functionality and engagement functionality to feel disconnected.

A ticket should be capable of becoming the beginning of a participant's engagement record.

---

# 3. PRODUCT TAGLINE

Primary:

> **Discover. Attend. Participate. Achieve.**

Secondary:

> **Every Action Counts.**

Use the primary tagline prominently on the marketing/home experience.

---

# 4. DESIGN PRINCIPLES

The application must be:

* Minimal
* Lightweight
* Fast
* Mobile-first
* Responsive
* Accessible
* Easy for non-technical users
* Intuitive
* Visually clean
* Low cognitive load
* PWA-friendly
* Optimized for low-bandwidth environments

Avoid unnecessary animations, excessive dashboards, complicated forms, and feature overload.

A user should be able to:

1. Find an event
2. Get a ticket
3. Attend
4. Check in
5. Verify participation
6. See their progress

with minimal interaction.

---

# 5. USER ROLES

Implement role-based access control.

Roles should include:

### Guest

Can:

* Browse public events
* Search events
* View event details
* View organizers
* Register/login

### Participant / Member

Can:

* Manage profile
* Discover events
* Obtain tickets
* View tickets
* Present QR tickets
* Check into events
* Confirm attendance of eligible participants
* View tasks
* Complete tasks
* View contributions
* View Impact Points
* View milestones
* View ranks
* View badges
* View activity history
* View notifications

### Organizer

Can:

* Create events
* Edit events
* Publish/unpublish events
* Create ticket types
* Manage ticket inventory
* Manage attendees
* Validate tickets
* Start/stop attendance
* Configure geofencing
* Configure peer verification
* Create tasks
* Assign tasks
* Verify task completion
* Record contributions
* Create achievements
* View analytics

### Community Administrator

Can additionally:

* Create/manage communities
* Manage members
* Configure engagement rules
* Configure rank systems
* Configure badge systems
* Configure milestones
* Configure point rules
* Manage community-wide activities
* View community analytics

### Super Administrator

Full platform access.

---

# 6. AUTHENTICATION

Implement secure authentication.

Support:

* Email/password
* Email verification
* Password reset
* Secure session management
* Optional OAuth/social authentication architecture
* Role-based authorization
* Profile completion

Profile should support:

* Name
* Username
* Profile photo
* Bio
* Location
* Interests
* Skills
* Organization/community memberships

Do not require excessive personal information.

---

# 7. EVENT DISCOVERY

Create a clean event discovery experience.

Users should be able to:

* Browse events
* Search events
* Filter events
* Sort events
* View nearby events
* View upcoming events
* View free events
* View paid events
* View categories
* Save/bookmark events

Event cards should show:

* Event image
* Event name
* Date
* Time
* Location
* Organizer
* Starting ticket price
* Availability
* Event category

---

# 8. EVENT CREATION

Organizers should be able to create events using a simple multi-step form.

Fields:

### Basic Information

* Event title
* Description
* Cover image
* Category
* Tags
* Organizer
* Contact information

### Date & Time

* Start date
* Start time
* End date
* End time
* Time zone

### Location

Support:

* Physical location
* Online event
* Hybrid event

For physical events:

* Venue name
* Address
* Map location
* Latitude
* Longitude

### Attendance Settings

Organizer can configure:

* Geofence enabled/disabled
* Geofence radius
* Check-in opening time
* Check-in closing time
* Peer confirmation enabled/disabled
* Number of confirmations required
* Organizer verification
* QR attendance

---

# 9. TICKETING SYSTEM

Build a complete digital ticketing system.

Organizers can create multiple ticket types:

Examples:

* Free
* Regular
* VIP
* Student
* Early Bird
* Group
* Sponsor
* Volunteer

Each ticket type supports:

* Name
* Description
* Price
* Quantity
* Sales start
* Sales end
* Ticket visibility
* Maximum per user

Tickets should generate:

* Unique ticket ID
* Unique QR code
* Attendee information
* Event information
* Ticket type
* Status

Ticket statuses:

* Reserved
* Pending payment
* Paid
* Active
* Used
* Cancelled
* Refunded
* Expired

Prevent duplicate ticket use.

---

# 10. PAYMENT ARCHITECTURE

Build the system so that payment providers can be integrated cleanly.

V1 requires Paystack. The architecture may support additional providers later:

* Paystack — required for V1
* Flutterwave — optional/future
* Stripe — optional/future

For V1, production configuration, documentation, and release verification target Paystack.

Do not store raw card information.

Payment states should include:

* Pending
* Successful
* Failed
* Cancelled
* Refunded

Use webhook verification.

Never trust client-side payment confirmation.

---

# 11. DIGITAL WALLET / TICKET AREA

Create a simple **My Tickets** section.

Users should see:

* Upcoming tickets
* Used tickets
* Cancelled tickets

Each ticket should display:

* Event
* Date
* Venue
* Ticket type
* QR code
* Ticket status

Allow users to open the ticket full-screen for entrance validation.

---

# 12. QR TICKET VALIDATION

Organizers/staff should have a QR scanner.

Scanning should:

1. Read QR
2. Validate ticket
3. Check event
4. Check ticket status
5. Prevent duplicate use
6. Record scan time
7. Record validating staff member
8. Mark ticket as used where appropriate

Display clear results:

### Valid

✓ Ticket Valid

### Already Used

⚠ Ticket Already Used

### Invalid

✕ Invalid Ticket

### Wrong Event

✕ Ticket Not Valid For This Event

---

# 13. EVENT ATTENDANCE ENGINE

Attendance must be independent from ticket purchase.

A person may:

* Have a ticket but not attend
* Attend through an invitation
* Attend through organizer registration
* Attend as a volunteer
* Attend through a free registration

Attendance records must therefore be separate entities.

Attendance states:

* Not checked in
* Checked in
* GPS verified
* QR verified
* Peer verified
* Organizer verified
* Rejected

---

# 14. GEO-FENCED ATTENDANCE

Implement geofenced attendance.

Organizer configures:

* Latitude
* Longitude
* Radius
* Start time
* End time

Example:

Event location:

Cafe One

Radius:

100 metres

During attendance:

The system requests browser/mobile geolocation permission.

Verify whether the participant is inside the permitted radius.

If valid:

> You are within the attendance zone.

Allow:

**CHECK IN**

Store:

* Event ID
* User ID
* Timestamp
* Verification method
* Approximate coordinates required for verification
* Attendance status

Do not continuously track users.

Location should only be requested when necessary for attendance verification.

Clearly explain why location is being requested.

---

# 15. QR + GEO ATTENDANCE

Support multiple attendance mechanisms:

### Method 1

GPS/geofence

### Method 2

QR code

### Method 3

Organizer/manual verification

### Method 4

Peer confirmation

Organizers can configure which methods are required.

Example:

**GPS + Peer Confirmation**

or:

**QR only**

or:

**Organizer verification**

---

# 16. PEER ATTENDANCE CONFIRMATION

Implement the peer confirmation system as a core feature.

After an event, eligible attendees may be asked to confirm other attendees.

Example:

> **Who did you see at today's event?**

Display a small randomized selection of eligible attendees.

Each person can answer:

**Yes, I saw them**

or

**I can't confirm**

Do not allow unlimited confirmation.

Configurable rules:

* Maximum confirmations per attendee
* Minimum confirmations required
* Confirmation deadline
* Eligibility requirements
* Organizer override

Only attendees with valid attendance status should be eligible to confirm others.

---

# 17. ATTENDANCE VERIFICATION LEVELS

Use layered verification.

Possible states:

### GPS Verified

Location requirement satisfied.

### QR Verified

Ticket/attendance QR successfully scanned.

### Peer Verified

Required number of peers confirmed attendance.

### Organizer Verified

Authorized organizer confirmed attendance.

The system should calculate a final attendance confidence/status from these signals.

Do not expose overly technical fraud information to ordinary users.

---

# 18. ANTI-FRAUD RULES

Implement basic abuse prevention.

Detect/flag:

* Duplicate QR scans
* Multiple check-ins
* Check-in outside event time
* Location outside allowed radius
* Suspicious repeated peer confirmations
* Excessive reciprocal confirmations
* Impossible location changes
* Repeated suspicious activity

Do not automatically punish users solely based on one suspicious signal.

Flag suspicious activity for organizer review.

---

# 19. TASK MANAGEMENT

Create a lightweight task system.

Organizers/admins can create:

* Task title
* Description
* Assignee
* Due date
* Priority
* Impact Point reward
* Attachments
* Verification requirement

Participants can:

* View tasks
* Accept task
* Mark complete
* Submit evidence
* View status

Task states:

* Assigned
* Accepted
* In progress
* Submitted
* Verified
* Rejected
* Overdue

Impact Points are awarded only after verification where configured.

---

# 20. COMMUNITY ACTIVITIES

Allow administrators to define activities beyond attendance and tasks.

Examples:

* Volunteer work
* Mentoring
* Community service
* Speaking
* Training
* Organizing
* Referrals
* Content contribution
* Resource donation
* Leadership activities

Activities can generate Impact Points and achievements.

---

# 21. CONTRIBUTION SYSTEM

Implement contribution tracking.

Contribution types:

* Monetary
* Equipment
* Materials
* Volunteer time
* Services
* Resources

For monetary contributions:

* Amount
* Currency
* Purpose
* Date
* Payment/reference ID
* Verification status

Do not make money the dominant determinant of rank.

Use configurable contribution bands.

Example:

₦1–₦999 → 2 points

₦1,000–₦4,999 → 5 points

₦5,000–₦9,999 → 10 points

₦10,000+ → 15 points

Administrators must be able to change these rules.

Implement configurable caps to prevent financial contributions from overwhelming participation-based achievements.

---

# 22. IMPACT POINT SYSTEM

Create a centralized rules engine.

Every qualifying activity can produce Impact Points.

Examples:

Attendance → +10

Task completion → +20

Volunteer activity → +15

Peer verification → +2

Leadership activity → +30

Contribution → configurable

Special achievement → configurable

Never hard-code point values into individual components.

Create an activity/reward engine.

Every awarded point should have:

* User
* Source activity
* Points
* Timestamp
* Organization/community
* Event/task reference where applicable
* Reason
* Status

Maintain an immutable-ish transaction history for auditability.

---

# 23. PREVENT DOUBLE REWARDING

The reward engine must prevent:

* Duplicate attendance rewards
* Duplicate task rewards
* Duplicate contribution rewards
* Repeated exploitation of the same activity

Every reward-producing activity should have a unique reward reference/idempotency key.

---

# 24. MULTI-DIMENSION ENGAGEMENT

Do not rely only on one global score.

Track:

### Participation

Attendance/events

### Execution

Tasks completed

### Contribution

Financial and non-financial contributions

### Service

Helping/community activities

### Leadership

Organizing/facilitating/leading

Show these dimensions on the member profile.

---

# 25. MILESTONE ENGINE

Create configurable milestones.

A milestone can depend on:

* Impact Points
* Attendance count
* Task count
* Contribution count
* Service activities
* Leadership activities
* Peer confirmations
* Event participation
* Consecutive activities

Example:

### Community Builder

Requirements:

* 300 Impact Points
* 10 verified attendances
* 5 completed tasks
* 1 community contribution

When requirements are satisfied:

Automatically award milestone.

---

# 26. RANK SYSTEM

Create configurable ranks.

Example:

### Starter

0–49

### Active Member

50–149

### Contributor

150–299

### Community Builder

300–499

### Community Leader

500–799

### Impact Champion

800+

But ranks may also contain qualification requirements.

Administrators can define:

* Rank name
* Description
* Icon
* Minimum points
* Required activities
* Required milestones
* Required badges

Do not make ranks hard-coded.

---

# 27. BADGE SYSTEM

Create a flexible badge engine.

Badge properties:

* Name
* Description
* Icon
* Category
* Requirements
* Reward
* Visibility

Example badges:

### First Step

First verified event attendance.

### Regular

Attend 5 events.

### Consistent

Attend 10 events.

### Task Starter

Complete first task.

### Doer

Complete 10 tasks.

### Community Helper

Help 5 members.

### Facilitator

Organize first event.

### Community Builder

Complete defined community requirements.

Badges should be automatically awarded when conditions are satisfied.

---

# 28. ACHIEVEMENT RULE BUILDER

Create an admin interface where administrators can define achievement logic without modifying code.

Example:

Achievement:

**Community Champion**

Conditions:

Attendance >= 20

Tasks >= 10

Peer Confirmations >= 10

Leadership Activities >= 3

Impact Points >= 500

Reward:

Badge + 50 Impact Points

The rules engine should support logical operators such as:

* AND
* OR
* > =
* <=
* =
* Count
* Sum
* Streak
* Unique event count

Design the underlying architecture so additional rule types can be added later.

---

# 29. STREAKS

Support optional engagement streaks.

Examples:

* 3-event attendance streak
* 5-task completion streak
* 4-week activity streak

Administrators should be able to enable/disable streaks.

Avoid making the experience overly game-like.

---

# 30. MEMBER JOURNEY

Create a visual milestone timeline.

Example:

Joined Community

↓

First Event

↓

First Badge

↓

Completed 5 Tasks

↓

Contributor

↓

Helped 10 Members

↓

Community Builder

↓

Community Leader

This should show the member's progress and achievements.

---

# 31. MEMBER PROFILE

Profile should contain:

* Profile photo
* Name
* Username
* Rank
* Impact Points
* Progress toward next rank
* Badges
* Milestones
* Events attended
* Tasks completed
* Contributions
* Service activities
* Leadership activities
* Engagement dimensions
* Achievement timeline

Allow privacy controls.

Users should be able to control what parts of their profile are publicly visible.

---

# 32. LEADERBOARD

Implement optional leaderboards.

Leaderboard types:

* Overall
* Attendance
* Tasks
* Community service
* Leadership
* Organization
* Event

Allow administrators to disable leaderboards.

Avoid making monetary contributions the primary public leaderboard metric.

---

# 33. EVENT ENGAGEMENT

Each event should have its own engagement summary.

Example:

### Event

Community Meetup

Tickets:

250

Checked in:

187

Verified:

175

Tasks:

12

Contributions:

₦X

Badges earned:

24

Impact Points generated:

2,430

This allows organizers to understand event engagement.

---

# 34. ORGANIZER DASHBOARD

Dashboard should show:

* Upcoming events
* Total events
* Ticket sales
* Revenue
* Registrations
* Attendance
* Verification status
* Pending tasks
* Contributions
* Engagement
* Top participants
* Achievement distribution

Use lightweight charts only where they improve understanding.

---

# 35. COMMUNITY DASHBOARD

Community administrators should see:

* Total members
* Active members
* Events
* Attendance
* Tasks
* Contributions
* Engagement
* Rank distribution
* Badge distribution
* Participation trends
* Member retention/engagement

---

# 36. NOTIFICATIONS

Implement useful notifications only.

Examples:

> Your event starts tomorrow.

> Attendance is now open.

> Your ticket has been confirmed.

> Your task was verified.

> You earned a new badge.

> You're 20 Impact Points away from your next milestone.

> You have attendance confirmations waiting.

> Congratulations! You reached Community Builder.

Support:

* In-app notifications
* Email notification architecture
* Push notification architecture

Allow notification preferences.

---

# 37. SEARCH

Global search should support:

* Events
* Organizers
* Communities
* Members where privacy permits
* Tasks where authorized

Use appropriate indexes.

---

# 38. EVENT CATEGORIES

Allow configurable categories such as:

* Technology
* Education
* Business
* Community
* Agriculture
* Entertainment
* Sports
* Training
* Conference
* Workshop
* Networking
* Volunteer
* Fundraising

Administrators can add/edit categories.

---

# 39. COMMUNITY SYSTEM

Implement communities/organizations.

A community can have:

* Name
* Logo
* Description
* Members
* Administrators
* Events
* Tasks
* Activities
* Contribution records
* Rank configuration
* Badge configuration
* Milestones

A user can belong to multiple communities.

Keep community data logically isolated.

---

# 40. EVENT ORGANIZER PROFILE

Organizer pages should show:

* Name
* Logo/profile
* Description
* Events
* Past events
* Upcoming events
* Basic credibility/verification status

---

# 41. ADMIN AUDIT LOG

Implement an audit log.

Track important actions:

* Event creation
* Event changes
* Ticket changes
* Attendance override
* Task verification
* Contribution verification
* Point adjustments
* Badge awards/revocations
* Rank changes
* User role changes

Each audit entry should contain:

* Actor
* Action
* Target
* Timestamp
* Relevant metadata

---

# 42. MANUAL POINT ADJUSTMENTS

Authorized administrators may adjust Impact Points.

Every adjustment must require:

* Amount
* Reason
* Administrator
* Timestamp

Never silently modify a user's score.

---

# 43. DATA MODEL

Design a normalized database architecture around entities such as:

* User
* Profile
* Organization
* Community
* Membership
* Event
* Venue
* TicketType
* Ticket
* Order
* Payment
* Attendance
* AttendanceVerification
* PeerConfirmation
* Task
* TaskAssignment
* TaskSubmission
* Contribution
* Activity
* ImpactTransaction
* Milestone
* MilestoneRequirement
* Badge
* BadgeAward
* Rank
* RankRequirement
* AchievementRule
* Notification
* AuditLog
* Leaderboard
* EventStaff

Use proper relationships, indexes, constraints and timestamps.

---

# 44. DATABASE REQUIREMENTS

Use:

* UUIDs or secure unique IDs
* Created timestamps
* Updated timestamps
* Soft deletion where appropriate
* Proper indexes
* Foreign keys/references
* Transactional operations where required
* Idempotency where required

Do not expose internal database IDs unnecessarily.

---

# 45. SECURITY

Implement strong security from the beginning.

Requirements:

* Input validation
* Output encoding
* Authorization checks
* RBAC
* Rate limiting
* CSRF protection where applicable
* Secure authentication
* Password hashing
* Secure session handling
* File upload validation
* Image validation
* Payment webhook validation
* API validation
* Audit logging
* Abuse prevention

Never rely exclusively on frontend validation.

Every sensitive operation must be authorized server-side.

---

# 46. PRIVACY

Follow privacy-by-design principles.

Location information must be:

* Requested only when needed
* Used only for attendance verification
* Not continuously tracked
* Minimized in storage
* Protected from unauthorized access

Provide clear consent messaging.

Allow users to control profile visibility.

Do not expose private member information through public APIs.

---

# 47. GEOLOCATION IMPLEMENTATION

Use browser/device geolocation where supported.

Implement distance calculation using a reliable geographic formula such as Haversine.

Do not assume GPS accuracy is perfect.

Consider:

* GPS accuracy
* Permission denied
* Timeout
* Location unavailable
* Low accuracy
* Browser restrictions

Provide useful fallback methods such as:

* QR
* Organizer verification

Do not prevent legitimate attendance simply because GPS fails.

---

# 48. OFFLINE/LOW CONNECTIVITY

The platform should be resilient in poor network environments.

Where practical:

* Cache event/ticket data
* Allow ticket QR to load from cached data
* Support PWA installation
* Queue non-sensitive actions where appropriate
* Retry failed requests safely
* Avoid large bundles

Do not cache sensitive information insecurely.

---

# 49. PWA

Make TickVendor installable as a Progressive Web App.

Include:

* Manifest
* Service worker
* Offline shell
* App icons
* Install prompt
* Responsive mobile experience

The PWA should not compromise security.

---

# 50. ACCESSIBILITY

Follow WCAG principles.

Include:

* Keyboard navigation
* Proper semantic HTML
* Accessible forms
* Labels
* Error messages
* Focus states
* Sufficient contrast
* Screen-reader-friendly components

---

# 51. RESPONSIVE DESIGN

Design mobile-first.

Primary targets:

* Android mobile browsers
* iOS mobile browsers
* Tablets
* Desktop

The majority of participant interactions should be comfortable on a smartphone.

---

# 52. PERFORMANCE

Optimize for:

* Low bandwidth
* Mobile devices
* Slow CPUs
* Large community datasets

Use:

* Code splitting
* Lazy loading
* Image optimization
* Pagination
* Server-side filtering
* Database indexing
* Efficient queries
* Caching where appropriate

Avoid loading huge datasets into the browser.

---

# 53. UI STRUCTURE

Suggested participant navigation:

### Home

Progress + upcoming events + recommended actions

### Events

Discover events

### Tickets

My tickets

### Activity

Attendance + tasks + contributions

### Achievements

Ranks + badges + milestones

### Profile

Account and settings

Organizer navigation may additionally contain:

### Manage

Events + tickets + attendance + tasks + members + analytics

Keep navigation simple and role-aware.

---

# 54. HOME DASHBOARD

The participant dashboard should immediately communicate:

### Your Progress

Community Builder

347 Impact Points

████████████░░░

153 points to next milestone.

Then:

**Next Action**

Attend Saturday Meetup

+10 Impact Points

And:

* Upcoming tickets
* Pending tasks
* Recent achievements
* Recent activity

---

# 55. EVENT PAGE

Event page should contain:

* Cover image
* Title
* Organizer
* Date
* Time
* Venue
* Map
* Description
* Ticket types
* Availability
* Event rules
* Attendance information
* Get Ticket button

Keep purchase/registration flow simple.

---

# 56. CHECK-IN EXPERIENCE

When attendance opens:

Show:

# Check In

Event name

📍 Location status

**Inside attendance zone**

Then:

### CHECK IN

After successful check-in:

> ✓ Attendance recorded

Then display:

> Your attendance is awaiting verification.

or:

> ✓ Attendance verified

Do not force users through complicated forms.

---

# 57. PEER VERIFICATION EXPERIENCE

After an event:

> **Help verify attendance**

Show a few participants.

For each:

**Did you see this person at the event?**

YES

I CAN'T CONFIRM

Keep this interaction extremely fast.

---

# 58. ACHIEVEMENT EXPERIENCE

When a user reaches a milestone:

Display a lightweight celebration.

Example:

> 🎉 Milestone Achieved

**Community Builder**

You have completed:

✓ 10 events

✓ 5 tasks

✓ 300 Impact Points

Avoid excessive animations.

---

# 59. EVENT CREATION UX

Use progressive disclosure.

Do not present 50 fields on one screen.

Suggested steps:

1. Basic information
2. Date & location
3. Tickets
4. Attendance
5. Engagement
6. Publish

Show a clear progress indicator.

---

# 60. ANALYTICS

Provide useful metrics.

Event analytics:

* Views
* Registrations
* Ticket sales
* Check-ins
* Attendance rate
* Verification rate
* No-show rate
* Engagement
* Points generated

Community analytics:

* Active members
* Participation rate
* Attendance
* Tasks
* Contributions
* Achievement progression

---

# 61. API DESIGN

Build a clean REST API or equivalent backend API architecture.

Organize endpoints around:

* Auth
* Users
* Communities
* Events
* Tickets
* Orders
* Payments
* Attendance
* Verification
* Tasks
* Contributions
* Activities
* Achievements
* Badges
* Ranks
* Notifications
* Analytics
* Admin

Use consistent:

* HTTP status codes
* Error responses
* Validation
* Pagination
* Filtering
* Authorization

---

# 62. ERROR HANDLING

Every user-facing operation must have meaningful errors.

Never display raw stack traces.

Examples:

> Unable to verify your location. Please try again or use the event QR code.

instead of:

> GeolocationError: POSITION_UNAVAILABLE

---

# 63. EMPTY STATES

Create thoughtful empty states.

Examples:

No tickets:

> You don't have any tickets yet.

No tasks:

> You're all caught up.

No achievements:

> Your journey starts with your first activity.

No events:

> No events found nearby.

---

# 64. DESIGN LANGUAGE

Create a consistent design system.

Define:

* Typography
* Spacing
* Buttons
* Cards
* Inputs
* Modals
* Toasts
* Badges
* Status indicators
* Tables
* Navigation
* Mobile components

Avoid visual clutter.

Use icons consistently.

Do not overuse gradients, shadows or animations.

---

# 65. BRAND IDENTITY

Create a modern identity around the name:

**TickVendor**

Possible visual concept:

A check/tick integrated into an event/ticket shape.

The logo should work as:

* Full logo
* App icon
* Favicon
* Monochrome mark

Do not make the brand overly corporate or overly playful.

It should feel trustworthy, modern and community-oriented.

---

# 66. INTERNATIONALIZATION

Architect the application so localization can be added later.

Initially support:

* English
* Nigerian Naira

Use configurable:

* Currency
* Time zone
* Date format
* Number format

Do not hard-code currency symbols throughout the code.

---

# 67. ADMIN CONFIGURATION

Administrators should be able to configure:

* Point rules
* Attendance rules
* Verification requirements
* Badge rules
* Rank rules
* Milestones
* Contribution rules
* Event categories
* Notification rules
* Leaderboard visibility

Configuration should be data-driven rather than hard-coded.

---

# 68. IMPORTANT BUSINESS RULE

Money must NOT automatically determine who is the most valuable community member.

The system should recognize:

* Presence
* Consistency
* Execution
* Service
* Leadership
* Contribution
* Community participation

Financial contribution is only one dimension.

---

# 69. IMPORTANT PRODUCT PRINCIPLE

Do not turn TickVendor into a complicated gamification platform.

The purpose of the achievement system is:

> **Recognition of meaningful participation.**

Badges, points and ranks should reinforce real-world contribution.

---

# 70. DEVELOPMENT REQUIREMENTS

Before writing implementation code:

1. Analyze the entire specification.
2. Identify architectural dependencies.
3. Design the database schema.
4. Design the API architecture.
5. Design RBAC.
6. Design the achievement/rules engine.
7. Design the ticketing system.
8. Design attendance verification.
9. Design the payment abstraction.
10. Design the frontend information architecture.

Then implement the system systematically.

Do NOT build isolated mock screens.

All major UI elements should connect to real application logic.

---

# 71. DEVELOPMENT QUALITY

Write:

* Modular code
* Maintainable code
* Reusable components
* Strong typing where supported
* Clear naming
* Centralized configuration
* Environment variables for secrets
* Proper error handling
* Tests for critical business logic

Avoid:

* Giant components
* Duplicated logic
* Hard-coded configuration
* Hard-coded point values
* Hard-coded ranks
* Hard-coded badges
* Hard-coded event categories
* Fake payment success
* Fake attendance verification

---

# 72. TESTING

Create tests for critical functionality.

At minimum test:

### Authentication

* Registration
* Login
* Authorization

### Tickets

* Ticket creation
* Ticket purchase
* QR generation
* QR validation
* Duplicate scan prevention

### Attendance

* Geofence calculation
* Check-in window
* Duplicate check-in
* Verification

### Peer verification

* Eligibility
* Confirmation limits
* Duplicate confirmations
* Verification completion

### Tasks

* Assignment
* Completion
* Verification
* Reward

### Contributions

* Recording
* Verification
* Reward calculation

### Achievement engine

* Point calculation
* Milestone qualification
* Badge qualification
* Rank progression
* Duplicate reward prevention

### Security

* Unauthorized access
* Role escalation
* Input validation

---

# 73. SEED DATA

Provide development/demo seed data.

Create:

* Demo users
* Demo organizer
* Demo community
* Demo events
* Demo tickets
* Demo tasks
* Demo badges
* Demo ranks
* Demo milestones
* Demo activities

Clearly separate seed/demo data from production data.

---

# 74. DOCUMENTATION

Create comprehensive project documentation.

Include:

* README
* Architecture overview
* Environment variables
* Installation
* Local development
* Database setup
* Migration/seed process
* API documentation
* Authentication
* Payment integration
* Deployment
* PWA
* Geolocation
* Achievement engine
* Admin configuration

---

# 75. ENVIRONMENT CONFIGURATION

Never commit secrets.

Use environment variables for:

* Database credentials
* Authentication secrets
* Payment provider keys
* Storage credentials
* Email provider credentials
* Maps configuration
* API URLs

Provide `.env.example`.

---

# 76. DEPLOYMENT

Prepare the application for production deployment.

Separate:

* Development
* Staging
* Production

Ensure:

* Secure environment variables
* Database migrations
* Logging
* Error monitoring hooks
* HTTPS
* CORS configuration
* Rate limiting
* Secure headers

---

# 77. OBSERVABILITY

Prepare for:

* Application logging
* Error tracking
* API performance monitoring
* Payment webhook monitoring
* Attendance failures
* Authentication failures

Do not log passwords, payment credentials or unnecessary sensitive location information.

---

# 78. FUTURE-READY ARCHITECTURE

Do not over-engineer the first implementation, but structure the system so future functionality can be added.

Potential future features:

* Native Android/iOS apps
* WhatsApp notifications
* Telegram integration
* Corporate teams
* Certificates
* Membership cards
* Public achievement profiles
* Event sponsorship
* Event promotion
* Referral systems
* API integrations
* Advanced fraud detection
* AI event recommendations
* Community marketplace

The current architecture should not make these impossible.

---

# 79. CORE PRODUCT LOOP

The implementation should preserve this fundamental loop:

### EVENT

Organizer creates event.

↓

### TICKET

Participant obtains ticket.

↓

### ATTEND

Participant arrives.

↓

### CHECK-IN

QR/GPS/manual check-in.

↓

### VERIFY

GPS + QR + peer/organizer verification.

↓

### PARTICIPATE

Tasks, volunteering, contributions and activities.

↓

### IMPACT

Impact Points awarded.

↓

### MILESTONE

Requirements fulfilled.

↓

### BADGE

Achievement awarded.

↓

### RANK

Member progresses.

↓

### RECOGNITION

Participant sees measurable history of contribution.

---

# 80. DEFINITION OF DONE

Do not consider the project complete merely because pages render.

The application is complete when:

* Authentication works.
* Roles work.
* Events can be created.
* Events can be discovered.
* Tickets can be created.
* Tickets can be issued.
* QR tickets work.
* Ticket validation works.
* Attendance works.
* Geofencing works.
* Peer confirmation works.
* Tasks work.
* Contributions work.
* Impact Points work.
* Milestones work.
* Badges work.
* Ranks work.
* Achievement rules are configurable.
* Communities work.
* Notifications work.
* Admin management works.
* Audit logging works.
* Security controls are implemented.
* Critical business logic is tested.
* Responsive mobile UX works.
* PWA works.
* Production configuration exists.
* Documentation exists.

---

# 81. CRITICAL IMPLEMENTATION INSTRUCTION

Do not simplify the product by removing major functionality from this specification without explicitly documenting the reason.

Do not replace functional systems with fake/mock implementations unless a third-party credential is genuinely required.

If an external service requires credentials that are unavailable, implement the integration interface, configuration, error handling and development mock/test adapter so the real provider can be connected without rewriting the application.

Prioritize working architecture over visual prototypes.

---

# 82. FINAL UX TEST

After implementation, mentally test the complete experience as three users.

### Participant

"I want to find an event, get a ticket, attend, check in and see my progress."

This must be extremely simple.

### Organizer

"I want to create an event, sell tickets, manage attendees, verify attendance and understand engagement."

This must be straightforward.

### Community Administrator

"I want to turn member participation into measurable milestones, badges and ranks."

This must be configurable without modifying source code.

If any of these journeys is unnecessarily complicated, simplify the UX.

---

# FINAL PRODUCT STATEMENT

Build TickVendor as a lightweight, scalable platform where:

> **Tickets bring people to events.**
>
> **Events create participation.**
>
> **Participation creates measurable impact.**
>
> **Impact creates milestones.**
>
> **Milestones create recognition.**

The product should ultimately answer one simple question for every participant:

> **"What have I contributed, and how far have I come?"**

Build the complete system around that principle.
