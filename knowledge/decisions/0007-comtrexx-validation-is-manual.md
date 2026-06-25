---
id: 0007-comtrexx-validation-is-manual
type: decision
owner: pipeline-guardian
status: accepted
last_reviewed: 2026-06-24
sources:
  - .claude/skills/comtrexx-integration-guardian/SKILL.md
  - .claude/skills/pipeline-guardian/SKILL.md
  - backend/voice/freeswitch/verify_freeswitch.sh
  - backend/tests/test_phone_safety.py
---

# 0007 — COMtrexx validation is manual; CI must not depend on a live PBX

## Status

Accepted.

## Context

Live telephony — gateway registration, an inbound INVITE reaching extension
`003010`, deflect into the orbit, and manual pickup — cannot run in automated CI.
Backend tests are hermetic (no real network, FreeSWITCH, COMtrexx, or SIP).

## Decision

COMtrexx/SIP validation is a manual, out-of-band checklist on the FreeSWITCH host.
CI must not depend on live PBX access, SIP registration, or real phone calls.

## Reasoning

Hermetic tests pin the escalation mechanism (deflect-not-bridge, ADR 0001) via
source assertions and mocks. Live behavior depends on out-of-repo COMtrexx
configuration and a real PBX, which cannot be reproduced in CI and would make the
suite non-portable.

## Consequences

- The deflect-not-bridge guarantee is checked in CI by source/mechanism assertions.
- Live behavior is validated manually using `verify_freeswitch.sh` and a test call
  (gateway `REGED`, INVITE to `003010`, deflect to `778`/`779`, no
  `INCOMPATIBLE_DESTINATION`).
- The automated suite stays runnable anywhere without a PBX.

## Related Sources

- `.claude/skills/comtrexx-integration-guardian/SKILL.md` — live validation
  checklist and CI test limitations.
- `.claude/skills/pipeline-guardian/SKILL.md` — no live-PBX dependency in CI.
- `backend/voice/freeswitch/verify_freeswitch.sh` — read-only runtime snapshot.
- `backend/tests/test_phone_safety.py` — `TestEscalationUsesDeflect` (mechanism gate).
