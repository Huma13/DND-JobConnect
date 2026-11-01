# DND-JobConnect

LinkedIn and Social Media–Driven Automated Job Application System (Project 16, Team HAND).
Layered Django REST backend per the SW Architecture document.

## Quick start (one command, issue #8)

```bash
cp backend/.env.example backend/.env      # set DJANGO_SECRET_KEY and POSTGRES_PASSWORD
docker compose up --build
```

This starts PostgreSQL 15, Redis, a one-off migration job, the Django API (Gunicorn, port 8000),
a Celery worker and Celery beat. Check with `curl localhost:8000/health/`.

## Local development without Docker

```bash
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
docker compose up -d db redis                          # run from the repo root
echo DJANGO_DEBUG=1 > .env
python manage.py migrate
pytest --cov=.                                         # tests run against PostgreSQL
python manage.py runserver
celery -A config worker -l INFO                        # separate terminal
celery -A config beat -l INFO                          # separate terminal
```

## Layout

| Path | Layer | Contents |
|---|---|---|
| `backend/integrations/` | Integration | `IJobSource` interface, X/Tweepy adapter, LinkedIn + Naukri public listing collector |
| `backend/matching/` | Business | Relevance scoring, de-duplication, feed filters, search service, feed API |
| `backend/scheduler/` | Business / Data | Celery tasks, beat schedules, rate limiter, run log |
| `backend/accounts/` | Business | Minimal user model, JWT login, Pause All (the full auth story is separate) |
| `backend/resume_parser/` | Business | `Profile` model read by matching (the parsing story is separate) |
| `backend/loadtest/` | Testing | Locust scenarios and the 50-user degradation check |

## API (this increment)

All endpoints except register, login and health need `Authorization: Bearer <access token>`.

| Method | Endpoint | Requirement |
|---|---|---|
| GET/PUT | `/api/jobs/preferences/` | REQ-5: choose platforms, e.g. `{"platforms": ["naukri","x"]}` |
| GET | `/api/jobs/feed/?platform=&location=&min_score=&posted_within_days=&state=` | REQ-6, 7, 8 |
| POST | `/api/jobs/feed/search/` | Start a search now (202 + `run_id`) |
| POST | `/api/jobs/feed/{id}/skip/` | Hide a posting |
| GET/PUT/DELETE | `/api/scheduler/schedule/` | REQ-18, e.g. `{"cadence":"weekly","run_time":"09:00","weekday":0}` |
| GET | `/api/scheduler/runs/`, `/api/scheduler/runs/{id}/` | REQ-20 run log |
| GET | `/api/scheduler/rate-limits/` | REQ-19 current window usage |
| POST | `/api/auth/pause/` | SRS 6.2, `{"paused": true}` |

## How the requirements are met

* **Relevance (REQ-6):** skills 50, role 30, location 10, experience 10, giving a score from 0 to 100. Skills found
  in the title count double. Common abbreviations (ML, SDE, Sr.) are expanded before roles are compared.
  See `matching/scoring.py`.
* **Duplicates (REQ-7):** title and company are normalised (case, punctuation, "Pvt Ltd", "Sr." and so on) and
  hashed. The first copy a user sees is shown. Later copies, from any platform or run, attach to it as `also_on`.
* **Rate limits (REQ-19):** fixed windows per user, platform and action, locked with `SELECT … FOR UPDATE` so
  parallel workers cannot overshoot. At 90% the action is deferred and re-queued for when the window resets.
  A 429 from the platform blocks the window until the platform's reset time. Limits live in `settings.RATE_LIMITS`.
* **Schedules (REQ-18):** each user's schedule is stored as a `django-celery-beat` crontab in their time zone.
* **Sources (SRS 3.2):** X uses API v2 recent search (needs `X_BEARER_TOKEN`). LinkedIn and Naukri use their
  public, logged-out listing endpoints: GET only, an identifying User-Agent, a per-host delay, and robots.txt
  honoured by default. **Note:** LinkedIn's and Naukri's robots.txt currently disallow these paths, so with the
  default compliant setting those two sources log a clear error in the run log while X keeps working. Discuss
  with the team before changing `COLLECTOR_RESPECT_ROBOTS`. The parsers are tested against saved fixtures either way.
* **Pause All (SRS 6.2):** scheduled runs are skipped, manual searches are refused, and an in-flight run stops
  storing results as soon as the flag is seen.

## Performance (issue #43, SRS 6.1)

```bash
python manage.py seed_loadtest --users 50 --postings 2000
gunicorn config.wsgi -w 4 &
python loadtest/run_degradation.py --host http://localhost:8000
```

Measured locally (4 Gunicorn workers, PostgreSQL 16, 100,000 feed rows, 45 s per phase):

| | Requests | Failures | Median | p95 |
|---|---|---|---|---|
| 1 user (baseline) | 25 | 0 | 15 ms | 200 ms |
| 50 users | 1,065 | 0 | 14 ms | 990 ms |

The median does not degrade. The p95 rise comes from the login burst while 50 users ramp up, since Argon2
hashing is deliberately slow. Steady-state feed requests stay around 15–20 ms. CI also checks that a 3-platform
search finishes in about 2 s with sources run in parallel (TC-30), that slow sources are cut off, and that a
filtered 2,000-item feed responds in under 3 s with a fixed number of queries.

The analytics dashboard (TC-31) belongs to the Analytics story. The Locust file already calls
`/api/analytics/dashboard/` and starts measuring it once that endpoint exists.

## CI (issue #6)

`.github/workflows/ci.yml` runs on every PR: ruff lint, a migration check, pytest on PostgreSQL 15 + Redis with an
85% coverage gate, and a Docker image build. A push to `main` (a merged PR) publishes the image to GitHub
Container Registry. To require a passing build and one review before merging, a repo admin runs:

```bash
gh api -X PUT repos/Huma13/DND-JobConnect/branches/main/protection --input - <<'JSON'
{"required_status_checks":{"strict":true,"contexts":["test","docker"]},
 "enforce_admins":false,
 "required_pull_request_reviews":{"required_approving_review_count":1},
 "restrictions":null}
JSON
```
