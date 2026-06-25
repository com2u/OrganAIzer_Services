---
id: backend
type: infrastructure
owner: backend-guardian
status: active
last_reviewed: 2026-06-24
sources:
  - backend/main.py
  - backend/Dockerfile
  - docker-compose.yml
  - backend/core/config.py
  - backend/voice/config.py
---

# Backend (FastAPI)

> One source of truth: this profile references authoritative files. It does not
> restate ports, IPs, env vars, or configuration values.

## Purpose

The FastAPI application that hosts the OrganAIzer API, the Executive Agent, the
provider integrations, and the voice ESL server. It is the central runtime process.

## Responsibilities

- Serve the `/api` routers (registered in `backend/main.py`).
- On startup (`lifespan` in `backend/main.py`): start the voice ESL outbound server
  (`ESLOutboundServer`), prewarm fillers, preload/prewarm the Whisper voice model,
  and run the COMtrexx gateway-registration watchdog.
- Host the Executive Agent and its confirmation-gating safety model.
- Reach the bounded OpenClaw service over the internal network.

## Dependencies

- Python runtime and system packages per `backend/Dockerfile` and
  `backend/requirements.txt` (see ADR 0010).
- FreeSWITCH (voice ESL path) — see `knowledge/infrastructure/freeswitch.md`.
- OpenClaw (internal) — see `knowledge/infrastructure/openclaw.md`.
- External providers (LLM / OAuth) configured via env — see `config.py` sources.

## Consumers

- The frontend web UI (`knowledge/infrastructure/frontend.md`).
- The voice path: FreeSWITCH connects to the backend ESL outbound socket.

## Related ADRs

- ADR 0005 — WSL Debian + `.venv-wsl` is the canonical backend test environment.
- ADR 0009 — Confirmation required for external actions.
- ADR 0010 — Python 3.11 supported runtime.

## Related Procedures

- `knowledge/procedures/backend-validation.md`
- `knowledge/procedures/release-process.md`

## Source of Truth

- `backend/main.py` — router registration and startup `lifespan`.
- `backend/Dockerfile` — image/runtime contract.
- `docker-compose.yml` — published port and service wiring.
- `backend/core/config.py`, `backend/voice/config.py` — settings/env vars.

## Known Limitations

- Executive-Agent sessions and idempotency stores are in-memory and lost on restart
  (not multi-instance safe); running with reload enabled wipes session state.
- No CI workflow exists yet; the safety gate is run manually.
- **Needs Human Confirmation:** any move toward durable session/idempotency storage
  is a direction, not an accepted decision (no ADR).

## Ownership

`backend-guardian`.
