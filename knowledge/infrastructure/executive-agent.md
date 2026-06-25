---
id: executive-agent
type: infrastructure
owner: backend-guardian
status: active
last_reviewed: 2026-06-24
sources:
  - backend/services/executive_agent_service.py
  - backend/services/tool_definitions.py
  - backend/api/executive_agent.py
---

# Executive Agent

> References authoritative sources; does not restate configuration values.

## Purpose

The conversational agent that performs calendar and email actions through tools,
with explicit confirmation before any outward write.

## Responsibilities

- Maintain per-session conversation memory and pending actions
  (`ConversationMemory` in `executive_agent_service.py`).
- Gate outward actions: a `propose_*` tool records a pending action and returns a
  confirmation request; execution against the real provider API happens only on
  explicit confirmation (ADR 0009).
- Dispatch the tool set defined in `tool_definitions.py`
  (`CONFIRMATION_REQUIRED_TOOLS`).

## Dependencies

- The backend runtime — see `knowledge/infrastructure/backend.md`.
- The chat/LLM service used to drive reasoning.
- OAuth provider connections (calendar/email), via the integrations layer.

## Consumers

- The frontend Executive Agent UI and API clients (`backend/api/executive_agent.py`).

## Related ADRs

- ADR 0009 — Confirmation required for external actions.
- ADR 0005 — WSL Debian + `.venv-wsl` is the canonical backend test environment.

## Related Procedures

- `knowledge/procedures/backend-validation.md`

## Source of Truth

- `backend/services/executive_agent_service.py` — session memory, pending actions,
  confirmation flow.
- `backend/services/tool_definitions.py` — tool set and `CONFIRMATION_REQUIRED_TOOLS`.
- `backend/api/executive_agent.py` — session endpoints.

## Known Limitations

- Sessions and idempotency stores are in-memory, single-user, and lost on restart;
  not multi-instance safe.
- **Needs Human Confirmation:** a durable session/idempotency store is a future
  direction, not an accepted decision (no ADR).

## Ownership

`backend-guardian`.
