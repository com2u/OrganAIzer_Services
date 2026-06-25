---
id: openclaw
type: infrastructure
owner: docker-guardian
status: active
last_reviewed: 2026-06-24
sources:
  - docker-compose.yml
  - infra/openclaw/openclaw-data/openclaw.json
  - backend/tests/test_openclaw_safety.py
  - backend/services/openclaw_client.py
  - backend/api/openclaw.py
---

# OpenClaw (bounded automation container)

> References authoritative sources; does not restate ports, volumes, tokens, or
> tool lists (those live in the compose file, `openclaw.json`, and the safety test).

## Purpose

A bounded, least-privilege automation container the backend uses for a small set of
approved workflows.

## Responsibilities

- Run only approved tools/workflows within a hardened container.
- Remain reachable only on the internal network via the gateway, authenticated with
  a token.
- Hold its state in the single bound data volume.

## Dependencies

- The Docker Compose stack and internal network — see
  `knowledge/infrastructure/backend.md` and the compose file.
- The `infra/openclaw/openclaw-data` volume and the tool profile in `openclaw.json`.

## Consumers

- The backend, via `backend/services/openclaw_client.py` and `backend/api/openclaw.py`
  (the approved `/cleanup` and `/summarize` workflows).

## Related ADRs

- ADR 0006 — OpenClaw must remain bounded.

## Related Procedures

- `knowledge/procedures/release-process.md`
- `knowledge/procedures/backend-validation.md` (runs `test_openclaw_safety.py`).

## Source of Truth

- `docker-compose.yml` — the `openclaw` service definition (bounds, volume, no
  published ports).
- `infra/openclaw/openclaw-data/openclaw.json` — tool profile and deny-list.
- `backend/tests/test_openclaw_safety.py` — the executable spec for the bounds.

## Known Limitations

- The least-privilege bounds are enforced as an executable spec; any loosening must
  be a deliberate, justified change to `test_openclaw_safety.py`.

## Ownership

`docker-guardian`.
