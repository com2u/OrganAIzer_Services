---
id: 0010-python-3-11-supported-runtime
type: decision
owner: pipeline-guardian
status: accepted
last_reviewed: 2026-06-24
sources:
  - backend/Dockerfile
  - backend/requirements.txt
  - .claude/skills/pipeline-guardian/SKILL.md
  - .claude/skills/docker-guardian/SKILL.md
  - "commit 583254f — Add backend container build configuration"
---

# 0010 — Python 3.11 supported runtime

## Status

Accepted.

## Context

The backend depends on packages that are sensitive to the Python version:
`openai-whisper`/`torch` (no Python 3.13 support) and `pyVoIP==1.6.4` (uses
`audioop`, removed in Python 3.13).

## Decision

The supported/canonical backend runtime is Python 3.11. The backend container image
pins `python:3.11-slim`. Python 3.13 is excluded.

## Reasoning

`backend/Dockerfile` sets `FROM python:3.11-slim` with a comment stating 3.13 must
not be used because of `openai-whisper`/`torch` and `pyVoIP==1.6.4`/`audioop`.
`backend/requirements.txt` documents the same constraint (whisper/torch need 3.10
or 3.11; pyVoIP `1.6.4` is the last version that works before `audioop` removal in
3.13). The pipeline- and docker-guardian skills carry the same pin.

## Consequences

- The container runtime is Python 3.11; do not bump to 3.13.
- Dependency bumps for whisper/torch/pyVoIP must respect this version constraint.
- (Per `requirements.txt`, Python 3.10 also satisfies the STT stack, but the
  pinned/canonical container runtime is 3.11.)

## Related Sources

- `backend/Dockerfile` — `FROM python:3.11-slim` and the no-3.13 rationale.
- `backend/requirements.txt` — version-pin comments (whisper/torch, pyVoIP/audioop).
- `.claude/skills/pipeline-guardian/SKILL.md` — Python version pin in CI guidance.
- `.claude/skills/docker-guardian/SKILL.md` — backend image contract (Python 3.11).
- Commit: `583254f` (added `backend/Dockerfile` with the 3.11 pin).
