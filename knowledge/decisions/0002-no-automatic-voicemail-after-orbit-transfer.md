---
id: 0002-no-automatic-voicemail-after-orbit-transfer
type: decision
owner: comtrexx-integration-guardian
status: accepted
last_reviewed: 2026-06-24
sources:
  - backend/voice/esl_call_handler.py
  - backend/voice/config.py
  - backend/voice/freeswitch/README.md
  - "commit 9da3a64 — Restore COMtrexx deflect escalation flow"
  - "commit 12fef18 — Document COMtrexx deflect escalation behavior"
---

# 0002 — No automatic voicemail fallback after a successful orbit transfer

## Status

Accepted.

## Context

After a successful deflect (ADR 0001), COMtrexx owns the call in the park orbit.
COMtrexx park orbit `778` does not return control to the AI on timeout. Voicemail
helper functions exist in `esl_call_handler.py` but are retained and deliberately
not wired into the escalation path.

## Decision

There is no automatic voicemail fallback after a successful orbit transfer. Pickup
from the orbit is manual.

## Reasoning

The deflect (SIP REFER) releases the AI's call leg, and the orbit does not return
the call to extension `003010`, so the AI cannot record a voicemail on that call.
A future automatic voicemail would require both (a) COMtrexx configured to forward
the timed-out orbit back to `003010`, and (b) orbit-return detection in the
backend. Neither exists; this ADR records the current accepted behavior, not a
commitment to build the fallback.

## Consequences

- The caller waits in the orbit for a manual pickup by a technician.
- The voicemail helpers stay present in the code but uninvoked from escalation.
- The escalation email (ADR 0003) is the operator's handoff trigger.

## Related Sources

- `backend/voice/esl_call_handler.py` — retained-voicemail section comment;
  `_conversation_loop` (no voicemail call after deflect).
- `backend/voice/config.py` — escalation/voicemail settings comments.
- `backend/voice/freeswitch/README.md` — "Escalation / waiting room".
- Commits: `9da3a64` (restore + code comments), `12fef18` (docs).
