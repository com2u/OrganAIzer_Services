---
id: comtrexx
type: infrastructure
owner: comtrexx-integration-guardian
status: active
last_reviewed: 2026-06-24
sources:
  - backend/voice/freeswitch/comtrexx_gateway.xml
  - backend/voice/freeswitch/README.md
  - backend/voice/config.py
---

# COMtrexx (PBX integration boundary)

> References authoritative sources; does not restate the PBX address, extension, or
> orbit values (those live in the gateway XML / `config.py` / freeswitch README).

## Purpose

The Auerswald COMtrexx PBX is the telephony boundary: inbound calls enter through
it to the AI extension, and escalations are parked in its waiting-room orbits.

## Responsibilities

- Register/accept the FreeSWITCH `comtrexx` gateway.
- Route inbound external calls to the AI extension.
- Provide the waiting-room park orbits and native waiting music.
- Accept escalation re-routes via SIP REFER (deflect) from the internal AI
  extension (ADR 0001), where a technician picks up manually (ADR 0002).

## Dependencies

- The FreeSWITCH gateway — see `knowledge/infrastructure/freeswitch.md`.
- COMtrexx admin-side configuration (routing to the AI extension, orbit settings),
  which is managed in the COMtrexx admin UI, outside the repository.

## Consumers

- The FreeSWITCH/backend voice path.
- Callers (inbound) and parked callers awaiting manual pickup.

## Related ADRs

- ADR 0001 — Deflect (SIP REFER) instead of bridge() for orbit escalation.
- ADR 0002 — No automatic voicemail fallback after orbit transfer.
- ADR 0007 — COMtrexx validation is manual; CI must not depend on a live PBX.
- ADR 0008 — German-only outbound dialing.

## Related Procedures

- `knowledge/procedures/comtrexx-registration-troubleshooting.md`
- `knowledge/procedures/voice-escalation-validation.md`

## Source of Truth

- `backend/voice/freeswitch/comtrexx_gateway.xml` — gateway template (placeholder
  password).
- `backend/voice/freeswitch/README.md` — topology and address table.
- `backend/voice/config.py` — COMtrexx-facing settings.

## Known Limitations

- A direct bridge to an orbit via the gateway is rejected by COMtrexx
  (`INCOMPATIBLE_DESTINATION`, cause 88) — only deflect works (ADR 0001).
- A successfully parked call is not returned to the AI on orbit timeout; pickup is
  manual (ADR 0002).
- **Needs Human Confirmation:** COMtrexx-side routing to the AI extension, orbit
  timeout values, and any orbit→AI-extension forwarding are configured in the
  COMtrexx admin UI and are not defined in the repository.

## Ownership

`comtrexx-integration-guardian`.
