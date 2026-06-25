---
id: release-process
type: procedure
owner: docker-guardian
status: active
last_reviewed: 2026-06-24
sources:
  - deploy.sh
  - setup-deployment.sh
  - docker-compose.yml
  - backend/Dockerfile
  - .claude/skills/docker-guardian/SKILL.md
  - .claude/skills/pipeline-guardian/SKILL.md
---

# Release / deployment process

## When to use

To build and deploy the OrganAIzer Services stack with Docker Compose using the
repository's `deploy.sh` script.

## Prerequisites

- `docker` and Docker Compose (`docker-compose` or `docker compose`) installed —
  `deploy.sh` checks for these and exits if missing.
- A configured `.env` file with no placeholder values — `deploy.sh` refuses to
  deploy if `.env` is missing or still contains placeholders (e.g.
  `your_google_api_key_here`). Secrets are provided at runtime via `.env`, never
  baked into image layers.
- Backend tests green first (see `backend-validation`).

## Steps

1. (First-time setup) Prepare `.env` and deployment config:
   ```bash
   ./setup-deployment.sh
   ```
2. Deploy (fast build, uses cache):
   ```bash
   ./deploy.sh
   ```
   Full cleanup / no-cache rebuild:
   ```bash
   ./deploy.sh --clean
   ```
   `deploy.sh` runs `<compose> down`, `<compose> build`, then `<compose> up -d`.

## Validation

- `deploy.sh` performs a backend health check:
  ```bash
  curl -f http://localhost:5263/health
  ```
- Published ports (authoritative in `docker-compose.yml`): backend `5263:8000`,
  frontend `5264:80`, openclaw (no published ports).

## Expected outcomes

- Backend reports healthy on port `5263` (`deploy.sh`: "Backend is running and
  healthy on port 5263").
- OpenClaw stays bounded (no published ports, read-only, cap-drop — ADR 0006).

## Common failure modes

- **Full `docker compose build` fails at the frontend.** `docker-compose.yml`
  declares `build: ./frontend`, but `frontend/Dockerfile` does **not** exist
  (only `backend/Dockerfile` exists). `deploy.sh` builds all services, so it fails
  until the frontend Dockerfile is added (see `docker-guardian`).
- **`.env` missing or placeholder** — `deploy.sh` exits before building.
- **Backend health check fails** — `deploy.sh` reports the failure and checks logs.

## Recovery

- For image corruption, re-run with `./deploy.sh --clean` (full cleanup, no-cache
  rebuild) — documented in `deploy.sh --help`.
- To build only the working backend image (per `docker-guardian`):
  ```bash
  docker compose build backend
  ```

## Notes

- **Needs Human Confirmation:** the frontend Dockerfile and the production nginx /
  reverse-proxy wiring referenced by the compose stack are not present/complete in
  the repository; full-stack deployment depends on adding them.
- There is no CI workflow yet; the safety gate is manual (see `backend-validation`
  and `pipeline-guardian`).
