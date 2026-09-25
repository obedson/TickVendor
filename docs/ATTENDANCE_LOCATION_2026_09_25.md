# Attendance location reconciliation — 2026-09-25

Scope: the reported ticket self-check-in accuracy rejection and organizer visibility of submitted coordinates/proximity. Relevant contract: TICKVENDOR_SPEC sections 14, 15 and 47. Coordinates are browser-reported approximate evidence, not independently proven physical positions.

## Findings and implementation

- Ticket self-check-in compared browser accuracy to the event radius before calculating distance. Being physically inside the venue does not ensure the device reports sufficiently precise coordinates. The screenshot establishes the rejection but cannot establish the device's numerical accuracy or the configured radius. Neither staging database nor device telemetry was accessed.
- The original rejection discarded evidence. Valid GPS signals already stored coordinates/accuracy and a distance in their reason, but the roster omitted these fields.
- Both event check-in paths now share location assessment. Acceptance still requires distance within radius and reported accuracy no larger than radius. Missing accuracy can no longer be silently accepted as GPS verified. Distance decisions use unrounded Haversine values. No inflation of radius or invented device precision.
- The browser requests up to three fresh high-accuracy fixes (six-second timeout per request) when an event radius is available. It stops when sufficient accuracy is obtained, otherwise submits the most accurate reading. Permission denial always stops. Sampling is bounded to a user action; no continuous tracking. This cannot guarantee device precision.
- Event-scoped `attendance.location_submitted` audit snapshots retain submitted coordinates, accuracy, calculated distance, venue coordinates/radius at that time, outcome, operation and server timestamp. A rejected ticket location is committed before returning 422 without creating attendance, consuming the ticket or awarding points. Valid evidence commits with attendance. Existing repeated successful self-check-ins remain idempotent and retain the original evidence.
- Authorized People → Check-in → Attendance roster shows saved GPS/check-out signals and the latest submitted location attempt per participant. The API uses event authorization, the existing paginated participant set and a window query to avoid fetching unbounded attempt histories. The review queue remains an exception queue. No coordinates are added to public discovery or peer APIs.
- Legacy valid/invalid GPS evidence is exposed using the originally persisted distance; it is not recalculated against a subsequently edited venue. Old rejected ticket attempts were never saved and cannot be recovered. Without browser coordinates (denial/unavailable), no coordinate can truthfully be recorded. Requests rejected before location assessment for ownership, timing, invalid payload or event configuration do not become attendance attempts.
- Ticket check-in and checkout routes erroneously passed a dictionary returned by the service to a serializer expecting an Attendance model. Returning the already-serialized state directly fixes successful HTTP responses and is covered through actual local TestClient requests.
- No model/schema/migration changes. Existing audit storage and attendance verification columns are reused; no historical data is rewritten. No provider settings changed.

## Verification

- Initial focused run: 36 passed / 1 failed. The failed positive geofence fixture omitted accuracy; updated it to supply 12 metres while retaining its verified-status and single-award assertions. New negative coverage proves missing accuracy is refused.
- Corrected focused run: `python -m pytest tests/test_attendance_location_evidence.py tests/test_attendance_service.py -q`: 9 passed. Includes HTTP 422 durability, authorized roster display, 401/403 protection, retry to successful admission, repeat idempotency and checkout; includes a just-outside boundary precision test.
- The initial run's ticket-holder/entitlement and organizer attendance operations regressions passed (29 tests across those two files); unchanged after that run except HTTP response serialization now covered by the added HTTP test.
- Frontend location checks: six behavioral sampling cases plus error classification/attendance integration script passed.
- Production build/type check, frontend lint, changed Python Ruff and compile checks passed. Final whitespace check recorded in BUILD_STATUS.
- Full backend and Playwright suites were not run.

## External verification outstanding (B)

On staging, compare a precise GPS-capable phone with a laptop reporting coarse accuracy at the same venue. Confirm numeric errors, denied/timeout guidance, a saved failed attempt in the authorized roster, improved retry success, coordinates/distance/accuracy, checkout evidence, and responsive keyboard use of the roster/refresh. Confirm another community's staff cannot obtain the evidence. Rehearse deployment as usual; no migration is required. No deployed/manual behavior is claimed from these local tests.
