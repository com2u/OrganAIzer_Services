---
id: frontend
type: infrastructure
owner: frontend-guardian
status: active
last_reviewed: 2026-06-24
sources:
  - frontend/package.json
  - frontend/vite.config.ts
  - docker-compose.yml
---

# Frontend (React / Vite web UI)

> References authoritative sources; does not restate ports, env vars, or build args.

## Purpose

The web user interface for OrganAIzer, built with React and Vite and (per the
compose stack) served by nginx.

## Responsibilities

- Provide the UI pages/tabs and the Executive Agent / voice UI.
- Call the backend API and handle the frontend/backend contract (including any
  WebSocket UI behavior).
- Build a static bundle for deployment.

## Dependencies

- The backend API — see `knowledge/infrastructure/backend.md`.
- React and Vite toolchain (versions in `frontend/package.json`).
- The compose build/serve wiring (`docker-compose.yml`, `build: ./frontend`).

## Consumers

- End users (browser).

## Related ADRs

- None directly recorded. (Runtime/build constraints relevant to deployment are
  tracked under the backend/Docker ADRs and the docker-guardian skill.)

## Related Procedures

- `knowledge/procedures/release-process.md`
- `knowledge/procedures/backend-validation.md` (frontend lint/build steps).

## Source of Truth

- `frontend/package.json` — scripts and dependency versions.
- `frontend/vite.config.ts` — build configuration.
- `docker-compose.yml` — published port and build context.

## Known Limitations

- `frontend/Dockerfile` does **not** exist, while `docker-compose.yml` declares
  `build: ./frontend`. A full `docker compose build` / `deploy.sh` fails until it is
  added (see the docker-guardian skill and `release-process`).
- **Needs Human Confirmation:** the production nginx/reverse-proxy serving wiring is
  referenced by compose but not fully present in the repository.

## Ownership

`frontend-guardian`.
