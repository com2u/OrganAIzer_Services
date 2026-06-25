---
id: 0001-deflect-not-bridge-for-orbit-escalation
type: decision
owner: comtrexx-integration-guardian
status: accepted
last_reviewed: 2026-06-24
sources:
  - backend/voice/esl_call_handler.py
  - backend/voice/freeswitch/README.md
  - backend/voice/config.py
  - backend/tests/test_phone_safety.py
  - "commit e6ce4d7 — Add FreeSWITCH hold music fallback safety (introduced the bridge regression)"
  - "commit 9da3a64 — Restore COMtrexx deflect escalation flow"
  - "commit 12fef18 — Document COMtrexx deflect escalation behavior"
---

# 0001 — Use SIP REFER (deflect) instead of bridge() for COMtrexx orbit escalation

## Status

Accepted.

## Context

Escalation parks the caller in the COMtrexx park orbits `778` (primary) and `779`
(secondary). Commit `e6ce4d7` replaced the original SIP REFER (deflect) with a
direct `bridge sofia/gateway/comtrexx/{ext}`. COMtrexx rejected the bridge with
cause 88 `INCOMPATIBLE_DESTINATION`, because an INVITE arriving from the trunk
gateway is not a valid route to an internal park orbit. The waiting room stopped
working.

## Decision

Escalation transfers the caller to orbit `778`, then `779`, using SIP REFER via the
FreeSWITCH `deflect` application: `deflect sip:{ext}@{COMTREXX_IP}`. A `bridge()` to
the COMtrexx gateway must not be used for `778`/`779`.

## Reasoning

The REFER originates from the AI's internal extension `003010`, which COMtrexx
accepts as a re-route to its own park orbit; the trunk-side INVITE produced by a
bridge is not accepted (cause 88). With deflect, the caller is transferred
successfully and hears COMtrexx's native waiting music.

## Consequences

- Escalation works and the caller hears native COMtrexx orbit music.
- After the deflect, the AI's call leg is released (see ADR 0002 and ADR 0003).
- `default_transfer_dialplan.xml`'s bridge-to-gateway route for `77[89]` is the
  same trunk-INVITE pattern and is not the canonical orbit mechanism.
- The behavior is pinned by `TestEscalationUsesDeflect` in `test_phone_safety.py`
  (asserts deflect is used and bridge-to-gateway is absent).

## Related Sources

- `backend/voice/esl_call_handler.py` — `_conversation_loop` deflect loop.
- `backend/voice/freeswitch/README.md` — "Escalation / waiting room".
- `backend/voice/config.py` — `COMTREXX_IP`, `AI_WAITING_ROOM_PRIMARY/SECONDARY`.
- `backend/tests/test_phone_safety.py` — `TestEscalationUsesDeflect`.
- Commits: `e6ce4d7` (regression), `9da3a64` (restore), `12fef18` (docs).
