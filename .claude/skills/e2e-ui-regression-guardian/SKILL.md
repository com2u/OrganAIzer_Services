---
name: e2e-ui-regression-guardian
description: Owns browser-level and UI regression validation, including frontend smoke tests, voice UI smoke tests, frontend/backend contract checks, WebSocket behavior, and Playwright-style testing if configured. Activate when adding UI tests, changing user flows, changing WebSocket UI behavior, or validating frontend regressions.
---

# E2E / UI Regression Guardian

Owns end-to-end and browser-facing validation for the React app, especially chat,
provider selection, integrations, voice WebSocket UI, and phone UI flows.

## Purpose

- Define what must be smoke-tested after UI/user-flow changes.
- Keep frontend/backend contract validation explicit.
- Use browser automation only when the repo supports it; otherwise document manual checks.
- Prevent regressions in confirmation, provider selection, WebSocket state, and navigation.

## When to activate

- Adding or modifying browser-level tests, UI smoke tests, or test tooling.
- Changing `frontend/src/App.tsx`, `ExecutiveAgent`, voice overlay, integrations, phone UI.
- Changing frontend/backend contracts consumed by UI.
- Changing WebSocket message behavior or UI state transitions.
- Before shipping a user-facing workflow change without existing automated coverage.

## Files/directories to inspect

- `frontend/package.json` - currently has `dev`, `build`, `lint`, `preview`; no
  Playwright/Cypress script is present.
- `frontend/src/App.tsx`, `frontend/src/components/*`, `frontend/src/pages/*`.
- `frontend/src/lib/apiClient.ts`, `frontend/src/lib/api.ts`.
- `backend/api/executive_agent.py`, `backend/api/voice_mode.py`,
  `backend/api/phone.py`, `backend/api/integrations.py`.
- `backend/tests/` for backend contract/safety tests.
- `README.md`, `API_OVERVIEW.md`, `VOICE_MODE.md`, `DEVELOPER_GUIDE.md`.
- If introduced later: `.github/workflows/`, `playwright.config.*`,
  `cypress.config.*`, `frontend/tests/`, `e2e/`.

## Before-edit Checklist

- [ ] Confirm whether automated browser tooling exists; do not assume Playwright.
- [ ] Identify the user flows affected: chat, confirmation, provider selection,
      integration connect/disconnect, TTS/STT, image, video, phone, voice mode.
- [ ] Identify backend responses/events the UI must simulate or receive.
- [ ] For WebSocket behavior, list expected events and close/error states.
- [ ] Keep tests hermetic by default; do not require real OAuth, FreeSWITCH, Docker,
      COMtrexx, or external network for CI-style tests.

## After-edit Checklist

- [ ] Frontend lint/build still pass.
- [ ] Backend safety/contract tests still cover any changed response shape.
- [ ] Manual smoke checklist is updated if no automated browser test exists.
- [ ] Confirmation flows are tested for no double-submit.
- [ ] Provider-selection UX is tested for Google-only, Microsoft-only, both, neither.
- [ ] Voice UI is tested for connect, record, partial/final transcript, TTS audio,
      interrupt, close/error states when affected.

## Validation Commands

```bash
# Current frontend validation:
cd frontend
npm run lint
npm run build

# Backend contract/safety subset when UI contract changes (WSL debian12, from backend/):
cd backend
../.venv-wsl/bin/python -m pytest tests/test_executive_agent_safety.py \
  tests/test_phone_safety.py tests/test_voice_bugs_regression.py \
  tests/test_microsoft_integration.py -q

# Check whether browser automation is configured:
rg -n "playwright|cypress|vitest|testing-library" frontend package.json .github
```

## Documentation Updates Required

- `DEVELOPER_GUIDE.md` for any new UI/E2E test command or workflow.
- `README.md` local-running section if validation steps change.
- `VOICE_MODE.md` for manual/automated voice UI validation changes.
- `API_OVERVIEW.md` when UI contract checks depend on new response fields/events.
- CI docs if `.github/workflows/` is introduced.

## Known Repository Risks

- No Playwright/Cypress-style dependency or script is present in `frontend/package.json`.
- No CI workflow is present, so UI validation is manual unless test tooling is added.
- Real microphone/WebSocket voice testing requires browser permissions and a running backend.
- Provider integration flows require OAuth credentials and cannot be hermetic unless mocked.
- Phone UI can touch real call state; real call validation must stay manual/environment-gated.

## Forbidden Behavior

- Do NOT add E2E tests that require real OAuth, real phone calls, real COMtrexx/PBX,
  Docker, or external network in the default automated suite.
- Do NOT bypass confirmation gates in tests or UI helpers.
- Do NOT store screenshots/logs containing secrets, tokens, raw phone numbers,
  email bodies, or local file paths.
- Do NOT claim Playwright/Cypress support unless config and scripts exist.
- Do NOT run unrelated backend tests for a pure UI test change.

## External/Manual Validations

- Browser smoke test: navigation tabs, chat send, confirmation buttons, provider
  selection, integrations link, error display.
- Voice UI smoke test: microphone permission, WebSocket connect, hold-to-speak,
  transcript, TTS playback, interrupt, disconnect/reconnect.
- Phone UI smoke test without placing calls where possible; real COMtrexx/SIP/client
  network and live-call tests are manual/external.
- OAuth provider connect/disconnect is manual unless mocked.

## Open Questions

- Should Playwright be added as the standard browser automation framework?
- Which flows should become required CI smoke tests first?
- Should frontend contract tests mock `/api/agent/chat` and `/api/voice/stream`
  locally, or run against a test backend?
