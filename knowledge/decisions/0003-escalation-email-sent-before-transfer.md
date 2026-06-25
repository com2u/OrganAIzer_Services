---
id: 0003-escalation-email-sent-before-transfer
type: decision
owner: escalation-email-privacy-guardian
status: accepted
last_reviewed: 2026-06-24
sources:
  - backend/voice/esl_call_handler.py
  - backend/voice/escalation.py
  - "commit 939404e — Improve escalation email workflow"
---

# 0003 — Escalation email is sent before the transfer

## Status

Accepted.

## Context

On escalation, the system generates a call summary and sends the escalation email,
then deflects the caller into the orbit. In `_conversation_loop`, `handle_escalation`
(which sends the email) is called before the deflect loop runs.

## Decision

The escalation email is generated and sent before the caller is deflected into the
COMtrexx orbit.

## Reasoning

The deflect (SIP REFER) ends the AI's control of the call; after a successful
transfer the AI cannot reliably perform additional actions on that call. Sending
the email first ensures the operator handoff record is delivered regardless of the
transfer outcome.

## Consequences

- The operator receives the escalation email even if the transfer fails.
- The email carries the waiting-room and pickup details needed for the manual
  handoff (see ADR 0004 and the escalation-email-privacy-guardian skill).
- `handle_escalation` skips its own transfer attempt when the live ESL handler is
  present; the deflect is performed afterward by `_conversation_loop`.

## Related Sources

- `backend/voice/esl_call_handler.py` — `_conversation_loop`: `handle_escalation`
  call precedes the deflect loop.
- `backend/voice/escalation.py` — `handle_escalation` (summary + email send;
  transfer skipped when `esl_handler` is provided).
- Commit: `939404e` (escalation email workflow).
