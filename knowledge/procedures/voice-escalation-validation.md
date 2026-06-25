---
id: voice-escalation-validation
type: procedure
owner: comtrexx-integration-guardian
status: active
last_reviewed: 2026-06-24
sources:
  - backend/voice/esl_call_handler.py
  - backend/voice/freeswitch/README.md
  - backend/tests/test_phone_safety.py
  - backend/voice/freeswitch/verify_freeswitch.sh
  - .claude/skills/comtrexx-integration-guardian/SKILL.md
---

# Voice escalation validation

## When to use

After any change to escalation, the deflect/orbit flow, the escalation email, or
COMtrexx-facing config — to confirm escalation still parks the caller correctly and
the operator handoff is produced.

## Prerequisites

- For the automated mechanism check: WSL debian12 + `.venv-wsl` (see
  `backend-validation`).
- For the live check: a running FreeSWITCH host with the `comtrexx` gateway `REGED`
  (see `comtrexx-registration-troubleshooting`) and the ability to place a real
  call. Live telephony cannot run in CI (ADR 0007).

## Steps

1. **Automated mechanism gate (hermetic, no PBX).** From `backend/`, inside WSL:
   ```bash
   ../.venv-wsl/bin/python -m pytest tests/test_phone_safety.py -q
   ```
   The `TestEscalationUsesDeflect` class asserts escalation uses SIP REFER
   (`deflect`) and never a bridge to the gateway.
2. **Live validation (manual, on the FreeSWITCH host).** Place a test call,
   trigger escalation, and watch the FreeSWITCH log:
   ```bash
   bash backend/voice/freeswitch/verify_freeswitch.sh
   ```

## Validation

- The hermetic test run passes `TestEscalationUsesDeflect`.
- In the live FreeSWITCH log, escalation shows a `deflect`/REFER to
  `sip:778@…` (then `779`), **not** `bridge sofia/gateway/comtrexx/778`.
- No `INCOMPATIBLE_DESTINATION` / cause 88 appears.
- The caller hears COMtrexx native waiting music; a technician can pick up manually
  from orbit `778` (then `779`).
- An escalation email is received with the waiting room and Call-ID (see the
  escalation-email-privacy-guardian).

## Expected outcomes

- Escalation parks the caller via deflect into orbit `778`/`779`; pickup is manual.
- No automatic voicemail occurs after a successful transfer (ADR 0002).

## Common failure modes

- **`INCOMPATIBLE_DESTINATION` (cause 88)** — escalation is using a bridge to the
  orbit instead of deflect (the ADR 0001 regression). The mechanism test should
  fail in this case.
- **No INVITE on the call** — COMtrexx is not routing to `003010` (see
  `comtrexx-registration-troubleshooting`).
- **Caller dropped straight to a farewell** — both orbit deflects did not complete
  (the `_conversation_loop` farewell path).

## Recovery

- If a bridge-to-orbit regression is present, restore the deflect mechanism per
  ADR 0001 (`9da3a64` is the reference restore commit) and re-run the mechanism test.

## Notes

- **Needs Human Confirmation:** COMtrexx orbit timeout values and any orbit→`003010`
  forwarding are COMtrexx-side configuration, not defined in the repository.
