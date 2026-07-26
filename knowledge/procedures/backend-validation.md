---
id: backend-validation
type: procedure
owner: pipeline-guardian
status: active
last_reviewed: 2026-07-26
sources:
  - .claude/skills/pipeline-guardian/SKILL.md
  - .claude/skills/organalzer-master-skill/SKILL.md
  - backend/tests/
  - backend/requirements.txt
  - backend/requirements-dev.txt
---

# Backend validation (tests)

## When to use

Before committing or deploying any backend change — to run the test suite and the
safety gate in the canonical environment.

## Prerequisites

- WSL debian12 with the `.venv-wsl` interpreter (the canonical backend test
  environment — ADR 0005). Do **not** use Windows Python.
- Run from the `backend/` directory.
- Test dependencies installed from `backend/requirements-dev.txt` (it pulls in
  `requirements.txt` via `-r`, so this one command is sufficient):
  ```bash
  pip install -r requirements-dev.txt
  ```
  The test runner itself (`pytest`, `pytest-asyncio`) is pinned there, not in
  `requirements.txt` — the production image installs `requirements.txt` only.
- Tests are hermetic: no real network, FreeSWITCH, COMtrexx, SIP, Docker, or OAuth.

## Steps

1. Full backend suite — **the canonical command** (inside WSL debian12, from
   `backend/`):
   ```bash
   source ../.venv-wsl/bin/activate   # or: ../.venv-wsl/bin/python -m pytest . -q
   pytest . -q
   ```

   Note the `../`. The canonical venv is at the **repo root**
   (`OrganAIzer_Services/.venv-wsl`). A second, stale `backend/.venv-wsl` also
   exists on some machines — it has pytest 9.0.3, **no pytest-asyncio at all**,
   and pytz 2026.1.post1 instead of the pinned 2026.2. Activating it from
   `backend/` as `source .venv-wsl/bin/activate` runs the suite without the
   asyncio plugin, which silently fails `test_auth.py`'s async tests. Both
   directories are gitignored; neither is tracked. Prefer the explicit
   `../.venv-wsl/bin/python -m pytest` form, which cannot pick the wrong one.

   Use `.` — **not** `tests/`. Five pytest files live at the `backend/` root
   (`test_auth.py`, `test_ai_behavior.py`, `test_import.py`,
   `test_main_import.py`, `test_read_intents.py`) and are outside `tests/`, so
   `pytest tests/ -q` silently skips them and reports a green suite that never
   ran them.

   This is not merely a coverage gap. Root-level files are collected *before*
   `tests/`, so they also set process-wide state for everything after them —
   `test_auth.py`'s `@pytest.mark.asyncio` teardown clears the main thread's
   event loop. Ordering bugs of that kind are only reachable via `pytest . -q`;
   `pytest tests/ -q` cannot see them by construction.
2. Safety subset (run on every change):
   ```bash
   ../.venv-wsl/bin/python -m pytest tests/test_phone_safety.py \
     tests/test_openclaw_safety.py tests/test_executive_agent_safety.py \
     tests/test_logging_redaction.py -q
   ```
   (The pipeline-guardian skill lists an extended safety set that also includes
   `tests/test_voice_bugs_regression.py` and `tests/test_qa_audit_bugs.py`.)
3. Frontend checks:
   ```bash
   cd frontend && npm ci && npm run lint && npm run build
   ```

## Validation

- pytest reports all tests passing for the suite and the safety subset.
- The frontend lint and build complete without errors.

## Expected outcomes

- Green safety subset is the gate for any change touching safety-critical behavior.

## Common failure modes

- **Run via Windows Python** — unsupported; the voice/STT stack and pins
  (Python 3.11, openai-whisper/torch, pyVoIP — see ADR 0010) require the WSL
  `.venv-wsl` interpreter.
- **Run as `pytest tests/ -q`** — incomplete; misses the five root-level test
  files and every collection-order interaction they cause. Use `pytest . -q`.
- **Test runner missing or unpinned** — `pytest`/`pytest-asyncio` come from
  `requirements-dev.txt`. Installing only `requirements.txt` leaves no runner;
  installing them ad hoc can pick a version that changes collection (the 0.2x
  `pytest-asyncio` line caps pytest below 9 and silently downgrades it).
- **Wrong working directory** — tests import from `backend/` via `sys.path`; run
  from `backend/`.
- **Version-pin breakage** — bumping `requirements.txt` pins (whisper/torch,
  pyVoIP) without reading their comments can break startup or collection.

## Recovery

- Re-run from `backend/` with the `.venv-wsl` interpreter.
- If a dependency change broke collection, revert the pin and consult its comment
  in `requirements.txt`.

## Backlog (deferred, not blocking)

- **Consolidate root-level test files under `backend/tests/`.** The five files
  listed above sit outside `tests/`, so `tests/conftest.py` (and its shared
  `run_isolated` / `stub_missing_modules` helpers) does not apply to them, and
  their collection-order effect on the rest of the suite is invisible to anyone
  running `pytest tests/`. Three of them (`test_ai_behavior.py`,
  `test_import.py`, `test_read_intents.py`) are script-style rather than
  pytest-style and need converting as part of the move. Deliberately **not**
  done in the pinning pass — moving them changes collection order, which is the
  exact variable being stabilised. Until then, `pytest . -q` is mandatory.
- **Deferred dependency cleanup — `pip check` conflicts.** Two unresolved
  transitive conflicts, both `click`-version-only:
  ```
  huggingface-hub 1.20.1 has requirement click>=8.4.0, but you have click 8.1.8.
  typer 0.25.1     has requirement click>=8.2.1, but you have click 8.1.8.
  ```
  `click` is unpinned and arrives transitively. Both affect CLI entry points,
  not library imports; no test implicates them and the full suite is green.
  Resolving means pinning `click` in `requirements.txt` (production), so it is
  out of scope for test-environment work and should be assessed on its own.
- **`.claude/skills/pipeline-guardian/SKILL.md` still documents
  `pytest tests/ -q`** in its validation commands and proposed CI steps. It
  should be updated to `pytest . -q` to match this procedure.
- **Remove the stale `backend/.venv-wsl`.** It shadows the canonical root venv
  under the natural-looking `source .venv-wsl/bin/activate` from `backend/`,
  and it is missing pytest-asyncio entirely. Deleting it removes a whole class
  of "green on my machine, red in yours" reports. Not done here because it is
  an untracked local environment, not a repo change.

## Notes

- **Needs Human Confirmation:** no CI workflow exists yet (`.github/workflows/` is
  absent), so this gate is currently run manually (see `pipeline-guardian`).
- The proposed CI in `pipeline-guardian` installs `requirements.txt` only, which
  provides no test runner. CI must install `requirements-dev.txt`.
