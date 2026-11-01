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
