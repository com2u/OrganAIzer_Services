---
name: docker-guardian
description: Owns containerization, compose topology, nginx, deploy scripts, and the bounded OpenClaw container security model. Activate when touching docker-compose.yml, Dockerfiles, nginx config, deploy.sh/setup-deployment.sh, or infra/openclaw. Enforces the OpenClaw hardening contract asserted by test_openclaw_safety.py.
---

# Docker Guardian

Owns how OrganAIzer Services is packaged and deployed: the compose stack
(backend + frontend + OpenClaw), nginx reverse proxy, deploy scripts, and the
**bounded OpenClaw container** whose hardening is asserted by tests.

## Purpose

- Keep the compose topology coherent and buildable.
- Enforce the OpenClaw least-privilege contract (the repo's strongest container
  security boundary).
- Keep deploy scripts, ports, and nginx config in sync with the compose file.

## When to activate

- Editing `docker-compose.yml`, any `Dockerfile`, `.dockerignore`.
- Editing `nginx/`, `frontend/nginx.conf`, `deploy.sh`, `setup-deployment.sh`.
- Editing `infra/openclaw/openclaw-data/openclaw.json` or the OpenClaw service.
- Changing exposed ports, volumes, healthchecks, or container env wiring.

## Files/directories to inspect

- `docker-compose.yml` — backend (`5263:8000`), frontend (`5264:80`), openclaw (no ports).
- `infra/openclaw/openclaw-data/openclaw.json` — gateway + tool deny-list (JSON5).
- `backend/tests/test_openclaw_safety.py` — the executable spec for the bounds.
- `nginx/conf.d/`, `frontend/nginx.conf` — reverse proxy + WS upgrade headers.
- `deploy.sh`, `setup-deployment.sh`, `README-DOCKER.md`, `DEPLOYMENT*.md`.
- `backend/services/openclaw_client.py`, `backend/api/openclaw.py` — the only
  callers of OpenClaw (`/cleanup`, `/summarize`).

## OpenClaw bounded-access contract (MUST hold)

`test_openclaw_safety.py` asserts all of these on the `openclaw` service:
- **No exposed ports** (`ports:` absent — reachable only on the internal network).
- **Volume bound to exactly** `./infra/openclaw/openclaw-data:/home/node/.openclaw`.
  No Docker socket mount, no repo-root mount, no extra host paths.
- `read_only: true`, `cap_drop: [ALL]`, `security_opt: [no-new-privileges:true]`.
- `tmpfs` for `/tmp`, `/var/tmp`, `/home/node/.cache` (writable scratch only).
- `openclaw.json` `tools.profile: "minimal"` and `tools.deny` includes
  `browser`, `cron`, `heartbeat`, `channels`, `runtime`, `filesystem`.
- Backend reaches it only via `OPENCLAW_BASE_URL=http://openclaw:18789` with
  `OPENCLAW_GATEWAY_TOKEN` auth; API router exposes only `/cleanup` and `/summarize`.

Any edit that loosens these must be rejected unless the test is deliberately and
explicitly updated with justification.

## Mandatory checklist BEFORE editing

- [ ] Read `test_openclaw_safety.py` to know exactly what is asserted.
- [ ] Note current published ports; check for collisions before adding/changing.
- [ ] Confirm whether the change needs a matching nginx/deploy-script update.
- [ ] For OpenClaw changes, confirm the new capability is genuinely required
      (default posture is deny).

## Mandatory checklist AFTER editing

- [ ] `docker compose config` parses (no YAML/interpolation errors).
- [ ] OpenClaw safety tests still pass (see Validation).
- [ ] Ports in `docker-compose.yml`, `deploy.sh`, nginx, and docs all agree.
- [ ] Healthchecks still target valid endpoints (`/health` for backend, `/` for frontend).
- [ ] `README-DOCKER.md` / `DEPLOYMENT*.md` updated for any topology change.

## Validation commands

```bash
# Compose validity:
docker compose config >/dev/null && echo "compose OK"

# OpenClaw bounds (WSL debian12, .venv-wsl):
cd backend && ../.venv-wsl/bin/python -m pytest tests/test_openclaw_safety.py -q

# Build (will FAIL until Dockerfiles exist — see risks):
docker compose build
```

## Documentation updates required

- `README-DOCKER.md` and `DEPLOYMENT.md` / `DEPLOYMENT-EXISTING-NGINX.md` for any
  port, volume, service, or nginx change.
- `SECURITY.md` if the security posture of any container changes.
- `docker-compose.yml` comments for any non-obvious security setting.

## Known repository risks

- **Missing Dockerfiles (high):** `docker-compose.yml` declares `build: ./backend`
  and `build: ./frontend`, but no `backend/Dockerfile` or `frontend/Dockerfile`
  exists. `docker compose build` and `deploy.sh` will fail until they are created.
  When adding them: backend needs `ffmpeg` on PATH (voice) and Python 3.10/3.11
  (not 3.13); frontend is a Vite build served by nginx with the `VITE_API_KEY`
  build arg and WS-upgrade proxy headers.
- `openclaw.json` is **JSON5** (unquoted keys, `//` comments) — `json.load` fails;
  the test reads it as raw text. Keep it JSON5 and keep the deny strings literal.
- The OpenClaw `openclaw-data` volume contains a large npm cache and session
  state — do not delete or relocate it casually; the volume binding is asserted.
- CORS is `allow_origins=["*"]` in `backend/main.py`; production deploys are
  expected to restrict origin at nginx/backend.

## Forbidden behavior

- Do NOT add `ports:`, a Docker socket mount, or a repo-root volume to the
  OpenClaw service.
- Do NOT remove `read_only`, `cap_drop: ALL`, `no-new-privileges`, or tmpfs from
  OpenClaw.
- Do NOT remove entries from the OpenClaw `tools.deny` list without explicit need
  and a corresponding test update.
- Do NOT change a published port in compose without updating deploy scripts,
  nginx, and docs.
- Do NOT commit real secrets into compose/env; use `.env` + `env_file`.
