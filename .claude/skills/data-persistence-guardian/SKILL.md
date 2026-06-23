---
name: data-persistence-guardian
description: Owns persistence and lifecycle of sessions, OAuth tokens, documents, knowledge-base data, generated media, call logs/messages, backup/cleanup, retention, multi-instance readiness, and idempotency. Activate when editing data storage paths, services that persist files, cleanup behavior, or state/idempotency logic.
---

# Data / Persistence Guardian

Owns stored state and data lifecycle across the repo: in-memory sessions,
encrypted OAuth tokens, document/knowledge stores, generated media, call logs,
cleanup, retention, and idempotency.

## Purpose

- Keep persistent and in-memory state behavior explicit and documented.
- Protect data from accidental deletion, leakage, or cross-user/session bleed.
- Keep cleanup and retention behavior deliberate.
- Preserve idempotency for outward writes.
- Surface multi-instance limitations before deployment changes.

## When to activate

- Editing session/state logic in `backend/services/executive_agent_service.py`.
- Editing OAuth token storage or provider connection state.
- Editing document, knowledge-base, TTS, image, STT, video, or generated media storage.
- Editing phone call logs, messages, recordings, or voice temp directories.
- Adding cleanup jobs, retention policies, backup/export behavior, or multi-instance support.
- Changing idempotency stores for email/calendar/phone/external writes.

## Files/directories to inspect

- `backend/services/executive_agent_service.py` - `ConversationMemory`, session
  dict, pending actions, draft memory, email/calendar idempotency stores.
- `backend/api/executive_agent.py` - session info/list/delete endpoints.
- `backend/utils/token_storage.py`, `backend/utils/ms_token.py`.
- `backend/core/config.py` - `TTS_TEMP_DIR`, `IMAGE_GEN_TEMP_DIR`, other data dirs.
- `backend/services/document_service.py`, `backend/api/document.py`,
  `backend/models/document.py`.
- `backend/services/knowledge_base_service.py`, `backend/api/knowledge_base.py`,
  `backend/models/knowledge_base.py`, `backend/utils/embeddings.py`,
  `backend/utils/text_processing.py`.
- `backend/services/tts_service.py`, `backend/services/image_gen_service.py`,
  `backend/services/stt_service.py`, `backend/services/video_service.py`,
  `backend/services/youtube_service.py`.
- `backend/voice/call_log.py`, `backend/voice/contacts.py`,
  `backend/voice/config.py`, `backend/voice/esl_call_handler.py`.
- `data/`, `backend/data/`, `infra/openclaw/openclaw-data/`, `.gitignore`.
- Docs: `README.md`, `ARCHITECTURE.md`, `VOICE_MODE.md`, `SECURITY.md`,
  `README-DOCKER.md`, deployment docs.
- Tests: `test_executive_agent_safety.py`, `test_calendar_event_creation.py`,
  `test_qa_audit_bugs.py`, `test_phone_safety.py`, `test_logging_redaction.py`.

## Before-edit Checklist

- [ ] Identify whether state is process memory, local filesystem, static media,
      encrypted token storage, OpenClaw volume, or provider-side data.
- [ ] Determine user/session ownership rules and whether data can cross users.
- [ ] Check `.gitignore` before creating or relocating persisted files.
- [ ] For deletes/cleanup, identify all dependent indexes, metadata, cached summaries,
      generated files, and docs.
- [ ] For multi-instance or Docker changes, identify which data path needs a shared volume.
- [ ] For idempotency, define the stable key and the retry/failure behavior before editing.

## After-edit Checklist

- [ ] User/session scoping is explicit and tested for sensitive data.
- [ ] Deletes remove dependent metadata/indexes/files or deliberately leave audited data.
- [ ] Generated media is retrievable only through documented static/API paths.
- [ ] Cleanup/retention behavior is documented and does not delete secrets or user data casually.
- [ ] Idempotency still prevents duplicate outward writes on retries/double-confirm.
- [ ] Multi-instance limitations are documented if state remains process-local or local-file only.

## Validation Commands

```bash
# WSL debian12 + .venv-wsl, from backend/:
cd backend
../.venv-wsl/bin/python -m pytest tests/test_executive_agent_safety.py \
  tests/test_calendar_event_creation.py tests/test_qa_audit_bugs.py \
  tests/test_phone_safety.py tests/test_logging_redaction.py -q

# Storage path and data lifecycle searches from repo root:
rg -n "data/|TTS_TEMP_DIR|IMAGE_GEN_TEMP_DIR|TokenStorage|idempot|session|delete_document|knowledge_base|call_log" backend README.md SECURITY.md .env.example docker-compose.yml
```

## Documentation Updates Required

- `README.md` known limitations for session/idempotency/token storage changes.
- `ARCHITECTURE.md` for state model, data flow, and storage lifecycle changes.
- `SECURITY.md` for token/data retention, backups, and sensitive storage.
- `README-DOCKER.md` / deployment docs for volume or persistence topology changes.
- `.env.example` for new storage paths, retention knobs, or cleanup settings.
- `API_OVERVIEW.md` / `openapi.json` for data lifecycle endpoint changes.

## Known Repository Risks

- Executive Agent sessions and idempotency stores are in-memory and lost on restart.
- OAuth tokens are local encrypted files under `data/tokens`; not shared across instances.
- Generated TTS and image media use local data directories from `backend/core/config.py`.
- OpenClaw state is bound to `infra/openclaw/openclaw-data` and is protected by
  docker safety tests.
- Document and knowledge-base storage implementations must be checked directly
  before assuming retention, ownership, or cleanup semantics.
- `backend/Dockerfile` and `.dockerignore` are currently untracked in this worktree;
  do not assume they are committed deployment contracts.

## Forbidden Behavior

- Do NOT delete, move, or rewrite persisted data paths without a backup/retention decision.
- Do NOT expose tokens, raw phone numbers, local file paths, document bodies, or
  provider data in logs/model-visible responses.
- Do NOT assume in-memory state survives reload, restart, scaling, or multiple workers.
- Do NOT weaken idempotency guards for email/calendar/phone/external writes.
- Do NOT add persistence that is unscoped by user/session when data can be sensitive.

## External/Manual Validations

- Backup/restore drills are manual unless scripts/tests are added.
- Multi-instance readiness requires a real shared storage/deployment environment.
- Real provider-token refresh/expiration behavior is manual with Google/Microsoft.
- SIP, COMtrexx, client PBX, and real-call log validation are environment-dependent/manual.

## Open Questions

- What retention period should apply to documents, generated media, call logs, and transcripts?
- Should sessions/idempotency move from process memory to durable storage?
- What is the intended backup strategy for `data/`, `backend/data/`, and OpenClaw data?
- How should per-user ownership be enforced for documents and knowledge-base items?
