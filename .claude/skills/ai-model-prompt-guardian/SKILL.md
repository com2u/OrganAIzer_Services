---
name: ai-model-prompt-guardian
description: Owns AI behavior, Executive Agent prompts, tool schemas, OpenRouter/Gemini usage, OpenClaw bounded text usage, STT/TTS, document QA, RAG/knowledge base, translation, hallucination prevention, and prompt/tool drift. Activate when editing prompts, model calls, tool definitions, AI services, NLU, STT/TTS, document/KB QA, or translation behavior.
---

# AI / Model / Prompt Guardian

Owns model-facing behavior: prompts, tool schemas, LLM provider calls,
STT/TTS, document QA, RAG/knowledge base, translation, OpenClaw text operations,
and hallucination controls.

## Purpose

- Keep prompts grounded in repository evidence and user-visible capabilities.
- Keep tool schemas narrow, typed, and aligned with dispatch handlers.
- Prevent prompt/tool drift between docs, tool definitions, and runtime behavior.
- Keep document/KB answers grounded in retrieved content.
- Keep model calls secret-safe and bounded by token/context limits.

## When to activate

- Editing `backend/services/executive_agent_service.py` system prompt or loop.
- Editing `backend/services/tool_definitions.py` or adding agent-callable tools.
- Editing OpenRouter/Gemini usage in chat, image, YouTube, translation, voice, or agent services.
- Editing STT/TTS services, document QA, knowledge-base/RAG, translation, NLU, slot extraction.
- Editing OpenClaw client/API behavior or bounded text-operation prompts.
- Changing prompt instructions, model names, token limits, grounding, or hallucination behavior.

## Files/directories to inspect

- `backend/services/executive_agent_service.py` - system prompt, memory context,
  LLM loop, tool execution, confirmation behavior.
- `backend/services/tool_definitions.py` - function schemas and confirmation set.
- `backend/services/chat_service.py`, `backend/api/chat.py`, `backend/routers/llm.py`.
- `backend/services/nlu_service.py`, `backend/utils/intent_router.py`,
  `backend/utils/slot_extraction.py`.
- `backend/services/document_service.py`, `backend/api/document.py`.
- `backend/services/knowledge_base_service.py`, `backend/api/knowledge_base.py`,
  `backend/utils/embeddings.py`, `backend/utils/text_processing.py`.
- `backend/services/translation_service.py`, `backend/api/translation.py`.
- `backend/services/stt_service.py`, `backend/services/tts_service.py`,
  `backend/api/stt.py`, `backend/api/tts.py`, `backend/routers/stt.py`,
  `backend/routers/tts.py`.
- `backend/services/image_gen_service.py`, `backend/services/nano_banana_service.py`,
  `backend/api/image_gen.py`.
- `backend/services/openclaw_client.py`, `backend/api/openclaw.py`,
  `infra/openclaw/openclaw-data/openclaw.json`.
- `backend/voice/llm_bridge.py`, `backend/voice/knowledge/*.md`.
- Tests: `test_executive_agent_safety.py`, `test_ai_behavior.py`,
  `test_calendar_intent.py`, `test_voice_bugs_regression.py`,
  `test_openclaw_safety.py`, `test_qa_audit_bugs.py`.

## Before-edit Checklist

- [ ] Identify the exact prompt, schema, retrieval step, or model call being changed.
- [ ] Confirm every tool schema has a dispatch path and every dispatch path has a schema.
- [ ] Keep tools narrow and typed; do not add generic `call_backend_api` style tools.
- [ ] For grounding tasks, identify the source text/retrieval result the model may use.
- [ ] For external writes or phone actions, confirm the proposal/confirmation model.
- [ ] Check token limits, truncation, body stripping, and model-visible sensitive data.
- [ ] For OpenClaw, confirm the operation remains a bounded text operation only.

## After-edit Checklist

- [ ] Tool definitions, system prompt, dispatch logic, frontend/docs, and tests agree.
- [ ] Model-visible data excludes secrets, tokens, raw phone numbers, OAuth data,
      local file paths, and unnecessary full bodies.
- [ ] Document/KB answers are instructed to say when evidence is missing.
- [ ] STT/TTS/image/translation behavior still handles missing API keys gracefully.
- [ ] OpenClaw remains limited to cleanup/summarize style text operations.
- [ ] Safety and regression tests cover changed AI behavior where feasible.

## Validation Commands

```bash
# WSL debian12 + .venv-wsl, from backend/:
cd backend
../.venv-wsl/bin/python -m pytest tests/test_executive_agent_safety.py \
  tests/test_ai_behavior.py tests/test_calendar_intent.py \
  tests/test_voice_bugs_regression.py tests/test_openclaw_safety.py \
  tests/test_qa_audit_bugs.py -q

# Prompt/tool drift searches from repo root:
rg -n "TOOLS|CONFIRMATION_REQUIRED_TOOLS|chat_with_tools|system prompt|OpenRouter|Gemini|OpenClaw|document|knowledge_base|translation" backend README.md ARCHITECTURE.md API_OVERVIEW.md
```

## Documentation Updates Required

- `README.md` Executive Agent and feature tables for user-visible AI capability changes.
- `ARCHITECTURE.md` for prompt/tool/state-machine or routing changes.
- `API_OVERVIEW.md` / `openapi.json` for route/schema/model response changes.
- `VOICE_MODE.md` and `backend/voice/freeswitch/README.md` for voice prompt/pipeline changes.
- `SECURITY.md` for model-visible sensitive data or provider key handling changes.

## Known Repository Risks

- README tool names and known limitations can drift from actual
  `tool_definitions.py` and `executive_agent_service.py`.
- Tool schemas are currently agent-specific calendar/email productivity tools;
  many backend AI services are standalone APIs, not agent-callable tools.
- Prompt text embeds operational rules; changes can silently alter safety behavior.
- Document/KB implementations must be inspected before assuming persistence,
  retrieval quality, or citation behavior.
- Voice prompt has layered client knowledge; do not hardcode client facts into
  generic layers.
- OpenClaw is intentionally bounded by container/tool-deny policy; keep AI usage narrow.

## Forbidden Behavior

- Do NOT create generic backend/API/runtime/browser/filesystem tools.
- Do NOT let a model directly execute email/calendar/phone/delete/write actions
  without a typed proposal and explicit confirmation.
- Do NOT expose secrets, tokens, raw phone numbers, local file paths, OAuth data,
  or unrestricted document/email bodies to models.
- Do NOT claim a backend capability exists in the agent unless a tool schema and
  dispatch path prove it.
- Do NOT weaken OpenClaw deny-list assumptions or broaden it beyond bounded text operations.

## External/Manual Validations

- Live model quality checks require configured OpenRouter/Gemini keys and are manual.
- STT/TTS latency and audio quality checks require local audio tools/models and are manual.
- Image generation and translation quality checks require provider credentials/network.
- Real voice/COMtrexx/PBX conversations are environment-dependent/manual.

## Open Questions

- Which model should own each AI surface long-term: OpenRouter, Gemini direct,
  local Whisper, edge/gTTS, or OpenClaw?
- Should document/KB answers include citations/snippets in the API contract?
- What model-visible redaction policy should apply to full email/document bodies?
