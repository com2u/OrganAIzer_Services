---
id: telekom
type: provider
owner: unassigned
status: draft
last_reviewed: 2026-06-25
sources:
  - backend/voice/knowledge/teleprofi_fulda.md
  - https://hilfe.companyflex.de/de/grundlagen/systemvoraussetzungen
  - https://hilfe.companyflex.de/de/endgeraete/ueberblick
  - https://geschaeftskunden.telekom.de/internet-dsl/tarife/companyflex/sip-trunk/sip-trunk-technische-unterlage
provider_type: carrier
country: DE
supported_services: [sip-trunk, fiber, dsl, all-ip]
---

# Overview

> Deutsche Telekom — Germany's incumbent carrier, supplying business Internet,
> fiber/DSL access and the CompanyFlex / DeutschlandLAN SIP-Trunk telephony that
> Teleprofi's PBX deployments register to.

Telekom provides the connectivity layer beneath Teleprofi's products: Internet
access (fiber and DSL) and business telephony via SIP-Trunk. The PBXs Teleprofi
installs (Auerswald COMtrexx) and the routers it deploys (AVM FRITZ!Box) connect
*through* Telekom services. This file is business and technical knowledge only;
how OrganAIzer decides to recommend Telekom lives in
[`../ai-rules/provider-selection.md`](../ai-rules/provider-selection.md).

# Business Position

Telekom is the incumbent German carrier with the broadest business-grade
footprint for fiber, DSL and SIP telephony. Its business arm
(Geschäftskunden / DeutschlandLAN) focuses on professional connectivity and
SIP-Trunk telephony for companies. Teleprofi's repository describes DSL/fiber
connection work and SIP-Trunk provisioning as core services, with Telekom as a
routinely-coordinated provider. *(Positioning, not a superlative claim.)*

# Customer View

## Benefits
- Broad nationwide business coverage for fiber and DSL access.
- Established business telephony via the CompanyFlex / DeutschlandLAN SIP-Trunk.
- Encrypted SIP telephony (VoSIP) is documented and supported (see Technician View).

## Typical customers
- New business installations needing reliable business-grade telephony plus
  Internet from a single incumbent carrier.
- Companies running a professional PBX (e.g. Auerswald COMtrexx) that needs a
  well-documented, standards-based SIP-Trunk.

## Limitations
- Encrypted-SIP requirements (TLS/SRTP, certificates) add configuration steps the
  PBX must satisfy — see Technician View.
- Specific tariff availability (fiber vs. DSL at a given address) is
  address-dependent and must be checked per site. *(Needs confirmation per site.)*

# Sales View

## When to recommend
- New business installations where standards-based, encryption-capable SIP
  telephony and professional PBX compatibility matter.
- Sites where Telekom fiber/DSL business access is available.

## When NOT to recommend
- When the customer already has a working Vodafone or O₂ installation that meets
  requirements — do not pressure a change (see AI rules).
- When a specific required tariff/feature is not available at the customer's
  address.

## Migration scenarios
- ISDN → All-IP / SIP-Trunk migrations; number porting
  (Rufnummernportierung) is a core Teleprofi service.
- Moving an existing PBX onto a CompanyFlex SIP-Trunk with TLS/SRTP enabled.

## Upsell opportunities
- Fiber upgrade where business fiber is available at the site.
- Additional voice channels / number blocks on the SIP-Trunk as the customer grows.

# Technician View

> Encryption and transport facts below are cited from Telekom's official
> CompanyFlex / DeutschlandLAN documentation. Reference operational config
> (ports, certificates, COMtrexx values) at its single source of truth; do not
> copy values into product/customer files.

## SIP compatibility
Telekom's CompanyFlex / DeutschlandLAN SIP-Trunk uses **VoSIP (Voice over Secure
IP)**. Per Telekom's documentation:
- **TLS over TCP** is the SIP transport layer; **port 5061** must be configured on
  the endpoint.
- **SRTP** is used for media encryption and must be enabled; **TLS and SRTP must
  be used in combination** (exception: T.38).
- Additional **mediasec** SIP headers and SDP attributes must be supported.
- The **T-TeleSec GlobalRoot Class 2** root certificate is required on the
  endpoint to validate the TLS connection.
- The PBX must support the **SIP-over-TLS client at TLS 1.2**; supported TLS
  versions and cipher suites are defined in Telekom specs **1TR114 (Annex 2)** and
  **1TR119**.

Sources: CompanyFlex Systemvoraussetzungen and Endgeräte-Überblick; DeutschlandLAN
SIP-Trunk technische Unterlage (linked in frontmatter).

## Fiber compatibility
Telekom offers business fiber access; availability is address-dependent.
*(Exact products/speeds per site need confirmation.)*

## DSL compatibility
DSL/VDSL business access is supported and is a routine Teleprofi connection type
(`teleprofi_fulda.md` — "DSL und Glasfaser … Provider-Koordination").

## Router compatibility
Teleprofi standardly deploys **AVM FRITZ!Box** routers (`teleprofi_fulda.md`).
CompanyFlex documents supported routers/PBXs in its Endgeräte overview; confirm a
specific FRITZ!Box model is listed before relying on it. *(Per-model check.)*

## PBX compatibility
Teleprofi installs **Auerswald COMtrexx** PBXs (`teleprofi_fulda.md`). The PBX must
satisfy the VoSIP requirements above (TLS 1.2, SRTP, mediasec, T-TeleSec root
cert). Confirm the specific COMtrexx firmware supports the required cipher suites
per 1TR114 Annex 2. *(Per-firmware check.)*

## Typical configuration considerations
- Configure SIP transport TLS on port 5061; enable SRTP.
- Install the T-TeleSec GlobalRoot Class 2 root certificate on the PBX.
- Enable mediasec header/SDP support.

## Common issues
- Registration fails when TLS/SRTP or the required root certificate is not
  configured. (General SIP-registration triage: `procedures/comtrexx-registration-troubleshooting.md`.)

## Troubleshooting references
- `procedures/comtrexx-registration-troubleshooting.md`
- `procedures/freeswitch-diagnostics.md`
- Official: CompanyFlex Hilfe (hilfe.companyflex.de).

# Support Experience

Teleprofi routinely coordinates with Telekom for DSL/fiber connections and
SIP-Trunk provisioning (`teleprofi_fulda.md`). Detailed, dated support-experience
notes (responsiveness, escalation paths) are **operational experience to be filled
in by Teleprofi** and should be marked as experiential. *(Needs human input.)*

# Related Products

- Auerswald COMtrexx PBXs and AVM FRITZ!Box routers (see `products/` once entries
  exist).

# Related Procedures

- `procedures/comtrexx-registration-troubleshooting.md`
- `procedures/freeswitch-diagnostics.md`

# Related ADRs

- (None specific to Telekom yet.)

# Related Providers

- [`vodafone.md`](./vodafone.md)
- [`o2.md`](./o2.md)

# Open Questions

- Which exact COMtrexx firmware versions are validated against CompanyFlex
  1TR114 Annex 2 cipher suites? *(Needs human confirmation.)*
- Which FRITZ!Box models are on Telekom's current CompanyFlex supported-endpoint
  list? *(Needs human confirmation.)*
- Teleprofi's concrete operational support experience with Telekom (for the
  Support Experience section). *(Needs human input.)*
- The statement that Teleprofi prefers Telekom for new business installations is
  captured as a **decision rule** in `ai-rules/provider-selection.md`, not as a
  fact here.
