# Demo script

## Before the demo (5 minutes)

```bash
cp backend/.env.example backend/.env
# in backend/.env set DJANGO_SECRET_KEY to any long random string and DEMO_SOURCES=1
docker compose up --build -d
docker compose exec web python manage.py seed_demo
```

Open three tabs: http://localhost:5173 (app), http://localhost:8025 (Mailpit) and the GitHub repo
(Actions tab). Run `seed_demo` again right before presenting so the data is fresh.

Log in as **demo@dnd.test / Demo!2026**.

## 15-minute final demo

| Time | Show | Say | Who |
|---|---|---|---|
| 0:00 | Title slide | Problem, scope (Project 16), team | |
| 1:00 | Architecture diagram | Layered design; adapters behind `IJobSource` / `IApplyChannel` | |
| 2:00 | **Profile**: upload a resume, edit a skill, Save, Get tips | REQ-1 to 4; profile optimisation from the scope | |
| 3:30 | **Job feed**: scores, "Also on Naukri", filters, Search now | REQ-5 to 8: weighted score, de-duplication, run in parallel | |
| 5:00 | **Apply** on the Northwind LinkedIn job: kit tabs, Open posting, I've applied | Assisted apply, and *why* (LinkedIn terms) | |
| 6:00 | **Apply** on "Hiring: Backend Engineer" (X) by email, tick confirm, send; switch to Mailpit | REQ-10 confirmation; the real email with resume attached | |
| 7:00 | **Apply** on "SDE 1 - Backend" (Greenhouse); show the failure reason; **Review** tab | Career-page channel; failures and CAPTCHA stops are never silent (REQ-12, 13) | |
| 8:00 | **Outreach**: Ananya, draft, edit, I've sent it; then paste the same text to Karthik | REQ-14 to 17: personalised, capped, identical text blocked | |
| 9:30 | **Analytics**: KPIs, keyword yield, log an interview, change a status, Export CSV | REQ-21 to 24 | |
| 11:00 | **Settings**: Pause All, then Search now on the feed is refused; schedule; limits | SRS 6.2 safety, REQ-11, 16, 18 to 20 | |
| 12:00 | GitHub: Actions run, coverage, SonarQube, Jira/Project board | CI/CD, 265 tests, 96% coverage, process | |
| 13:00 | `docs/deviations.md` | What changed from the SRS and why | |
| 14:00 | Questions | | |

## 2-minute Sprint video

0:00 log in → 0:15 profile upload → 0:30 feed and Search now → 0:50 assisted apply → 1:10 email apply and
Mailpit → 1:30 analytics → 1:45 Pause All → 2:00 end. Record with OBS or the Windows Game Bar (Win+G) at
1280×720, then commit the file to `docs/videos/`.

## Questions you may be asked

* **Why not auto-apply on LinkedIn?** No public API; bots break the terms of service and risk bans. Assisted
  apply keeps the user in control and is still tracked.
* **How is relevance scored?** Skills 50, role 30, location 10, experience 10; skills in the title count double
  (`matching/scoring.py`).
* **How are duplicates found?** Normalised title and company are hashed; later copies attach to the first.
* **How are credentials protected?** Argon2 passwords, 30-minute JWTs, AES-256-GCM for stored tokens and
  mailbox passwords, write-only in the API.
* **What happens at 90% of a rate limit?** The action is deferred to the next window (`scheduler/ratelimit.py`).
