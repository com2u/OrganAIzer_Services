---
name: frontend-guardian
description: Owns the React/Vite frontend, including UI pages and tabs, frontend/backend API contracts, WebSocket UI behavior, provider-selection UX, and frontend build/lint expectations. Activate when editing frontend/, frontend API clients, ExecutiveAgent UI, voice UI, page navigation, or adding UI for backend APIs.
---

# Frontend Guardian

Owns the browser application under `frontend/`: React components, Vite build,
API client contracts, tab/page exposure, and WebSocket-driven voice UI behavior.

## Purpose

- Keep frontend behavior aligned with backend response contracts and routes.
- Keep provider-selection UX consistent with the Executive Agent's backend rules.
- Keep WebSocket voice UI state transitions coherent and recoverable.
- Ensure visible pages in `frontend/src/App.tsx` reflect intentional product scope.
- Catch missing UI surfaces for backend APIs without inventing implementation.

## When to activate

- Editing anything under `frontend/`.
- Changing `frontend/src/lib/apiClient.ts` or `frontend/src/lib/api.ts`.
- Changing `ExecutiveAgent`, `VoiceExecutiveAgent`, `PhonePage`, `IntegrationsPage`, or page tabs.
- Adding/removing frontend pages or exposing backend APIs in the UI.
- Changing frontend handling of backend `type`, `task_state`, `action_needed`, or WebSocket events.
- Changing frontend build, lint, TypeScript, Tailwind, Vite, or nginx config.

## Files/directories to inspect

- `frontend/src/App.tsx` - tabs/pages currently exposed: executive, tts, stt,
  image-gen, youtube, integrations, phone.
- `frontend/src/components/ExecutiveAgent.tsx` - chat UI, provider resolution,
  confirmation quick replies, voice WebSocket overlay.
- `frontend/src/components/VoiceExecutiveAgent.tsx`, `ChatComposer.tsx`,
  `TopNav.tsx`, `ErrorBanner.tsx`, `AudioPlayer.tsx`.
- `frontend/src/lib/apiClient.ts` - Executive Agent, STT/TTS, WebSocket URL helpers.
- `frontend/src/lib/api.ts` - standalone API helpers for TTS, STT, image, video, chat.
- `frontend/src/pages/*` - currently implemented page surfaces.
- `frontend/package.json`, `vite.config.ts`, `eslint.config.js`,
  `tsconfig*.json`, `tailwind.config.js`, `frontend/nginx.conf`.
- Backend contracts: `backend/api/executive_agent.py`, `backend/main.py`,
  `backend/api/voice_mode.py`, `backend/api/phone.py`, `backend/api/integrations.py`.
- Docs: `README.md`, `API_OVERVIEW.md`, `VOICE_MODE.md`, `frontend/README.md`.

## Before-edit Checklist

- [ ] Identify every backend response field/event the UI consumes.
- [ ] Search for all consumers of changed response `type`, `task_state`,
      `action_needed`, route path, or WebSocket event names.
- [ ] Check `frontend/src/App.tsx` before adding or removing a page/tab.
- [ ] Verify whether the backend already has the route; do not invent frontend
      behavior for an unproven backend capability.
- [ ] For provider UX, confirm the "exactly one connected provider locks it;
      both/neither leaves backend to ask" rule still holds.
- [ ] For voice UI, confirm reconnect, interrupt, partial/final transcript, and
      TTS audio paths are affected or unaffected.

## After-edit Checklist

- [ ] Frontend contracts match backend response shapes and documented values.
- [ ] No confirmation button can double-submit an outward action.
- [ ] Provider-selection UI does not force Google/Microsoft when ambiguous.
- [ ] WebSocket UI handles close/error/reconnect without stale speaking/listening state.
- [ ] Text fits in buttons/cards at narrow and desktop widths.
- [ ] Missing or intentionally absent pages are documented if backend docs claim them.
- [ ] Build/lint validation is run when frontend code changes.

## Validation Commands

```bash
# Frontend only:
cd frontend
npm run lint
npm run build

# Contract search examples from repo root:
rg "confirmation_required|task_state|action_needed|provider_not_connected|calendar_provider_request" frontend backend README.md API_OVERVIEW.md
rg "type PageType|TABS|currentPage" frontend/src/App.tsx
```

## Documentation Updates Required

- `README.md` feature table and frontend/backend communication section when UI
  pages or response behavior changes.
- `API_OVERVIEW.md` when the frontend depends on new/changed response fields.
- `VOICE_MODE.md` when WebSocket event handling or voice UI protocol changes.
- `frontend/README.md` for frontend setup/build behavior changes.

## Known Repository Risks

- Backend registers document, knowledge-base, and translation APIs in
  `backend/main.py`, but `frontend/src/App.tsx` currently exposes no document,
  knowledge-base, or translation pages. README claims `/documents` and
  `/translation` pages; verify before trusting that docs reflect UI.
- Frontend has no Playwright or browser test dependency in `frontend/package.json`.
- The app uses hand-rolled tab state in `App.tsx`, not router-based page routing.
- There are two API helper files (`api.ts` and `apiClient.ts`); avoid duplicating
  or diverging endpoint definitions.
- Some UI strings include German labels while backend intent suggestions rely on
  English phrases.

## Forbidden Behavior

- Do NOT change backend API contracts from the frontend layer.
- Do NOT hardcode secrets or fallback API keys in frontend code.
- Do NOT add UI for an unproven backend route without marking the backend gap.
- Do NOT bypass confirmation UX for email, calendar, phone, delete, or other
  external/destructive actions.
- Do NOT expose tokens, OAuth data, raw phone numbers, local file paths, or
  provider secrets in UI state, debug panels, or errors.

## External/Manual Validations

- Manual browser smoke test for changed pages and tabs.
- Manual voice WebSocket smoke test with microphone permissions when voice UI changes.
- Manual provider-selection test with Google-only, Microsoft-only, both, and neither
  connected when integrations UX changes.
- Browser automation is manual until a Playwright/Cypress-style setup exists.

## Open Questions

- Should the missing document, knowledge-base, and translation frontend pages be
  added, or should README claims be corrected first?
- Should the repo standardize on `apiClient.ts`, `api.ts`, or keep both with a
  clear ownership split?
- Should browser-level tests be introduced before larger frontend work?
