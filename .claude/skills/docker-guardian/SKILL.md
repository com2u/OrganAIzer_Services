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
- `backend/Dockerfile` — Python 3.11-slim backend image (exists). `backend/.dockerignore`.
- `frontend/Dockerfile` — **does not exist yet** (compose declares `build: ./frontend`).
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

## Backend image contract (MUST hold)

`backend/Dockerfile` packages the FastAPI/voice backend. Keep these properties:

- **Python 3.11** (`FROM python:3.11-slim`). Do NOT bump to 3.13 — `openai-whisper`/
  `torch` have no 3.13 support and `pyVoIP==1.6.4` uses `audioop` (removed in 3.13).
  Mirrors the `pipeline-guardian` version pins.
- **`ffmpeg` on PATH** — required by voice mode (webm/opus → 16 kHz WAV for Whisper).
- **`curl` on PATH** — the compose healthcheck is `curl -f http://localhost:8000/health`.
  The healthcheck lives in `docker-compose.yml`, not as a `HEALTHCHECK` line in the
  Dockerfile; if you move it into the image, keep `curl` (or use an equivalent).
- **No secrets in image layers.** `backend/.dockerignore` must keep `.env`/`.env.*`
  (except `.env.example`), `credentials.json`, `token*.json`, `data/tokens/`,
  virtualenvs, caches, and runtime data (`data/esl_audio`, `data/tts`, logs) out of
  the build context. `COPY . .` relies on it — never weaken it. Secrets arrive at
  runtime via `.env` + `env_file`, never baked in.
- **Layer caching:** `COPY requirements.txt` + install before `COPY . .`.
- **Run command:** `uvicorn main:app` with **no `--reload`** (reload wipes
  in-memory session state and forces a slow Whisper reload; see `backend/main.py`).

## Mandatory checklist BEFORE editing

- [ ] Read `test_openclaw_safety.py` to know exactly what is asserted.
- [ ] Note current published ports; check for collisions before adding/changing.
- [ ] Confirm whether the change needs a matching nginx/deploy-script update.
- [ ] For OpenClaw changes, confirm the new capability is genuinely required
      (default posture is deny).

## Mandatory checklist AFTER editing

- [ ] `docker compose config` parses (no YAML/interpolation errors).
- [ ] `docker compose build backend` succeeds (and `frontend` once its Dockerfile exists).
- [ ] `.dockerignore` still excludes `.env*`, `credentials.json`, `token*.json`,
      `data/tokens/`, venvs, caches, and runtime data — no secrets in layers.
- [ ] Backend image still has `ffmpeg` + `curl` and stays on Python 3.11.
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

# Build the backend image (exists today):
docker compose build backend
# Full build — FAILS until frontend/Dockerfile is added (see risks):
docker compose build
```

## Documentation updates required

- `README-DOCKER.md` and `DEPLOYMENT.md` / `DEPLOYMENT-EXISTING-NGINX.md` for any
  port, volume, service, or nginx change.
- `SECURITY.md` if the security posture of any container changes.
- `docker-compose.yml` comments for any non-obvious security setting.

## Known repository risks

- **Frontend Dockerfile still missing (high):** `backend/Dockerfile` now exists
  (Python 3.11-slim, ffmpeg + curl), but `frontend/Dockerfile` does **not**, while
  `docker-compose.yml` declares `build: ./frontend`. A full `docker compose build`
  and `deploy.sh` still fail until it is added. When adding it: a Vite build served
  by nginx with the `VITE_API_KEY` build arg and WS-upgrade proxy headers; keep
  `curl` available for the `curl -f http://localhost/` healthcheck.
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
