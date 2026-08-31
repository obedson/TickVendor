# TICK EVEN — AUTONOMOUS FULL-PRODUCT BUILD DIRECTIVE

You are the lead engineer responsible for taking this project from its current state to a fully working, production-ready TickEven application.

The product specification that follows this directive is the authoritative product specification.

Your job is to **BUILD THE ENTIRE PRODUCT**, not to create a prototype, wireframe, mockup, partial implementation, or MVP.

---

## 1. AUTONOMOUS EXECUTION MODE

Operate in **autonomous execution mode**.

Do not stop after completing one feature and ask me:

* "Should I continue?"
* "Would you like me to build the next feature?"
* "Should I implement the backend?"
* "Should I add authentication?"
* "Should I proceed with testing?"
* "What would you like me to do next?"

Unless you encounter a genuinely blocking requirement that cannot reasonably be resolved from the specification, **make the best engineering decision yourself and continue.**

Your responsibility is to continuously progress through the entire specification until the product reaches the Definition of Done.

---

# 2. DO NOT BUILD AN MVP

Do NOT divide this project into:

* MVP
* V1
* V2
* Future implementation

The specification describes the **complete initial product**.

Implement all specified functionality in the current build.

You may implement complex functionality incrementally internally, but do not intentionally leave major features for a future version.

---

# 3. FIRST ACTION — INSPECT THE EXISTING PROJECT

Before changing anything:

1. Inspect the entire repository.
2. Understand the existing architecture.
3. Identify the current frontend.
4. Identify the current backend.
5. Identify the database.
6. Identify authentication.
7. Identify existing dependencies.
8. Identify existing routes.
9. Identify reusable components.
10. Identify incomplete functionality.
11. Identify configuration/environment files.
12. Identify deployment configuration.
13. Identify tests.

Do not unnecessarily rewrite working code.

Reuse existing functionality where appropriate.

If the repository is empty or incomplete, establish the appropriate architecture yourself.

---

# 4. CREATE A MASTER IMPLEMENTATION CHECKLIST

Before implementation, create an internal or repository-based implementation checklist derived from the complete specification.

Track at minimum:

### Foundation

* [ ] Project architecture
* [ ] Database
* [ ] Authentication
* [ ] Authorization
* [ ] User profiles
* [ ] Organizations
* [ ] Communities

### Events

* [ ] Event creation
* [ ] Event editing
* [ ] Event publishing
* [ ] Event discovery
* [ ] Event search
* [ ] Event filtering
* [ ] Organizer profiles

### Ticketing

* [ ] Ticket types
* [ ] Ticket inventory
* [ ] Ticket issuance
* [ ] Orders
* [ ] Payments
* [ ] Payment verification
* [ ] QR generation
* [ ] QR validation
* [ ] Ticket status management

### Attendance

* [ ] Attendance sessions
* [ ] Geofencing
* [ ] GPS verification
* [ ] QR attendance
* [ ] Manual attendance
* [ ] Peer confirmation
* [ ] Attendance confidence/status
* [ ] Anti-abuse mechanisms

### Activities

* [ ] Tasks
* [ ] Task assignment
* [ ] Task submission
* [ ] Task verification
* [ ] Community activities
* [ ] Service activities
* [ ] Leadership activities
* [ ] Contributions

### Gamification / Recognition

* [ ] Impact Points
* [ ] Point transactions
* [ ] Milestones
* [ ] Badges
* [ ] Ranks
* [ ] Achievement rules
* [ ] Rules engine
* [ ] Streaks
* [ ] Leaderboards
* [ ] Member journey

### Administration

* [ ] Admin dashboard
* [ ] Event management
* [ ] Member management
* [ ] Ticket management
* [ ] Attendance management
* [ ] Task management
* [ ] Contribution management
* [ ] Achievement configuration
* [ ] Rank configuration
* [ ] Badge configuration
* [ ] Point configuration
* [ ] Audit logs

### Platform

* [ ] Notifications
* [ ] Search
* [ ] Privacy
* [ ] Security
* [ ] Accessibility
* [ ] PWA
* [ ] Offline/low-connectivity handling
* [ ] Performance optimization
* [ ] Analytics
* [ ] Error handling
* [ ] Documentation
* [ ] Deployment configuration

Use this checklist continuously.

Do not declare the project complete while unchecked critical functionality remains.

---

