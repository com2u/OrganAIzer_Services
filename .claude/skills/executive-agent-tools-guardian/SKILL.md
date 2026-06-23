---
name: executive-agent-tools-guardian
description: Owns future Executive Agent callable tools beyond current calendar/email tools, especially document upload/summarize/chat, knowledge-base add/search/chat, TTS/STT, phone/call handling, and OpenClaw cleanup/summarize. Activate when adding or changing agent tool schemas, tool dispatch, confirmation-required tools, or model instructions for these capabilities.
---

# Executive Agent Tools Guardian

Owns the design and safety review for future agent-callable tools exposed through
`POST /api/agent/chat`. This is not a runtime implementation by itself; it
governs how new tools should be added when the backend APIs already prove the
capability exists.

## Purpose

- Keep Executive Agent tools narrow, typed, and grounded in existing backend APIs.
- Prevent unsafe generic tool access such as `call_backend_api`.
- Classify new tools as safe immediate or confirmation-required before coding.
- Preserve confirmation gates for destructive, persistent, or external actions.
- Keep phone tools stricter than normal tools because they can place real calls.

## When to activate

- Editing `backend/services/tool_definitions.py`.
- Editing tool dispatch in `backend/services/executive_agent_service.py`.
- Adding agent-callable tools for documents, knowledge base, TTS/STT, phone/calls,
  or OpenClaw.
- Changing confirmation-required tool policy.
- Updating system prompt instructions for tool use or future agent capabilities.
- Changing frontend behavior that relies on agent tool response types.

## Files/directories to inspect

- Current agent core:
  - `backend/services/tool_definitions.py`
  - `backend/services/executive_agent_service.py`
  - `backend/api/executive_agent.py`
  - `backend/tests/test_executive_agent_safety.py`
- Candidate backend APIs:
  - `backend/api/document.py`, `backend/services/document_service.py`
  - `backend/api/knowledge_base.py`, `backend/services/knowledge_base_service.py`
  - `backend/api/tts.py`, `backend/api/stt.py`, `backend/services/tts_service.py`,
    `backend/services/stt_service.py`
  - `backend/api/phone.py`, `backend/voice/call_trigger.py`,
    `backend/voice/outbound.py`, `backend/voice/call_log.py`
  - `backend/api/openclaw.py`, `backend/services/openclaw_client.py`
  - `infra/openclaw/openclaw-data/openclaw.json`
- Frontend/contracts: `frontend/src/components/ExecutiveAgent.tsx`,
  `frontend/src/lib/apiClient.ts`, `README.md`, `API_OVERVIEW.md`,
  `ARCHITECTURE.md`, `openapi.json`.
- Safety tests: `test_phone_safety.py`, `test_openclaw_safety.py`,
  `test_logging_redaction.py`, `test_qa_audit_bugs.py`.

## Tool Classification

Safe immediate tools may execute without a user confirmation because they are
read-only, local transformation, or bounded text/audio generation:

- `summarize_document`
- `chat_with_document`
- `search_knowledge_base`
- `chat_with_knowledge_base`
- `generate_speech`
- `transcribe_audio`
- `cleanup_text`
- `summarize_text`
- `get_phone_status`
- `get_call_log`

Confirmation-required tools must create a pending action and wait for explicit
user confirmation before execution:

- `delete_document`
- `add_to_knowledge_base`
- `delete_knowledge_base_item`
- `reindex_knowledge_base`
- `propose_dial_phone`
- `hangup_active_call`

## Phone-Specific Rules

- Never create a direct `dial_phone` tool.
- Use only `propose_dial_phone` plus explicit user confirmation.
- Keep the existing German phone-number restriction from the phone/call stack.
- Mask phone numbers in logs and model-visible responses.
- Treat real COMtrexx/SIP/client-network validation as manual/external.
- Do not allow concurrent-call bypass or affirmative-without-pending dialing.

## Before-edit Checklist

- [ ] Prove the backend capability exists by reading its API/service files.
- [ ] Decide safe immediate vs confirmation-required before writing a schema.
- [ ] Define a narrow JSON schema with typed fields and `additionalProperties: False`.
- [ ] Add schema, dispatch, system prompt guidance, response type handling, and tests together.
- [ ] Ensure every `propose_` or destructive/persistent action is in
      `CONFIRMATION_REQUIRED_TOOLS`.
