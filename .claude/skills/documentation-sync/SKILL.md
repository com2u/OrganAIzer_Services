---
name: documentation-sync
description: Keeps OrganAIzer Services documentation in lockstep with code. Activate after ANY behavior, endpoint, env var, protocol, topology, or security change. Maps each kind of change to the exact docs that must be updated, and treats docs as part of the contract — a change is not done until its docs match.
---

# Documentation Sync

This repo documents its contracts in markdown that is frequently duplicated across
code, docs, and tests. Documentation here is normative, not decorative: the
README's response-`type` table, VOICE_MODE's WS protocol, and the FreeSWITCH
address table are relied on by humans and by impact analysis. Keep them true.

## Purpose

- Ensure every behavior/contract change is reflected in the owning document.
- Prevent silent drift between code and the tables/specs that describe it.
- Keep `openapi.json` and `.env.example` files synchronized with code.

## When to activate

- After any change to an API route, response shape, or WS message.
- After any env var add/rename/default change.
- After any voice topology, ESL address, dialplan, or escalation change.
- After any security posture, OAuth scope, or container hardening change.
- As the closing step of essentially every guardian skill.

## Change → document mapping

| Change | Update |
|---|---|
| API route / response `type` / `action_needed` | `API_OVERVIEW.md`, `openapi.json` (via `backend/export_openapi.py`), README `type`→reaction table, `ARCHITECTURE.md` |
| Executive Agent / intent router / state machine | `ARCHITECTURE.md`, `README.md` Executive Agent section |
| Voice WS protocol / idempotency / pipeline | `VOICE_MODE.md` |
| FreeSWITCH topology / ESL ports / dialplan / addresses | `backend/voice/freeswitch/README.md` |
| Voice env vars / company layers | `backend/voice/config.py` docstrings + `.env.example` |
| Any new/renamed env var | `.env.example`, `backend/.env.example`, `frontend/.env.example` (as applicable), `README.md` env section |
| OAuth scopes / auth / tokens / secrets | `SECURITY.md`, `MICROSOFT_VERIFY.md`, README integration section |
| Docker/compose/nginx/ports/deploy | `README-DOCKER.md`, `DEPLOYMENT.md`, `DEPLOYMENT-EXISTING-NGINX.md`, `SETUP-GUIDE.md` |
| New dependency / prerequisite | `README.md` prerequisites, `DEVELOPER_GUIDE.md` |
| OpenClaw bounds | `docker-compose.yml` comments, `SECURITY.md` |

## Files/directories to inspect

Root docs: `README.md`, `ARCHITECTURE.md`, `API_OVERVIEW.md`, `DEVELOPER_GUIDE.md`,
`VOICE_MODE.md`, `SECURITY.md`, `MICROSOFT_VERIFY.md`, `DEPLOYMENT.md`,
`DEPLOYMENT-EXISTING-NGINX.md`, `README-DOCKER.md`, `SETUP-GUIDE.md`, `openapi.json`.
Module docs: `backend/voice/freeswitch/README.md`, `frontend/README.md`,
`backend/voice/knowledge/*.md`, all `.env.example` files.

## Mandatory checklist BEFORE editing docs

- [ ] Identify which contract/behavior changed and find its owning doc via the map.
- [ ] Read the existing doc section so the update matches its structure/voice.
- [ ] Check for the same fact duplicated elsewhere (tables often repeat values).

## Mandatory checklist AFTER editing docs

- [ ] Every table/spec that mentions the changed value now matches the code.
- [ ] `.env.example` files updated for any env var change (all relevant ones).
- [ ] `openapi.json` regenerated if routes/schemas changed.
- [ ] No doc claims a behavior the code no longer has (e.g. "pyVoIP" for the live
      voice path, which is now FreeSWITCH ESL).
- [ ] Cross-references between docs still resolve.

## Validation commands

```bash
# Regenerate the OpenAPI spec from the live app (WSL debian12, .venv-wsl):
cd backend && ../.venv-wsl/bin/python export_openapi.py   # writes openapi.json

# Find every doc/code mention of a value you changed (use the Grep tool), e.g.:
#   Grep "8085"            -> ESL outbound port across config/xml/docs
#   Grep "calendar_confirmation" -> response type across backend/frontend/docs
```

## Documentation updates required

This skill *is* the documentation step — but it must also ensure the change's
guardian-specific doc note is added (e.g. a voice change updates the FreeSWITCH
README, not just the top-level README).

## Known repository risks

- Several docs describe **intended** behavior that the code is still catching up to
  (e.g. ARCHITECTURE.md mentions Google STT/gTTS while the phone path uses
  faster-whisper + edge-tts). When you touch such an area, correct the doc rather
  than copy the stale claim.
- Contract values are duplicated 2–3×; updating only one place creates drift that
  `change-impact-analysis` later flags.
- `openapi.json` is a committed artifact — it goes stale unless regenerated.

## Forbidden behavior

- Do NOT mark a change complete while a documented table/spec still contradicts the code.
- Do NOT rename/add an env var without updating every relevant `.env.example`.
- Do NOT copy a stale claim forward; fix it when you touch that area.
- Do NOT leave `openapi.json` stale after a route/schema change.
