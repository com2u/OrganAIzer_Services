---
name: backend-guardian
description: Owns the FastAPI backend — Executive Agent, intent router, integrations/OAuth, services, routers, and the confirmation-gating safety model. Activate when editing backend/api, backend/services, backend/routers, backend/utils, backend/core, or models. Enforces session-state, confirmation, idempotency, and OAuth invariants.
---

# Backend Guardian

Owns the FastAPI application: the Executive Agent brain, deterministic intent
routing, Google/Microsoft integrations, OAuth, and all REST/WS surface except the
phone/FreeSWITCH path (that is `voice-freeswitch-guardian`).

## Purpose

- Protect the confirmation-gated action model (no silent outward writes).
- Keep the in-memory session/state model intact and reload-safe.
- Keep the deterministic intent router ahead of the LLM for control signals.
- Keep OAuth, token storage, and provider resolution correct and secret-safe.

## When to activate

- Editing `backend/api/*` (except `phone.py`, `voice_mode.py` audio path), `backend/services/*`,
  `backend/routers/*`, `backend/utils/*`, `backend/core/*`, `backend/models/*`.
- Changing the Executive Agent, tool definitions, intent router, slot extraction.
- Changing integrations/OAuth, token storage, provider resolution.
- Adding/removing API routes or changing response contracts.

## Files/directories to inspect

- `backend/main.py` — router registration, CORS, lifespan startup.
- `backend/services/executive_agent_service.py` — the agent loop, session dict,
  pending actions, calendar idempotency.
- `backend/services/tool_definitions.py` — callable tool schema.
- `backend/utils/intent_router.py` — pre-LLM deterministic routing + task locking.
- `backend/utils/slot_extraction.py` — email/calendar slot parsing.
- `backend/api/integrations.py` — Google + Microsoft OAuth/Calendar/Mail.
- `backend/utils/token_storage.py`, `backend/config/google_scopes.py`.
- `backend/core/config.py`, `core/logging_config.py`, `core/middleware.py`.
- Tests: `test_executive_agent_safety.py`, `test_calendar_event_creation.py`,
  `test_calendar_intent.py`, `test_email_foundation.py`,
  `test_microsoft_integration.py`, `test_logging_redaction.py`,
  `test_qa_audit_bugs.py`.

## Backend invariants (MUST hold)

1. **Confirmation gating.** `propose_*` tools draft; only `confirm_action`
   executes. Email sends and calendar creates require explicit confirmation;
   deletes require a second confirmation. Never execute an outward write directly
   from an LLM turn.
2. **Idempotent calendar create.** Deterministic SHA-256 `request_id`
   (`user_id|title|start|end|tz`); duplicates return the cached `event_id`. A
   `2xx` response **without** an `event_id` is a FAILURE and must preserve the
   pending action for retry. (See `VOICE_MODE.md` §4.)
3. **Intent router precedes the LLM.** Cancel/confirm/slot/provider-select signals
   are classified deterministically before LLM inference. While a task is
   `collecting`/`awaiting_confirmation`/`drafted` it is **locked** — no topic reset
   or fallback.
4. **Provider resolution order.** Explicit user mention → session-locked provider
   (when exactly one connected) → clarification question. Don't auto-pick when
   both are connected (except the documented Google-default fallback).
5. **In-memory, single-user state.** Sessions live in a process dict; never assume
   persistence. Don't run with `BACKEND_RELOAD=true` for agent work.
6. **Secret-safe logging.** Tokens/keys/PII never logged. `test_logging_redaction.py`
   is the spec.
7. **OAuth scopes are authoritative in code.** Google scopes live in
   `config/google_scopes.py`; Microsoft scopes in the integrations module. Keep
   docs in sync.

## Mandatory checklist BEFORE editing

- [ ] Identify whether the change touches an outward action — if so, the
      confirmation path must remain intact.
- [ ] Read the test that pins the behavior you are changing.
- [ ] If touching response shape, run `change-impact-analysis` (frontend reacts to
      exact `type`/`action_needed` strings).
- [ ] If touching intent routing, map your change against the priority order in
      `ARCHITECTURE.md`.
- [ ] If touching OAuth/scopes, check both `.env.example` files and the scope module.

## Mandatory checklist AFTER editing

- [ ] No new code path executes a send/create/delete without confirmation.
- [ ] Idempotency + truthfulness checks intact for calendar create.
- [ ] Logging redaction tests pass; no new secret/PII reaches logs.
- [ ] Response `type`/`action_needed` values match the frontend + README table.
- [ ] `openapi.json` regenerated if routes/schemas changed (`backend/export_openapi.py`).
- [ ] Relevant docs updated (`README.md`, `ARCHITECTURE.md`, `API_OVERVIEW.md`).

## Validation commands

```bash
# WSL debian12 + .venv-wsl, from backend/:
cd backend
../.venv-wsl/bin/python -m pytest tests/test_executive_agent_safety.py \
  tests/test_calendar_event_creation.py tests/test_calendar_intent.py \
  tests/test_email_foundation.py tests/test_microsoft_integration.py \
  tests/test_logging_redaction.py tests/test_qa_audit_bugs.py -q
# Regenerate OpenAPI after route/schema changes:
../.venv-wsl/bin/python export_openapi.py   # writes openapi.json
```

## Documentation updates required

- `API_OVERVIEW.md` + `openapi.json` for any route/schema change.
- `README.md` `type` → frontend-reaction table for any new/changed response type.
- `ARCHITECTURE.md` for intent-router priority, state-machine, or provider changes.
- `SECURITY.md` for any auth/token/scope change.

## Known repository risks

- Intent router patterns are **English/German keyword-based**; other languages
  fall through to the LLM and silently skip calendar/email tool calls.
- Session + idempotency stores are **in-memory** — restart loses them; not
  multi-instance safe.
- CORS is `allow_origins=["*"]` with `allow_credentials=False` — fine for dev,
  restrict for prod.
- `credentials.json` is auto-built from `GOOGLE_CLIENT_ID/SECRET`; never commit it.

## Forbidden behavior

- Do NOT add a path that sends email, creates/deletes events, or otherwise acts
  outwardly without a tracked pending action + explicit confirmation.
- Do NOT weaken the calendar idempotency or the `2xx`-without-`event_id` failure rule.
- Do NOT log tokens, API keys, OAuth codes, email bodies, or PII.
- Do NOT change a response `type` string without updating the frontend and docs.
- Do NOT widen OAuth scopes without updating `google_scopes.py`/docs and justifying it.