- [ ] For tools needing uploaded files/audio/documents, require an existing ID or
      upload reference; do not let the agent invent local paths.
- [ ] Confirm no tool exposes secrets, tokens, raw phone numbers, local file paths,
      OAuth data, or full bodies unnecessarily.

## After-edit Checklist

- [ ] Every tool schema has exactly one dispatch path and tests.
- [ ] Every dispatch path is represented in `tool_definitions.py`.
- [ ] Confirmation-required tools return a pending action and do not execute on
      the first LLM turn.
- [ ] Safe immediate tools are read-only/bounded and strip sensitive payloads.
- [ ] Frontend handles any new response `type` or `action_needed` value.
- [ ] Docs and OpenAPI are updated if routes/response contracts changed.
- [ ] Phone and OpenClaw safety tests still cover the relevant boundaries.

## Validation Commands

```bash
# WSL debian12 + .venv-wsl, from backend/:
cd backend
../.venv-wsl/bin/python -m pytest tests/test_executive_agent_safety.py \
  tests/test_phone_safety.py tests/test_openclaw_safety.py \
  tests/test_logging_redaction.py tests/test_qa_audit_bugs.py -q

# Drift checks from repo root:
rg -n "summarize_document|chat_with_document|search_knowledge_base|chat_with_knowledge_base|generate_speech|transcribe_audio|cleanup_text|summarize_text|propose_dial_phone|hangup_active_call|CONFIRMATION_REQUIRED_TOOLS|TOOLS" backend README.md ARCHITECTURE.md API_OVERVIEW.md frontend
```

## Documentation Updates Required

- `README.md` Executive Agent available tools and feature table.
- `ARCHITECTURE.md` tool-calling loop and capability sections.
- `API_OVERVIEW.md` and `openapi.json` for response/route changes.
- `DEVELOPER_GUIDE.md` "Adding Executive AI capabilities" section.
- `VOICE_MODE.md` / `backend/voice/freeswitch/README.md` if phone agent tools
  affect voice/telephony behavior.
- `SECURITY.md` for new destructive/external action gates or sensitive data exposure.

## Known Repository Risks

- Current agent tools are calendar/email-centric; standalone backend APIs are not
  automatically agent-callable.
- README may describe intended behavior that is stale against actual tools.
- Document upload requires file transfer semantics; agent chat currently accepts
  text payloads, so file upload references must be designed deliberately.
- Knowledge-base writes are persistent memory and must not be treated as casual chat.
- TTS/STT need media references or generated URLs; local filesystem paths must not
  be exposed to the model/user.
- Phone tools can place or end real calls and must stay stricter than other tools.
- OpenClaw is intentionally bounded to cleanup/summarize API routes and denied
  filesystem/runtime/browser tools.

## Forbidden Behavior

- Do NOT create `call_backend_api`, `http_request`, `run_tool`, `dial_phone`, or
  any other generic/unbounded agent tool.
- Do NOT let the LLM execute delete/write/dial/hangup/reindex actions directly.
- Do NOT expose tokens, OAuth data, raw phone numbers, local file paths, secrets,
  or unrestricted email/document bodies in tool results.
- Do NOT invent a document/audio/file reference if the frontend/API has not provided one.
- Do NOT weaken existing German-number restrictions or phone masking.
- Do NOT broaden OpenClaw beyond specific cleanup/summarize text tools.

## External/Manual Validations

- Real phone/COMtrexx/SIP/client-network tests are manual and environment-dependent.
- TTS/STT media quality validation is manual unless test fixtures are added.
- Document upload/chat requires representative local test files; avoid network.
- OpenClaw live checks require the bounded container to be running; default tests
  should remain hermetic.

## Open Questions

- How should `POST /api/agent/chat` receive or refer to uploaded documents/audio:
  document IDs, temporary upload IDs, or frontend-selected context?
- Should `add_to_knowledge_base` require confirmation for every write or only
  when storing user/private content?
- What response types should the frontend render for new confirmation-required tools?
- Should `hangup_active_call` require confirmation when the user is already in an
  active phone-control context?
