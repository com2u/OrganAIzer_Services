---
id: 0006-openclaw-must-remain-bounded
type: decision
owner: docker-guardian
status: accepted
last_reviewed: 2026-06-24
sources:
  - backend/tests/test_openclaw_safety.py
  - docker-compose.yml
  - infra/openclaw/openclaw-data/openclaw.json
  - .claude/skills/docker-guardian/SKILL.md
---

# 0006 — OpenClaw must remain bounded

## Status

Accepted.

## Context

OpenClaw is a containerized automation service in the compose stack. Its
least-privilege bounds are asserted by `test_openclaw_safety.py`.

## Decision

OpenClaw remains bounded: no exposed ports, `read_only` filesystem,
`cap_drop: [ALL]`, `no-new-privileges`, a single data volume bound to
`infra/openclaw/openclaw-data`, and a minimal tool profile with a deny-list
(no unrestricted filesystem access, no unrestricted execution). The backend reaches
it only via the internal gateway URL with a token, and only the approved
`/cleanup` and `/summarize` workflows are used.

## Reasoning

This is the repository's strongest container security boundary. The bounds are
enforced as an executable spec by `test_openclaw_safety.py`; loosening them
requires a deliberate, justified test change.

## Consequences

- Any change that adds ports, a broader volume/socket mount, or removes the
  hardening flags must update `test_openclaw_safety.py` with justification.
- The OpenClaw service is reachable only on the internal network.

## Related Sources

- `backend/tests/test_openclaw_safety.py` — the executable spec.
- `docker-compose.yml` — `openclaw` service definition.
- `infra/openclaw/openclaw-data/openclaw.json` — tool profile + deny-list.
- `.claude/skills/docker-guardian/SKILL.md` — OpenClaw bounded-access contract.
