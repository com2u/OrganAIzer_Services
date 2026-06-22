---
name: change-impact-analysis
description: Run this BEFORE editing whenever a change could affect more than one module of OrganAIzer Services, or touches safety-critical behavior (voice, phone, OpenClaw, OAuth, confirmation gating, logging). Maps the blast radius of a change across backend, frontend, voice, docker, infra, docs, and tests so nothing downstream silently breaks.
---

# Change Impact Analysis

OrganAIzer Services is tightly coupled across layers: a backend response `type`
drives a specific frontend reaction, a voice config value drives FreeSWITCH
dialplan behavior, a docker setting is asserted by a safety test. This skill
forces a deliberate blast-radius assessment before any cross-cutting edit.

## Purpose

- Surface every consumer of the thing you are about to change.
- Catch contract breaks (API response shapes, WS message types, env var names,
  ESL ports, OAuth scopes) before they ship.
- Decide which guardian skills, tests, and docs the change pulls in.

## When to activate

- Any change spanning two or more directories.
- Any change to a **contract**: API response `type`/`action_needed`, voice WS
  message types, ESL ports/hosts, env var names, OAuth scopes, OpenClaw config.
- Any safety-critical edit (phone, OpenClaw, confirmation flow, logging, escalation).
- Before renaming/moving a symbol used across modules.
- Whenever the master skill routes you here.

## Files/directories to inspect

Trace the change through these contract boundaries:

1. **Backend → Frontend response contract**
   - `backend/api/executive_agent.py` response `type` / `action_needed` values
   - `frontend/src/components/ExecutiveAgent.tsx`, `VoiceExecutiveAgent.tsx`
   - `frontend/src/lib/api.ts` (typed fetch wrapper)
   - The `type` → frontend-reaction table in `README.md`
2. **Voice WS contract**
   - `backend/api/voice_mode.py` ↔ `VOICE_MODE.md` (client→server / server→client message tables)
3. **Voice config → FreeSWITCH**
   - `backend/voice/config.py` env vars ↔ `backend/voice/freeswitch/*.xml` ↔ `freeswitch/README.md` address table
4. **Env var surface**
   - `.env.example`, `backend/.env.example`, `frontend/.env.example`, `core/config.py`, `voice/config.py`
5. **Router registration**
   - `backend/main.py` `include_router(...)` prefixes ↔ `API_OVERVIEW.md` / `openapi.json`
6. **OpenClaw bounded contract**
   - `docker-compose.yml` openclaw service ↔ `infra/openclaw/openclaw-data/openclaw.json` ↔ `backend/api/openclaw.py` ↔ `test_openclaw_safety.py`
7. **Tests that assert the behavior**
   - `backend/tests/` — find the test whose name matches your area.

## Mandatory checklist BEFORE editing

- [ ] Grep for every reference to the symbol/value/route you are changing
      (e.g. `Grep` for the env var name, response `type` string, ESL port).
- [ ] List the consumers found, grouped by layer (backend/frontend/voice/infra/docs/tests).
- [ ] For each consumer, decide: unaffected / needs update / needs a new test.
- [ ] Confirm which invariants from `organalzer-master-skill` are in scope.
- [ ] Identify the test(s) that currently pin the behavior — they must stay green
      or be updated deliberately.
- [ ] Produce a short written impact summary before touching code.

## Mandatory checklist AFTER editing

- [ ] Every consumer identified above is either updated or confirmed unaffected.
- [ ] No contract value was changed in one layer but not its mirror (env var,
      response `type`, WS message type, ESL port, OAuth scope).
- [ ] All pinning tests pass; new behavior has a new/updated test.
- [ ] `documentation-sync` run for every doc touching the changed contract.

## Validation commands

```bash
# Find all consumers of a contract value (run from repo root):
#   Grep tool with the literal string — e.g. an env var or response "type".
# Then run the impacted tests in WSL:
cd backend && ../.venv-wsl/bin/python -m pytest tests/ -q
```

For frontend contract changes also run:
```bash
cd frontend && npm run build   # tsc -b surfaces type/contract breaks
```

## Documentation updates required

Update the doc that *documents the contract* you changed — not just the nearest
README. Cross-reference `documentation-sync` for the file mapping. A contract is
not changed until its table/spec in docs matches the code.

## Known repository risks

- Many contracts are duplicated across **three places** (code, docs, tests) and
  can silently drift — e.g. ESL addresses appear in `config.py`, the XML files,
  and `freeswitch/README.md`.
- Frontend reacts to exact `type` strings; a typo'd/renamed `type` fails silently
  (falls to a generic branch) rather than erroring.
- Env var renames must be mirrored in **all** `.env.example` files or deploys break
  with confusing defaults.

## Forbidden behavior

- Do NOT edit a contract value in one layer and stop. Update or verify every mirror.
- Do NOT skip the impact summary for safety-critical or cross-module changes.
- Do NOT assume a value is unused because the local file does not reference it —
  grep the whole repo (and the XML/docs).
