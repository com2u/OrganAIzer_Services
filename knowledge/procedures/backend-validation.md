---
id: backend-validation
type: procedure
owner: pipeline-guardian
status: active
last_reviewed: 2026-06-24
sources:
  - .claude/skills/pipeline-guardian/SKILL.md
  - .claude/skills/organalzer-master-skill/SKILL.md
  - backend/tests/
  - backend/requirements.txt
---

# Backend validation (tests)

## When to use

Before committing or deploying any backend change — to run the test suite and the
safety gate in the canonical environment.

## Prerequisites

- WSL debian12 with the `.venv-wsl` interpreter (the canonical backend test
  environment — ADR 0005). Do **not** use Windows Python.
- Run from the `backend/` directory.
- Tests are hermetic: no real network, FreeSWITCH, COMtrexx, SIP, Docker, or OAuth.

## Steps

1. Full backend suite (inside WSL debian12, from `backend/`):
   ```bash
   ../.venv-wsl/bin/python -m pytest tests/ -q
   ```
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
- **Wrong working directory** — tests import from `backend/` via `sys.path`; run
  from `backend/`.
- **Version-pin breakage** — bumping `requirements.txt` pins (whisper/torch,
  pyVoIP) without reading their comments can break startup or collection.

## Recovery

- Re-run from `backend/` with the `.venv-wsl` interpreter.
- If a dependency change broke collection, revert the pin and consult its comment
  in `requirements.txt`.

## Notes

- **Needs Human Confirmation:** no CI workflow exists yet (`.github/workflows/` is
  absent), so this gate is currently run manually (see `pipeline-guardian`).