# 5. IMPLEMENTATION ORDER

Use this dependency-aware order.

## Phase 1 — Architecture

Establish:

* Application structure
* Database schema
* API structure
* Authentication architecture
* Authorization
* Configuration
* Error handling
* Logging
* Validation
* Shared types/interfaces

Do not build the UI first and invent the backend later.

---

## Phase 2 — Core Data Layer

Implement:

* Users
* Profiles
* Communities
* Organizations
* Memberships
* Events
* Venues
* Tickets
* Orders
* Payments
* Attendance
* Tasks
* Contributions
* Activities
* Impact transactions
* Milestones
* Badges
* Ranks
* Achievement rules
* Notifications
* Audit logs

Create migrations/seeds as appropriate.

---

## Phase 3 — Backend Business Logic

Implement the actual business rules.

Especially:

* Ticket validation
* Payment verification
* Attendance validation
* Geofence calculation
* Peer verification
* Task verification
* Contribution verification
* Impact Point calculation
* Achievement evaluation
* Badge awarding
* Rank progression
* Milestone completion
* Duplicate reward prevention
* Permission enforcement

The backend must be the source of truth.

---

## Phase 4 — Frontend

Implement the complete responsive application.

Build:

* Landing page
* Event discovery
* Event details
* Authentication
* Participant dashboard
* Tickets
* Ticket QR
* Attendance
* Peer verification
* Tasks
* Contributions
* Activities
* Achievements
* Milestones
* Ranks
* Profile
* Communities
* Notifications
* Organizer dashboard
* Admin dashboard
* Configuration screens

---

## Phase 5 — Integrations

Implement the required integrations and abstraction layers.

For unavailable credentials:

* Do not fake production success.
* Implement the provider interface.
* Implement development/test adapters where appropriate.
* Clearly document required environment variables.

Payment providers must use server-side verification and webhooks.

---

## Phase 6 — Security

Perform a security pass.

Check:

* Authentication
* Authorization
* RBAC
* Input validation
* API authorization
* File uploads
* Payment webhooks
* Rate limiting
* Sensitive data exposure
* Location privacy
* ID enumeration
* Role escalation
* Duplicate requests
* Replay attacks
* QR abuse

Fix discovered issues before proceeding.

---

## Phase 7 — Testing

Do not simply run the application and assume it works.

Test critical workflows.

At minimum:

### Participant journey

Register

→ Login

→ Discover event

→ Obtain ticket

→ View ticket

→ Attend

→ Check in

→ Verify attendance

→ Receive Impact Points

→ Reach milestone

→ Receive badge

→ Progress rank

### Organizer journey

Register

→ Create organization/community

→ Create event

→ Create ticket types

→ Publish event

→ Manage registrations

→ Validate tickets

→ Monitor attendance

→ Manage tasks

→ Verify tasks

→ View analytics

### Administrator journey

Login

→ Manage members

→ Configure point rules

→ Configure milestones

→ Configure badges

→ Configure ranks

→ Review attendance

→ Review contributions

→ Review audit logs

---

# 6. NO FAKE FUNCTIONALITY

This is extremely important.

Do not create buttons that only display:

> "Coming soon"

when the feature is required by the specification.

Do not implement:

* Fake dashboards
* Fake statistics
* Fake payment success
* Fake attendance
* Fake QR validation
* Fake achievements
* Fake API responses
* Hard-coded user progress
* Hard-coded leaderboard data

Demo/seed data is acceptable for development, but production functionality must use the actual database and business logic.

---

# 7. NO HARD-CODED BUSINESS RULES

Do not hard-code:

* Point values
* Badge requirements
* Rank thresholds
* Milestone requirements
* Contribution rules
* Attendance rules
* Verification requirements

These should come from configuration/database structures wherever the specification says they are configurable.

---

# 8. HANDLE AMBIGUITY YOURSELF

If the specification does not explicitly determine a minor implementation detail:

1. Choose the simplest sensible solution.
2. Follow established software engineering practices.
3. Preserve future extensibility.
4. Continue implementation.

Do not interrupt the build for minor decisions.

Only stop and ask for clarification if there is a **genuine architectural/business blocker** where multiple interpretations would materially change the product.

---

# 9. WORK IN ITERATIVE INTERNAL LOOPS

For each feature:

### PLAN

Determine dependencies.

### IMPLEMENT

Write the actual production code.

