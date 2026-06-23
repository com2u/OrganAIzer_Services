---
name: security-auth-guardian
description: Owns API key auth, OAuth scopes and provider authentication flows, token storage, CORS, env handling, log redaction, and confirmation gates for destructive or external actions. Activate when editing auth, integrations, token storage, config, logging, security docs, or outward-action safety behavior.
---

# Security / Auth Guardian

Owns security-sensitive boundaries: API keys, OAuth, token files, CORS, logs,
environment variables, provider auth flows, and confirmation gates.

## Purpose

- Keep secrets out of source, logs, model-visible responses, and frontend bundles.
- Keep OAuth scopes and token storage behavior explicit and documented.
- Keep API-key authentication and CORS posture intentional.
- Preserve confirmation gates for destructive or external actions.
- Keep provider auth/disconnect/status flows safe and truthful.

## When to activate

- Editing `backend/auth.py`, `backend/core/config.py`, `backend/core/logging_config.py`,
  `backend/core/middleware.py`, or `.env*`.
- Editing Google/Microsoft OAuth code in `backend/api/integrations.py`,
  `backend/config/google_scopes.py`, `backend/utils/token_storage.py`,
  `backend/utils/ms_token.py`, or provider classes.
- Changing CORS in `backend/main.py` or nginx auth/proxy behavior.
- Changing logs, error handling, debug endpoints, or token diagnostics.
- Changing confirmation-gated actions in Executive Agent, phone, calendar, email,
  document delete, knowledge-base writes, or OpenClaw calls.

## Files/directories to inspect

- `backend/auth.py` - API key loading and request validation.
- `backend/main.py` - CORS setup and router registration.
- `backend/core/config.py`, `backend/core/logging_config.py`,
  `backend/core/middleware.py`, `backend/core/error_handling.py`.
- `backend/api/integrations.py` - Google/Microsoft OAuth, status, disconnect,
  mail/calendar routes, Microsoft debug endpoints.
- `backend/config/google_scopes.py` - Google OAuth scope list and scope hash.
- `backend/utils/token_storage.py`, `backend/utils/ms_token.py`.
- `backend/services/providers/*`.
- `backend/services/executive_agent_service.py`,
  `backend/services/tool_definitions.py` - confirmation gate and tool exposure.
- `backend/api/phone.py`, `backend/voice/call_trigger.py`,
  `backend/voice/outbound.py`, `backend/voice/escalation.py`.
- `SECURITY.md`, `MICROSOFT_VERIFY.md`, `.env.example`, `.gitignore`.
- Tests: `backend/tests/test_logging_redaction.py`,
  `test_executive_agent_safety.py`, `test_phone_safety.py`,
  `test_microsoft_integration.py`, `test_openclaw_safety.py`.

## Before-edit Checklist

- [ ] Identify whether the change touches secrets, OAuth data, tokens, PII, or
      outward/destructive actions.
- [ ] Check current `.env.example` entries before adding or renaming env vars.
- [ ] Check `google_scopes.py` and Microsoft scope usage before changing provider permissions.
- [ ] Confirm whether logs/errors/debug output may include tokens, email bodies,
      phone numbers, local file paths, OAuth codes, or raw provider responses.
- [ ] Confirm destructive/external actions still require explicit user confirmation.
- [ ] If touching CORS, document the intended deployment origin model.

## After-edit Checklist

- [ ] No secrets, tokens, OAuth codes, raw phone numbers, local file paths, or
      email/document bodies are logged or returned unnecessarily.
- [ ] `.env.example`, `SECURITY.md`, and provider docs match new env vars/scopes.
- [ ] OAuth reconnect behavior is clear if scopes change.
- [ ] CORS remains deliberate; wildcard origins must be justified for dev only.
- [ ] Confirmation gates still cover email send, calendar writes/deletes, phone
      dialing/hangup, document delete, knowledge-base writes/deletes/reindex.
- [ ] Logging redaction and safety tests are still appropriate.

## Validation Commands

```bash
# WSL debian12 + .venv-wsl, from backend/:
cd backend
../.venv-wsl/bin/python -m pytest tests/test_logging_redaction.py \
  tests/test_executive_agent_safety.py tests/test_phone_safety.py \
  tests/test_microsoft_integration.py tests/test_openclaw_safety.py -q

# Secret/sensitive string scan examples from repo root:
rg -n "API_KEY|TOKEN|SECRET|CLIENT_SECRET|refresh_token|access_token|id_token|CORS|allow_origins" backend .env.example SECURITY.md
```

## Documentation Updates Required

- `SECURITY.md` for CORS, secret handling, OAuth/token changes, logging posture.
- `.env.example` and any backend/frontend env examples for env var changes.
- `MICROSOFT_VERIFY.md` for Microsoft auth, scopes, redirect, or token behavior.
- `README.md` integration/security sections for user-facing auth changes.
- `API_OVERVIEW.md` / `openapi.json` for auth-sensitive endpoint changes.

## Known Repository Risks

- `backend/main.py` currently uses `allow_origins=["*"]` with
  `allow_credentials=False`; production restriction is documented but not enforced
  in code.
- OAuth tokens are encrypted file storage under `backend/data/tokens` through
  `TokenStorage`; this is not multi-instance storage.
- `SECURITY.md` contains some aspirational or stale claims; verify against code.
- Microsoft debug/token endpoints exist; keep their responses body-safe and
  token-safe.
- Frontend `VITE_API_KEY` is a build-time/public browser value; treat it as an
  access gate, not a secret once shipped to users.

## Forbidden Behavior

- Do NOT commit `.env`, OAuth credentials, token files, SIP passwords, or real keys.
- Do NOT log tokens, OAuth codes, client secrets, raw phone numbers, email bodies,
  document contents, or local filesystem paths.
- Do NOT widen OAuth scopes without updating code, docs, and reconnect behavior.
- Do NOT weaken confirmation gates for destructive/external actions.
- Do NOT create generic execution/API proxy tools that could bypass auth policy.

## External/Manual Validations

- Real Google/Microsoft OAuth flows are environment-dependent and manual.
- Production CORS validation requires the deployed origin and nginx/backend config.
- Secret rotation and token revocation must be validated in the provider consoles.
- Real SIP/COMtrexx/client PBX validation is manual and belongs with the voice
  guardian when phone auth/safety is involved.

## Open Questions

- What production origin list should replace wildcard CORS?
- Is encrypted file token storage acceptable long-term, or should tokens move to
  a database/secrets manager before multi-user/multi-instance deployment?
- Which users/admin roles should be allowed to call Microsoft debug endpoints?
