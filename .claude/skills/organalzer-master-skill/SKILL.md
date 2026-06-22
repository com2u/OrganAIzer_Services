---
name: organalzer-master-skill
description: Master orchestration skill for the OrganAIzer Services repo. Activate at the start of ANY non-trivial change to route to the correct guardian skill, enforce the shared workflow (impact analysis → edit → validate → doc sync → regression), and apply repo-wide invariants. Read this first whenever you touch backend, frontend, voice, docker, infra/openclaw, docs, or tests.
---

# OrganAIzer Master Skill

The single entry point for working in `OrganAIzer_Services`. It encodes how the
project is *meant* to work, the non-negotiable invariants, and which specialized
skill owns each area. Treat this as the dispatcher: read it, then delegate to the
matching guardian skill below.

## Purpose

- Give every change a consistent lifecycle: **impact → edit → validate → document → regression-check**.
- Hold the repo-wide invariants that no single sub-area owns.
- Route work to the right guardian so domain rules are never skipped.
- Prevent the recurring failure modes this repo is prone to (session-state wipes,
  number/PII leaks, unbounded OpenClaw, drifting FreeSWITCH templates, missing
  Dockerfiles, English-only intent routing).

## When to activate

Activate **before** the first edit in a session whenever the task touches any of:
- `backend/` (API, services, voice, utils, core, models)
- `frontend/`
- `docker-compose.yml`, deploy scripts, `nginx/`, `infra/openclaw/`
- `.env*`, `requirements.txt`, `package.json`
- any `*.md` documentation or `backend/tests/`

If the task is a pure question with no edits, you may answer directly — but still
consult the relevant guardian for accuracy.

## Skill routing map

| If the change touches… | Delegate to |
|---|---|
| Two or more modules, or you are unsure of blast radius | `change-impact-analysis` (run FIRST) |
| CI, build/test pipeline, lint, release gating, `requirements.txt`/`package.json` versions | `pipeline-guardian` |
| `docker-compose.yml`, Dockerfiles, `nginx/`, `deploy.sh`, `setup-deployment.sh`, container security | `docker-guardian` |
| `backend/api/*`, `backend/services/*`, `backend/routers/*`, executive agent, integrations, OAuth | `backend-guardian` |
| `backend/voice/*`, FreeSWITCH XML, ESL, COMtrexx, phone, STT/TTS pipeline, escalation | `voice-freeswitch-guardian` |
| Any user-facing behavior, endpoint, env var, or protocol change | `documentation-sync` |
| `infra/openclaw/*`, `backend/services/openclaw_client.py`, `backend/api/openclaw.py` | `docker-guardian` + `backend-guardian` (OpenClaw bounded-access rules) |
| Adding/changing tests, or any change to safety-critical behavior | `regression-protection` |

Most real changes invoke **two or more** of these. Always finish with
`documentation-sync` and `regression-protection`.

## Files/directories to inspect first

- `README.md`, `ARCHITECTURE.md`, `API_OVERVIEW.md`, `DEVELOPER_GUIDE.md` — intended design
- `VOICE_MODE.md`, `backend/voice/freeswitch/README.md` — voice topology
- `SECURITY.md` — secret-handling rules
- `docker-compose.yml`, `deploy.sh` — runtime topology
- `backend/main.py` — router registration + startup lifespan (ESL server, watchdogs, Whisper preload)
- `backend/tests/` — the executable spec for safety behavior

## Repo-wide invariants (NEVER violate)

1. **Single user, in-memory session state.** Executive Agent sessions live in a
   process-level dict and are lost on restart. Never run the backend with
   `BACKEND_RELOAD=true` for voice/agent work — it wipes session state, resets
   pending actions, and forces a ~slow Whisper reload. See `backend/main.py:287`.
2. **Confirmation gating is sacred.** Email sends and calendar creates require
   explicit user confirmation; deletes require a second confirmation. Never add a
   path that executes an outward action without a tracked pending-action +
   confirmation. (`backend-guardian`)
3. **No PII / secret leakage in logs.** Phone numbers must be masked
   (`voice/call_trigger.mask_number`), tokens/keys redacted. `test_logging_redaction.py`
   and `test_phone_safety.py` are the spec.
