---
name: voice-freeswitch-guardian
description: Owns the telephony stack — FreeSWITCH/COMtrexx, ESL inbound/outbound sockets, the AI call handler, escalation/voicemail, phone-call triggering, and the layered voice prompt. Activate when editing backend/voice/*, FreeSWITCH XML, or backend/api/phone.py. Enforces German-only dialing, number masking, template hygiene, and the ESL topology.
---

# Voice / FreeSWITCH Guardian

Owns the live telephony path: COMtrexx PBX ↔ FreeSWITCH (WSL) ↔ Python backend
over ESL. This is the highest-risk subsystem — it places real phone calls, handles
PII (phone numbers), and depends on out-of-repo deployed config.

## Purpose

- Keep outbound dialing restricted to German numbers and never leak raw numbers.
- Keep the ESL inbound/outbound topology and ports coherent across code, XML, docs.
- Protect the layered prompt design and the escalation/voicemail safety timing.
- Keep repo FreeSWITCH XML as safe **templates** (no real secrets, no drift).

## When to activate

- Editing anything under `backend/voice/` (handlers, ESL, config, escalation,
  call_trigger, llm_bridge, audio_bridge, contacts, outbound).
- Editing `backend/voice/freeswitch/*.xml` or `verify_freeswitch.sh`.
- Editing `backend/api/phone.py` or the voice startup in `backend/main.py`.
- Editing `backend/voice/knowledge/*.md` (Layer 3 client knowledge).

## Files/directories to inspect

- `backend/voice/freeswitch/README.md` — authoritative topology + address table.
- `backend/voice/config.py` — all env-driven voice settings (ESL, escalation,
  recording, company profile Layers 2/3).
- `backend/voice/esl_client.py` (inbound API), `esl_call_handler.py` (per-call loop),
  `outbound.py` (originate), `call_trigger.py` (NL call intent + masking + German gate),
  `escalation.py` (transfer/voicemail), `llm_bridge.py` (Layer 1 prompt), `audio_bridge.py`
  (Whisper STT prewarm), `call_log.py`, `contacts.py`.
- `backend/api/phone.py` — `/api/phone/*` + `phone_state`.
- `backend/main.py` lifespan — ESL outbound server, gateway watchdog, prewarm.
- Tests: `test_phone_safety.py`, `test_voice_bugs_regression.py`.

## Topology (MUST stay coherent)

```
COMtrexx 172.20.0.244  ──SIP/TLS:5061──▶ FreeSWITCH (WSL)
FreeSWITCH ──ESL outbound socket──▶ Python 127.0.0.1:8085  (per-call, FS→Python)
Python ──ESL inbound──▶ FreeSWITCH 127.0.0.1:8021  (originate/status, Python→FS)
```
- Outbound: `originate_call()` → `originate ... &socket(127.0.0.1:8085 async full)`.
- Inbound: COMtrexx INVITE → dialplan `socket 127.0.0.1:8085 async full` → Python.
- Live path is **FreeSWITCH ESL**, NOT pyVoIP. `sip_client.py`/pyVoIP are legacy;
  do not wire new behavior to them.
- ESL addresses appear in THREE places: `config.py`, the XML files, and
  `freeswitch/README.md`. Change all three together.

## Voice invariants (MUST hold)

1. **German-only dialing.** `is_german_number` gates every dial. Blocks `+1/+44/+33`
   etc. Never bypass it.
2. **Number masking everywhere outward.** `mask_number` masks the middle; the raw
   number lives ONLY in `_pending` process memory — never logged, never returned,
   never in escalation emails as raw.
3. **Confirmation before dialing.** `call_trigger` state machine requires a pending
   confirmation; an affirmative with no pending must NOT dial. One active call at a
   time (`phone_state` blocking).
4. **Layered prompt.** Layer 1 (`llm_bridge.py`) is client-agnostic core behavior.
   Layer 2 = `AI_COMPANY_*` env vars in `config.py`. Layer 3 = knowledge markdown
   (`backend/voice/knowledge/*.md`, default `teleprofi_fulda.md`). Never hardcode a
   client into Layer 1.
5. **Escalation = deflect to the manned waiting room.** Escalation parks the
   caller via SIP REFER (`deflect sip:778@<COMtrexx IP>`, then `779`) — never a
   bridge to the gateway (COMtrexx rejects that with cause 88
   `INCOMPATIBLE_DESTINATION`). The caller then hears COMtrexx's native waiting
   music and a technician picks up MANUALLY. COMtrexx orbit 778 does NOT return
   the call to the AI on timeout, so there is **no automatic voicemail fallback
   after deflect**. The voicemail helpers in `esl_call_handler.py` are retained
   but NOT wired to escalation; wiring them would require COMtrexx to forward the
   timed-out orbit back to `003010` plus orbit-return detection (not implemented).
   The `AI_ESCALATION_*` / voicemail config vars only parameterize those retained
   helpers — they do not fire on the live escalation path.
6. **Templates only in repo.** XML files contain `YOUR_SIP_PASSWORD_HERE`
   placeholders. Never commit a real SIP password; never assume the repo XML is the
   deployed XML (deployed copies live under `/etc/freeswitch/...`).

## Mandatory checklist BEFORE editing

- [ ] Re-read `freeswitch/README.md` topology + address table.
- [ ] If touching ESL ports/hosts, list all three locations to update.
- [ ] If touching dialing, confirm the German gate + masking + confirmation stay intact.
- [ ] If touching prompts, confirm you're editing the correct layer.
- [ ] If touching escalation, re-check the min-hold ≤ transfer-timeout relationship.

## Mandatory checklist AFTER editing

- [ ] `test_phone_safety.py` and `test_voice_bugs_regression.py` pass.
- [ ] No raw phone number can reach logs, responses, or emails.
- [ ] ESL addresses consistent across `config.py`, XML, and `freeswitch/README.md`.
- [ ] XML still contains placeholders, not real secrets.
- [ ] `VOICE_MODE.md` / `freeswitch/README.md` updated for any protocol/topology change.
- [ ] If a deployed XML must change, the apply command (`reloadxml` /
      `sofia profile external restart`) is documented in the change notes.

## Validation commands

```bash
# Phone + voice safety (WSL debian12, .venv-wsl):
cd backend
../.venv-wsl/bin/python -m pytest tests/test_phone_safety.py tests/test_voice_bugs_regression.py -q

# Read-only runtime snapshot (only where FreeSWITCH is actually running):
bash backend/voice/freeswitch/verify_freeswitch.sh
```

## Documentation updates required

- `backend/voice/freeswitch/README.md` for any topology/address/dialplan change.
- `VOICE_MODE.md` for WS protocol, idempotency, or pipeline changes.
- `backend/voice/config.py` docstrings for any new/changed env var (and mirror in
  `.env.example`).
- `backend/voice/knowledge/*.md` when client triage/escalation rules change.

## Known repository risks

- Repo XML are **templates**; deployed files under `/etc/freeswitch/...` drift.
  `verify_freeswitch.sh` detects drift but must be run on the host.
- `config.py` still carries pyVoIP/SIP fields (`COMTREXX_LOCAL_SIP_PORT`,
  `sip_client.py`) and a WSL2-gateway default (`172.21.224.1`) for the
  Python-on-Windows topology — the **current** topology is FS+Python both in WSL
  using `127.0.0.1`. Don't follow the stale path.
- Whisper/TTS are prewarmed at startup; a missing model or non-writable
  `FREESWITCH_AUDIO_TEMP_DIR` silently degrades calls (logged, not fatal).
- SIP OPTIONS keep-alives are not calls — only an INVITE starts a session.

## Forbidden behavior

- Do NOT dial non-German numbers or bypass `is_german_number`.
- Do NOT log, return, or email a raw (unmasked) phone number.
- Do NOT dial without a confirmed pending request, or allow concurrent calls.
- Do NOT hardcode a specific client into Layer 1 (`llm_bridge.py`).
- Do NOT commit real SIP passwords or remove the XML placeholder convention.
- Do NOT change one ESL address location without the other two.
- Do NOT route new behavior through the legacy pyVoIP/`sip_client.py` path.
