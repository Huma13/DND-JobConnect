# Deviations from the submitted documents

The Part-2 deliverables ask for deviations from the SRS, the SW Architecture document (SAD) and the Project
Test Plan to be documented and explained at the final demo. Each entry says what changed, why, and where to
see it.

## 1. Applying on LinkedIn and Naukri is assisted, not automated

| | |
|---|---|
| Documents | SRS REQ-9 and REQ-10 described automated form filling and submission on every platform. |
| What we built | Three channels (SAD v1.0 section 2.1): **assisted apply** for LinkedIn and Naukri, **career-page apply** for Greenhouse and Lever, and **email apply**. |
| Why | LinkedIn and Naukri offer no public application API, and their terms of service forbid bots that submit applications. Automating them would risk the user's account being banned. |
| Where | `applications/views.py` (`method=manual`), the web app's Apply dialog, which shows the tailored kit, opens the posting and records "I've applied". |

## 2. LinkedIn outreach is sent by the user

| | |
|---|---|
| Documents | REQ-14 to REQ-16 implied automated connection requests. |
| What we built | The app suggests the recruiter, drafts a personalised note and opens their profile; the user sends it and marks it sent. X messages are sent through the official API. |
| Why | Same terms-of-service reason as above. Limits (REQ-16) and the identical-message block (REQ-17) still apply. |

## 3. Demo sources instead of live LinkedIn and Naukri listings

| | |
|---|---|
| Documents | SRS 3.2 assumed the public listing pages could be read. |
| What we built | The collector honours robots.txt by default. LinkedIn's and Naukri's robots.txt disallow those paths, so in compliant mode those sources report an error in the run log. X search needs a paid API token. For demos, `DEMO_SOURCES=1` serves recorded postings through the same `IJobSource` interface. |
| Why | Respecting robots.txt and platform terms. The parsers are still tested against saved pages. |
| Where | `integrations/demo.py`, `integrations/demo_data/postings.json`, `python manage.py seed_demo`. |

## 4. CI/CD runs on GitHub Actions, not Jenkins

| | |
|---|---|
| Documents | The Test Plan and SAD named Jenkins, as in the Jackfruit guidelines. |
| What we built | `.github/workflows/ci.yml`: ruff, migration check, pytest with an 85% line-and-branch coverage gate, SonarQube quality gate, frontend lint and build, Docker build, and publishing the image on merge to `main`. OWASP ZAP runs in `zap.yml`. |
| Why | The Part-2 deliverables ask for GitHub Actions specifically, and it needs no server to host. The pipeline stages are the ones the Test Plan lists. |

## 5. Two sprints, not four

| | |
|---|---|
| Documents | The Test Plan and Jira backlog planned four two-week sprints. |
| What we did | The course schedule fixed two one-week sprints (Part-2 deliverables). Stories were regrouped into those two sprints. See `docs/retrospectives.md` for what each delivered and when. |

## 6. Additions not in the SRS

* **Log an employer reply or interview** (`POST /api/applications/{id}/responses/`). REQ-22/23 need these
  events for the response rate, but the SRS gave no way to record them except the admin panel.
* **Recruiters from merged duplicates.** When a job is found on several platforms, contacts named in any copy
  are suggested (REQ-7 combined with REQ-14).
* **Profile tips default to the user's own data** (profile and top feed postings), so the tips need no input.
* **Mailpit** in docker-compose catches email applications and notification emails during development and demos.

## 7. Things the SRS asked for that need credentials we do not have

| Feature | Needs | Behaviour without it |
|---|---|---|
| X job search and X messages | `X_BEARER_TOKEN`, X API keys (paid tier) | Clear error in the run log or on the message; demo sources cover search |
| Greenhouse and Lever submission | `GREENHOUSE_API_KEY`, `LEVER_API_KEY` from the employer | Application marked failed with the reason, shown in the Review screen |