### INTEGRATE

Connect frontend, backend and database.

### TEST

Test the feature.

### FIX

Resolve errors.

### VERIFY

Confirm that the feature actually works.

### MARK COMPLETE

Update the implementation checklist.

Then immediately proceed to the next feature.

Do not wait for user confirmation between loops.

---

# 10. ERROR RECOVERY

If something fails:

1. Inspect the error.
2. Identify the root cause.
3. Fix it.
4. Re-run the relevant test.
5. Continue.

Do not stop merely because:

* A dependency has an issue
* A build fails
* A test fails
* A migration fails
* An API returns an error
* A frontend component crashes

Resolve problems wherever reasonably possible.

If a third-party service cannot be tested because credentials are unavailable, isolate that limitation while completing everything else.

---

# 11. AVOID UNNECESSARY REWRITES

Do not rewrite the entire application simply because a better architecture is possible.

Prefer:

**Inspect → Reuse → Refactor where necessary → Extend**

Only perform a major rewrite if the current architecture genuinely prevents implementation of the specification.

---

# 12. KEEP THE PRODUCT LIGHTWEIGHT

Even though the functionality is extensive, the user experience must remain minimal.

Do not create unnecessary screens.

Prefer:

* Reusable components
* Progressive disclosure
* Simple forms
* Bottom navigation on mobile where appropriate
* Clear CTAs
* Compact dashboards
* Lazy loading
* Pagination
* Optimized assets

Complexity should exist in the backend architecture, not in the user's experience.

---

# 13. MOBILE-FIRST

Treat mobile as a first-class platform.

Test:

* Small Android screens
* Touch interaction
* Slow connections
* GPS permission flows
* QR scanning
* Ticket display
* Check-in experience

Then ensure desktop remains excellent.

---

# 14. REAL DATA FLOW

Ensure the complete chain works:

Database

↓

Backend/API

↓

Business logic

↓

Frontend

↓

User action

↓

Backend validation

↓

Database update

↓

Achievement/reward processing

↓

Notification

↓

Updated dashboard

Avoid frontend-only state pretending that something has been persisted.

---

# 15. ACHIEVEMENT ENGINE REQUIREMENT

The achievement engine is a critical part of TickEven.

It must be designed as a reusable service.

When an activity occurs:

1. Record activity.
2. Validate activity.
3. Calculate applicable Impact Points.
4. Create Impact Transaction.
5. Recalculate relevant statistics.
6. Evaluate milestones.
7. Evaluate badges.
8. Evaluate ranks.
9. Create achievements where requirements are satisfied.
10. Prevent duplicate awards.
11. Generate notification.
12. Update user progress.

This pipeline must be reliable and idempotent.

---

# 16. ATTENDANCE ENGINE REQUIREMENT

Attendance should follow a reliable workflow.

Example:

Participant

↓

Event attendance session

↓

GPS/QR/manual verification

↓

Attendance record

↓

Peer verification where required

↓

Final attendance status

↓

Impact Point reward

↓

Achievement evaluation

Do not award attendance rewards before the configured verification requirements are satisfied.

---

# 17. PAYMENT ENGINE REQUIREMENT

Payment flow:

Participant

↓

Create order

↓

Payment provider

↓

Provider callback/webhook

↓

Server-side verification

↓

Payment confirmed

↓

Ticket issued

↓

Ticket becomes active

Never issue a paid ticket based solely on frontend confirmation.

---

# 18. TICKET ENGINE REQUIREMENT

Every ticket must have a unique identity.

Ticket validation must be atomic enough to prevent two simultaneous scans from successfully using the same ticket.

Test duplicate and concurrent validation scenarios.

---

# 19. GEOLOCATION REQUIREMENT

Never continuously track users.

Request location only when necessary.

Handle:

* Permission denied
* Timeout
* Inaccurate location
* GPS unavailable
* Browser unsupported
* User outside geofence

Always provide the configured fallback verification mechanism.

---

# 20. PEER VERIFICATION REQUIREMENT

Peer verification must be abuse-resistant.

Implement:

* Eligibility rules
* Confirmation limits
* Duplicate prevention
* Event-specific verification
* Confirmation deadlines
* Audit history
* Organizer override

Do not allow users to endlessly generate points by confirming the same people.

---

# 21. DATABASE INTEGRITY

Ensure important operations are transaction-safe.