4. **German-only outbound calls.** `is_german_number` gates dialing; the raw
   number lives only in process memory, never logged or returned. (`voice-freeswitch-guardian`)
5. **OpenClaw stays bounded.** No exposed ports, `read_only: true`, `cap_drop: ALL`,
   `no-new-privileges:true`, volume bound only to `./infra/openclaw/openclaw-data`,
   and the tool deny-list intact. `test_openclaw_safety.py` is the spec. (`docker-guardian`)
6. **Secrets never committed.** `.env`, `credentials.json`, token files, SIP
   passwords stay out of git. FreeSWITCH XML in the repo are *templates* with
   placeholders. See `SECURITY.md`.
7. **Voice prompt layering.** Layer 1 (core behavior in `llm_bridge.py`) must stay
   client-agnostic; per-client values go in `config.py` env vars (Layer 2) and the
   knowledge markdown (Layer 3). Never hardcode a client into Layer 1.
8. **Idempotency for outward writes.** Calendar creation uses a deterministic
   SHA-256 `request_id`; a 2xx without an `event_id` is treated as failure. Do not
   weaken this.

## Mandatory checklist BEFORE editing

- [ ] Read this skill + the guardian(s) the routing map points to.
- [ ] Run `change-impact-analysis` if the change spans modules or is safety-relevant.
- [ ] Identify which invariants above the change could affect.
- [ ] Locate the test(s) that pin the current behavior (`backend/tests/`).
- [ ] Confirm you are NOT about to introduce a Windows-Python test run (tests run in WSL — see `pipeline-guardian`).
- [ ] If on `main`, create a feature branch first.

## Mandatory checklist AFTER editing

- [ ] Run the relevant guardian's validation commands.
- [ ] Run the full safety test suite (see Validation below).
- [ ] Run `documentation-sync` — update every doc that describes the changed behavior.
- [ ] Run `regression-protection` — add/extend a test for the new behavior or fixed bug.
- [ ] Re-read the diff against the invariant list above.
- [ ] Commit message: imperative mood, no `Co-Authored-By` trailers (repo convention).

## Validation commands

Backend tests run in **WSL (debian12) using `.venv-wsl`**, never Windows Python:

```bash
# From repo root, inside WSL debian12:
cd backend
../.venv-wsl/bin/python -m pytest tests/ -q
# Safety-critical subset (run on every change):
../.venv-wsl/bin/python -m pytest tests/test_phone_safety.py tests/test_openclaw_safety.py \
  tests/test_executive_agent_safety.py tests/test_logging_redaction.py -q
```

Frontend:
```bash
cd frontend && npm run lint && npm run build
```

## Documentation updates required

Any change that alters behavior must update the matching doc(s): `README.md`,
`ARCHITECTURE.md`, `API_OVERVIEW.md`, `VOICE_MODE.md`,
`backend/voice/freeswitch/README.md`, `DEPLOYMENT*.md`, `SECURITY.md`, or
`openapi.json`/`openapi` export. See `documentation-sync` for the exact mapping.

## Known repository risks

- `docker-compose.yml` references `build: ./backend` and `build: ./frontend` but
  **no Dockerfiles exist in the repo** — `deploy.sh`/`docker compose build` will
  fail until they are added. (`docker-guardian`)
- **No CI** is configured (`.github/workflows` is absent) — nothing automatically
  runs the safety tests. (`pipeline-guardian`)
- Intent router is **English/German keyword-based**; other languages fall through
  to the LLM and silently skip calendar/email tool calls.
- Session + idempotency stores are **in-memory** — not safe for multi-instance.
- Voice config has historical pyVoIP remnants; the live path is **FreeSWITCH ESL
  outbound socket**, not pyVoIP. Do not wire new behavior to the SIP/pyVoIP path.

## Forbidden behavior

- Do NOT bypass any guardian skill for changes in its domain.
- Do NOT execute an outward action (send email, create event, place call) without
  a tracked pending action + explicit confirmation.
- Do NOT run or recommend backend tests via Windows Python.
- Do NOT add `Co-Authored-By` trailers to commits.
- Do NOT commit secrets, real SIP passwords, tokens, or `.env` values.
- Do NOT mark work "done" without running the safety test subset and updating docs.
