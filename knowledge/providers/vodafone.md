---
id: vodafone
type: provider
owner: unassigned
status: draft
last_reviewed: 2026-06-25
sources:
  - backend/voice/knowledge/teleprofi_fulda.md
  - https://www.vodafone.de/business/festnetz-internet/all-ip-anschluss/
  - https://www.vodafone.de/business/blog/sip-anlagenanschluss-10351/
  - https://www.vodafone.de/business/hilfe-support/glasfaser-anschluss/
provider_type: carrier
country: DE
supported_services: [sip-trunk, fiber, dsl, all-ip]
---

# Overview

> Vodafone — a major German carrier offering business All-IP / SIP-Anlagenanschluss
> telephony together with fiber and DSL/cable Internet access.

Vodafone supplies Internet and SIP telephony that products depend on. Described
objectively here; recommendation logic lives in
[`../ai-rules/provider-selection.md`](../ai-rules/provider-selection.md).

# Business Position

Vodafone is one of the major German carriers offering business connectivity. For
telephony it provides an All-IP / SIP-Anlagenanschluss, and it typically **bundles
its SIP-Trunk with an Internet connection** rather than selling a standalone trunk
(per Vodafone Business documentation). It is an established alternative to the
incumbent for business Internet and telephony.

# Customer View

## Benefits
- All-IP telephony (SIP-Anlagenanschluss) for connecting a business PBX.
- Internet + telephony from one provider via bundled connections.
- Business fiber access where available, offering higher, more stable bandwidth
  than DSL/VDSL (Vodafone Business fiber documentation).

## Typical customers
- Businesses that already have Vodafone Internet/cable and want telephony on the
  same provider.
- Companies whose requirements are met by Vodafone's bundled All-IP offering.

## Limitations
- SIP-Trunk is generally **bundled with an Internet connection**, which makes
  direct comparison with standalone SIP-Trunks harder (Vodafone documentation).
- Encryption/transport specifics for the SIP-Anlagenanschluss must be confirmed
  against Vodafone's current technical documentation before relying on them.
  *(Needs confirmation — not asserted here to avoid invented specs.)*

# Sales View

## When to recommend
- Customer already has Vodafone Internet/cable and requirements are met by the
  bundled All-IP offering.
- Sites where Vodafone business fiber is available and fits the customer's needs.

## When NOT to recommend
- When a specific PBX feature requires a SIP-Trunk capability Vodafone does not
  document as supported. *(Confirm per requirement.)*

## Migration scenarios
- ISDN → All-IP migration onto a Vodafone SIP-Anlagenanschluss.
- Number porting to/from Vodafone (a core Teleprofi service).

## Upsell opportunities
- Fiber upgrade where available; additional voice channels as the customer grows.

# Technician View

> Only document what Vodafone's official sources state. Do not invent specs or
> compare aggressively against other carriers.

## SIP compatibility
Vodafone provides an **All-IP / SIP-Anlagenanschluss** for connecting a business
PBX, with voice channels delivered over the SIP protocol (Vodafone Business
documentation). Specific transport/encryption parameters (TLS/SRTP support,
ports) must be taken from Vodafone's current technical specification at
configuration time. *(Confirm against Vodafone docs — not asserted here.)*

## Fiber compatibility
Vodafone offers business fiber access; per Vodafone, full fiber delivers
significantly higher and more stable bandwidth than DSL/VDSL. Availability is
address-dependent.

## DSL compatibility
DSL and cable Internet access are offered for business. Availability is
address-dependent.

## Router compatibility
Community/integration documentation shows the AVM FRITZ!Box used with the
Vodafone SIP-Anlagenanschluss; confirm the specific model and configuration
against Vodafone's current docs. *(Per-model check.)*

## PBX compatibility
Third-party integration notes describe Auerswald PBXs configured against a
Vodafone SIP-Anlagenanschluss; validate against Vodafone's current technical
specification for the exact COMtrexx firmware. *(Per-firmware check.)*

## Typical configuration considerations
- Trunk is typically tied to the bundled Internet connection.
- Confirm channel count, transport and encryption parameters from Vodafone's
  current spec before provisioning.

## Common issues
- Registration/configuration issues stemming from spec mismatch; use standard SIP
  triage (`procedures/comtrexx-registration-troubleshooting.md`).

## Troubleshooting references
- `procedures/comtrexx-registration-troubleshooting.md`
- `procedures/freeswitch-diagnostics.md`
- Official: Vodafone Business Hilfe & Support.

# Support Experience

Teleprofi's concrete operational experience with Vodafone business support is
**experiential and to be filled in by Teleprofi** (dated, marked as experience).
*(Needs human input.)*

# Related Products

- Auerswald COMtrexx PBXs and AVM FRITZ!Box routers (see `products/` once entries
  exist).

# Related Procedures

- `procedures/comtrexx-registration-troubleshooting.md`
- `procedures/freeswitch-diagnostics.md`

# Related ADRs

- (None specific to Vodafone yet.)

# Related Providers

- [`telekom.md`](./telekom.md)
- [`o2.md`](./o2.md)

# Open Questions

- Vodafone SIP-Anlagenanschluss encryption/transport specifics (TLS/SRTP, ports)
  for COMtrexx. *(Needs human confirmation against Vodafone's current spec.)*
- Which FRITZ!Box / COMtrexx firmware combinations are validated against Vodafone.
  *(Needs human confirmation.)*
- Teleprofi's operational support experience with Vodafone. *(Needs human input.)*