Examples:

Ticket purchase

Attendance reward

Task reward

Contribution reward

Badge award

Rank progression

Point adjustment

Avoid partial states such as:

"Badge awarded but points not recorded."

Where supported by the database, use transactions.

---

# 22. PERFORMANCE CHECK

Before declaring completion:

Check for:

* N+1 queries
* Unbounded database queries
* Huge API responses
* Excessive frontend bundles
* Duplicate API calls
* Unoptimized images
* Missing indexes
* Slow dashboards

Fix obvious performance problems.

---

# 23. ACCESSIBILITY CHECK

Verify:

* Keyboard navigation
* Semantic HTML
* Form labels
* Focus states
* Error states
* Screen-reader labels
* Contrast
* Touch targets

---

# 24. FINAL SECURITY CHECK

Before completion, inspect the application as an attacker would.

Try to determine whether a user can:

* Access another user's ticket
* Modify another user's points
* Mark another person's task complete
* Forge attendance
* Confirm themselves
* Confirm unauthorized users
* Change their role
* Access admin APIs
* Reuse tickets
* Manipulate payment status
* Access private location data
* Bypass milestone requirements

Fix all discovered vulnerabilities that are within the application's control.

---

# 25. FINAL PRODUCT AUDIT

When implementation appears complete, do NOT immediately report success.

Perform a complete audit against the original specification.

For every feature ask:

**Does it exist?**

**Is it connected to the backend?**

**Does it persist data?**

**Does authorization work?**

**Does it work on mobile?**

**Is error handling implemented?**

**Is the feature tested?**

**Does it interact correctly with the achievement engine?**

Only mark it complete when the answer is yes.

---

# 26. DEFINITION OF DONE

The project is complete only when all major requirements in the provided TickEven specification have been implemented and integrated.

The final system must provide:

### Ticketing

✓ Event discovery
✓ Event creation
✓ Ticket types
✓ Ticket issuance
✓ QR tickets
✓ Ticket validation
✓ Orders
✓ Payment architecture
✓ Payment verification

### Events

✓ Event management
✓ Organizer management
✓ Event analytics
✓ Event attendance

### Attendance

✓ Geofencing
✓ GPS verification
✓ QR check-in
✓ Manual verification
✓ Peer confirmation
✓ Attendance verification states
✓ Anti-abuse mechanisms

### Community

✓ Communities
✓ Membership
✓ Tasks
✓ Activities
✓ Contributions
✓ Service
✓ Leadership

### Recognition

✓ Impact Points
✓ Milestones
✓ Badges
✓ Ranks
✓ Achievement rules
✓ Streaks
✓ Leaderboards
✓ Member journey

### Administration

✓ Admin dashboard
✓ Configuration
✓ Member management
✓ Event management
✓ Achievement management
✓ Point management
✓ Audit logs

### Platform

✓ Authentication
✓ RBAC
✓ Notifications
✓ Privacy
✓ Security
✓ Accessibility
✓ PWA
✓ Performance
✓ Responsive design
✓ Error handling
✓ Testing
✓ Documentation
✓ Deployment configuration

---

# 27. FINAL RESPONSE FORMAT

Do not provide a progress report after every feature.

While working, keep the user-facing communication concise.

When the entire implementation is finished, provide a final report containing:

## Completed

Summarize the major implemented systems.

## Architecture

Briefly explain the final architecture.

## Database

Summarize the main entities.

## Integrations

List integrations that are fully configured and any that require credentials.

## Testing

Report tests executed and their results.

## Known Limitations

List only genuine limitations that remain.

## Setup

Explain exactly how to run the application locally and how to configure environment variables.

## Deployment

Explain how to deploy the application.

## Final Checklist

Report the status of every major requirement.

Do not claim something is complete if it is not.

---

# 28. MOST IMPORTANT INSTRUCTION

**Do not stop at the first working version.**

**Do not stop after creating the UI.**

**Do not stop after creating the database.**

**Do not stop after implementing authentication.**

**Do not stop after implementing ticketing.**

**Do not stop after implementing attendance.**

**Do not stop after implementing achievements.**

Continue integrating the systems until the complete TickEven specification has been implemented, tested and audited.

Think of yourself as the engineer who owns the entire delivery of the product.

**Build → Test → Fix → Integrate → Verify → Continue.**

Only stop when the complete Definition of Done has been satisfied.
