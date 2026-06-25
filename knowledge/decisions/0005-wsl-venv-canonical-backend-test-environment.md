---
id: 0005-wsl-venv-canonical-backend-test-environment
type: decision
owner: pipeline-guardian
status: accepted
last_reviewed: 2026-06-24
sources:
  - .claude/skills/pipeline-guardian/SKILL.md
  - .claude/skills/organalzer-master-skill/SKILL.md
  - backend/requirements.txt
---

# 0005 — WSL Debian + .venv-wsl is the canonical backend test environment

## Status

Accepted.

## Context

The backend voice/STT stack and several version-pinned dependencies are validated
under WSL debian12 using the `.venv-wsl` interpreter. Windows Python is not the
authoritative validation environment.

## Decision

Backend tests run via WSL debian12 using `.venv-wsl`
(`../.venv-wsl/bin/python -m pytest` from `backend/`). Windows Python is not the
authoritative backend test/validation environment.

## Reasoning

The supported stack depends on Python 3.11 and pins such as openai-whisper/torch
and pyVoIP, which are tied to the WSL interpreter and are not supported under
Windows Python. Running the suite under the wrong interpreter is unsupported and
can change collection/behavior.

## Consequences

- All backend test runs and the safety gate use the WSL `.venv-wsl` interpreter.
- The pipeline-guardian and master skills document this as the required runner.

## Related Sources

- `.claude/skills/pipeline-guardian/SKILL.md` — WSL-only runner, version pins.
- `.claude/skills/organalzer-master-skill/SKILL.md` — Validation commands.
- `backend/requirements.txt` — load-bearing version pins.
