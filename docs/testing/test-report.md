# Test report

Generated from the `feature/demo-and-frontend-wiring` branch on 10 November 2026 with Python 3.12,
PostgreSQL 16 and Redis 7. CI repeats the same run on every pull request.

## How to reproduce

```bash
cd backend
pytest --cov=. --cov-report=term-missing --cov-report=html --junitxml=junit.xml
# htmlcov/index.html shows line and branch coverage per file
```

## Summary

| | Result |
|---|---|
| Automated tests | **265 passed**, 0 failed, 0 errors, 0 skipped (42 s) |
| Line coverage | **2,628 / 2,691 statements (97.7%)** |
| Branch coverage | **523 / 580 branches (90.2%)** |
| Combined (coverage.py total) | **96.3%**, CI gate is 85% |
| Lint | ruff: no issues; eslint (frontend): no issues |
| Migrations | `makemigrations --check`: no changes |

## Coverage by module

| Module (SAD component) | Lines | Line % | Branches | Branch % |
|---|---|---|---|---|
| accounts (Auth & Access Control) | 93 / 93 | 100.0 | 14 / 14 | 100.0 |
| applications (Application Manager, Analytics) | 609 / 628 | 97.0 | 95 / 106 | 89.6 |
| config | 86 / 93 | 92.5 | 3 / 6 | 50.0 |
| core | 5 / 5 | 100.0 | – | – |
| integrations (sources, ATS, X, demo) | 353 / 365 | 96.7 | 78 / 90 | 86.7 |
| matching (Job Aggregation & Matching) | 428 / 430 | 99.5 | 73 / 78 | 93.6 |
| outreach (Outreach & Connection Manager) | 256 / 259 | 98.8 | 45 / 50 | 90.0 |
| resume_parser (Resume & Profile Optimizer) | 495 / 507 | 97.6 | 163 / 180 | 90.6 |
| scheduler (Scheduler & Rate Limiter) | 303 / 311 | 97.4 | 52 / 56 | 92.9 |

## Tests by file

| File | Tests | Covers |
|---|---|---|
| test_accounts_auth.py | 20 | Registration, login, JWT expiry, roles (TC-27, TC-28) |
| test_disclaimer_and_pause.py | 15 | Legal disclaimer, Pause All (TC-29) |
| test_automation_gates.py | 5 | Automation blocked until disclaimer and profile are ready |
| test_platform_credentials.py | 4 | AES-256-GCM storage, no plaintext in DB (TC-26) |
| test_resume_parsing.py | 47 | Upload limits, parsing, scanned PDFs, profile 404 (TC-01 to TC-05) |
| test_profile_tips.py, test_profile_tips_api.py | 10 | Profile optimisation tips (TC-34) |
| test_sources.py | 20 | X adapter, listing collector, robots.txt |
| test_matching.py | 27 | Sources, scoring, de-duplication, filters (TC-06 to TC-09) |
| test_demo_source.py, test_seed_demo.py | 8 | Demo pipeline and seed data |
| test_scheduler.py | 26 | Schedules, 90% rate-limit hold, run log (TC-19 to TC-21) |
| test_admin_runs.py | 7 | Admin automation logs |
| test_applications.py | 49 | Kit, three channels, confirmation, caps, attempts, CAPTCHA, analytics (TC-10 to TC-14, TC-22 to TC-25, TC-35) |
| test_employer_responses.py | 4 | Logging replies and interviews (TC-23, TC-24) |
| test_notifications.py | 3 | Email and in-app notifications |
| test_outreach.py | 17 | Recruiters, drafts, caps, identical-message block (TC-15 to TC-18) |
| test_performance.py | 3 | 30 s search, 3 s dashboard queries (TC-30, TC-31) |

## System tests (web app, end to end)

Run in Chromium with Playwright against the running backend and the `seed_demo` account. All passed.

| Flow | Result |
|---|---|
| Wrong password, sign in, sign out; register a new account | Error shown; session kept and cleared correctly |
| New user must accept the disclaimer; not asked again after reload | Pass |
| Upload a non-resume file; upload a DOCX resume; edit and save profile; tips | Rejected with message; fields filled; saved; tips shown |
| Feed: 16 ranked jobs, platform filter, Search now, cross-platform "Also on" badge | Pass |
| Assisted apply: kit tabs, downloads, "I've applied" | Marked applied, feed updated |
| Career-page apply: Confirm & Apply disabled until the review box is ticked | Pass; without an API key it fails with the reason |
| Email apply through the demo mailbox | Message with resume attachment delivered to the mail catcher |
| Review queue lists drafts, failures and CAPTCHA stops | Pass |
| Analytics: KPIs, charts, keyword yield, status change, log interview, CSV export | Pass |
| Outreach: suggestions (including from merged duplicates), draft, LinkedIn mark-sent, cap shown | Pass |
| Sending the same outreach text to a second recruiter | Blocked (REQ-17) |
| X send without API keys | Shows "Not sent" with the reason |
| Pause All, then Search now | Refused: "Automation is paused." |
| Settings: sources, weekly schedule, Full-Auto, limits | Saved |
| Notification bell shows the CAPTCHA notice | Pass |

## Load test

See README "Performance": 50 concurrent users with no failures and no median degradation (TC-32).

## Known gaps

* The frontend has no unit tests; it is covered by the system tests above and by eslint in CI.
* X, Greenhouse and Lever are tested against mocked HTTP responses, not the live services.
* OWASP ZAP runs as a baseline scan in `zap.yml`; its report is attached to each CI run.
