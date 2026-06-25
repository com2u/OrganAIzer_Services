---
id: freeswitch
type: infrastructure
owner: voice-freeswitch-guardian
status: active
last_reviewed: 2026-06-24
sources:
  - backend/voice/freeswitch/README.md
  - backend/voice/freeswitch/inbound_ai_dialplan.xml
  - backend/voice/freeswitch/comtrexx_gateway.xml
  - backend/voice/freeswitch/default_transfer_dialplan.xml
  - backend/voice/freeswitch/verify_freeswitch.sh
  - backend/voice/config.py
---

# FreeSWITCH (voice bridge)

> References authoritative sources; does not restate addresses, ports, or extensions.

## Purpose

The telephony engine that bridges the COMtrexx PBX and the backend over ESL. It
registers the COMtrexx gateway, routes inbound calls to the AI, and carries
escalation transfers.

## Responsibilities

- Register and maintain the `comtrexx` gateway (external SIP profile).
- Route inbound calls (to the AI extension) into the backend via the ESL outbound
  socket (`inbound_ai_dialplan.xml`).
- Execute escalation transfers via SIP REFER (deflect) to the COMtrexx orbits
  (ADR 0001).
- Provide a read-only runtime diagnostic (`verify_freeswitch.sh`).

## Dependencies

- The FreeSWITCH runtime (deployed on the WSL host; out of repo).
- The COMtrexx PBX gateway — see `knowledge/infrastructure/comtrexx.md`.
- The backend ESL listener — see `knowledge/infrastructure/backend.md`.
- Deployed dialplan/gateway XML under `/etc/freeswitch/...` (repo files are
  templates).

## Consumers

- The backend (receives ESL connections per call).
- Callers, via COMtrexx.

## Related ADRs

- ADR 0001 — SIP REFER (deflect) instead of bridge() for orbit escalation.
- ADR 0002 — No automatic voicemail fallback after orbit transfer.
- ADR 0007 — COMtrexx validation is manual; CI must not depend on a live PBX.

## Related Procedures

- `knowledge/procedures/freeswitch-diagnostics.md`
- `knowledge/procedures/comtrexx-registration-troubleshooting.md`
- `knowledge/procedures/voice-escalation-validation.md`

## Source of Truth

- `backend/voice/freeswitch/README.md` — topology and address table.
- `backend/voice/freeswitch/*.xml` — gateway and dialplan templates.
- `backend/voice/config.py` — ESL/COMtrexx-facing settings.
- `backend/voice/freeswitch/verify_freeswitch.sh` — runtime diagnostic.

## Known Limitations

- Repo XML are templates; deployed copies under `/etc/freeswitch/...` can drift
  (`verify_freeswitch.sh` detects drift, host-only).
- The FreeSWITCH runtime is out of repo; live behavior is validated manually.
- `default_transfer_dialplan.xml` bridges `77x` via the gateway, which is the
  wrong mechanism for orbits (cause 88) — deflect is canonical (ADR 0001).

## Ownership

`voice-freeswitch-guardian`.
