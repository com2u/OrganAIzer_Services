---
name: pipeline-guardian
description: Owns how OrganAIzer Services is built, tested, linted, and gated. Activate when touching test infrastructure, requirements.txt/package.json versions, adding CI, or running the test suite. Enforces the WSL-only backend test runner, the safety-test gate, and the intended (currently missing) CI pipeline.
---

# Pipeline Guardian

This repo has **no CI configured yet** (`.github/workflows` is absent). This skill
describes both how testing works today and how the pipeline *should* work, so any
build/test/release change converges toward a safe, reproducible gate.

## Purpose

- Guarantee tests run in the correct environment (WSL, not Windows Python).
- Keep the safety-test suite as a hard gate on every change.
- Manage dependency pins carefully (several are Python-version-sensitive).
- Define the CI pipeline the repo should adopt.

## When to activate

- Adding or modifying tests, `conftest`, or test fixtures.
- Changing `backend/requirements.txt` or `frontend/package.json` versions.
- Adding/editing CI workflows, lint config, or pre-commit hooks.
- Any task that says "run the tests" or "make sure it passes".

## Files/directories to inspect

- `backend/tests/` — the full suite; the safety subset is the gate.
- `backend/requirements.txt` — pinned, with load-bearing version comments.
- `frontend/package.json` — `dev`/`build`/`lint`/`preview` scripts.
- `backend/main.py` — startup imports that must not break the test collection.
- `.github/workflows/` — **does not exist yet; create here when adding CI.**
- Memory note: backend tests run via **WSL debian12 + `.venv-wsl`**.

## How testing works (intended)

Backend tests are pure unit tests — **no real network, no FreeSWITCH, no COMtrexx,
no SIP, no Docker, no real OAuth.** External calls are mocked (aiohttp,
originate_call, MSAL, provider HTTP). This is by design and must stay true so CI
can run them anywhere. COMtrexx/FreeSWITCH behavior is validated manually,
separately from CI (see `comtrexx-integration-guardian`).

Test environment:
```bash
# Inside WSL debian12, from repo root:
cd backend
../.venv-wsl/bin/python -m pytest tests/ -q
```

Never invoke backend tests with Windows Python — the voice/STT stack
(torch/whisper, audioop) and the `.venv-wsl` interpreter are the supported path.

## Mandatory checklist BEFORE editing

- [ ] Confirm new tests stay hermetic: no real network, FS, Docker, or OAuth.
- [ ] If changing a dependency pin, read its comment in `requirements.txt` first
      (pyVoIP 1.6.4, openai-whisper/torch, websockets are version-sensitive).
- [ ] If adding CI, plan to run the safety subset as a required check.

## Mandatory checklist AFTER editing

- [ ] Full suite green in WSL: `pytest tests/ -q`.
- [ ] Safety subset green (see Validation).
- [ ] `frontend`: `npm run lint && npm run build` clean.
- [ ] Any new dependency pinned with a justifying comment if version-sensitive.
- [ ] If CI added/changed, the workflow runs the safety subset and frontend build.

## Validation commands

```bash
# Backend — full + safety gate (WSL debian12, .venv-wsl):
cd backend
../.venv-wsl/bin/python -m pytest tests/ -q
../.venv-wsl/bin/python -m pytest tests/test_phone_safety.py tests/test_openclaw_safety.py \
  tests/test_executive_agent_safety.py tests/test_logging_redaction.py \
  tests/test_voice_bugs_regression.py tests/test_qa_audit_bugs.py -q

# Frontend:
cd frontend && npm ci && npm run lint && npm run build
```

## Intended CI pipeline (create under `.github/workflows/`)

A workflow should, on push/PR:
1. Set up Python 3.11 (NOT 3.13 — torch/whisper + pyVoIP constraints).
2. `pip install -r backend/requirements.txt`.
3. Run `pytest backend/tests/ -q` (hermetic; no secrets needed) — **backend
   safety test suite is a required, non-skippable job.**
4. Set up Node 18+, `npm ci` + `npm run lint` + `npm run build` in `frontend/`.
5. **Docker build check:** `docker compose build backend` (the backend image
   exists today). Add `frontend` to the build once `frontend/Dockerfile` exists;
   until then the full `docker compose build` is expected to fail (see
   `docker-guardian`). Build only — do not start the stack or hit external services.
6. **No live COMtrexx / FreeSWITCH / SIP in CI.** The suite is hermetic by design;
   the deflect-not-bridge guarantee is pinned by source/mechanism assertions, not a
   live call. CI must never dial, register a gateway, or require a real PBX.

### Manual COMtrexx validation stays separate from CI

Live PBX behavior (gateway `REGED`, inbound INVITE to `003010`, deflect→orbit
music→manual pickup, no `INCOMPATIBLE_DESTINATION`) cannot run in CI and must stay
an **out-of-band manual checklist** on the FreeSWITCH host — see
`comtrexx-integration-guardian`. Do not try to fold it into the pipeline, and do
not gate CI on it.

## Documentation updates required

- Update `DEVELOPER_GUIDE.md` and `VOICE_MODE.md` §5 if the test invocation changes.
- Document any new required dependency in `README.md` prerequisites.
- If CI is added, document the gate in `README.md` / `DEVELOPER_GUIDE.md`.

## Known repository risks

- **No CI exists** — the safety tests only run if a human runs them. Treat the
  safety subset as a manual gate until CI lands.
- `requirements.txt` has **load-bearing version pins**: `pyVoIP==1.6.4` (audioop
  removed in 3.13), `openai-whisper`/`torch` (no Py3.13 Windows support, imported
  lazily), `websockets>=11.0` (uvicorn extra not always installed transitively).
  Bumping these blindly breaks startup or WS.
- Tests import from `backend/` via `sys.path.insert`; running pytest from the wrong
  cwd changes collection. Run from `backend/`.

## Forbidden behavior

- Do NOT run or recommend backend tests via Windows Python.
- Do NOT make tests depend on real network, FreeSWITCH, COMtrexx, SIP, Docker, or OAuth.
- Do NOT add a live COMtrexx/PBX dependency to CI, or gate CI on manual PBX validation.
- Do NOT bump version-pinned dependencies without reading their comment and testing.
- Do NOT add CI that skips or soft-fails the safety subset.
- Do NOT add `Co-Authored-By` trailers to commits the pipeline produces.
