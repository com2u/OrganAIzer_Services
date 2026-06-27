---
id: tfs-door-systems
type: product
owner: unassigned
status: draft
knowledge_version: 0.1   # door-communication integration entry; teaches when/how door systems fit the solution
last_reviewed: 2026-06-25
sources:
  - backend/voice/knowledge/teleprofi_fulda.md            # primary: Teleprofi business knowledge (door communication services)
  - Teleprofi operational knowledge (Renato, 2026-06-25)   # primary
  - knowledge/products/comtrexx-family.md                  # PBX integration (analog/IP door stations)
  - https://www.auerswald.de/de/produkt/tfs-universal-plus-2/reseller   # supporting: official Auerswald TFS
  - https://www.auerswald.de/de/produkt/tfs-dialog-300-serie/reseller   # supporting: official Auerswald TFS
category: door
vendor: Auerswald
model: TFS door intercom (TFS-Dialog / TFS-Universal); Siedle and others also supported
lifecycle: current
---

# TFS Door Systems — Teleprofi product knowledge

> Door-communication **integration** knowledge — **when** Teleprofi recommends an
> integrated door intercom and **how it fits** the COMtrexx-based business
> communication solution. This is a category/integration entry (Auerswald **TFS** is
> the named example; Teleprofi also fits **Siedle** and others — `teleprofi_fulda.md`),
> not a single-SKU spec sheet. Reusable principles live in `business-philosophy/`; the
> PBX/analog context lives in `comtrexx-family.md` — **referenced, not duplicated**.
>
> **Knowledge maturity: v0.1 (draft).** Specific TFS models, which brand Teleprofi
> standardises on, and exact video/mobile capabilities are **not yet confirmed** —
> captured as questions under **[Teleprofi Knowledge Needed](#teleprofi-knowledge-needed)**.

# Executive Summary

**What is it?** A **door intercom / door-communication system** (Türfreisprechsystem,
"TFS") integrated into the phone system: visitors press the door station, the call
**rings configured phones**, staff **talk to the door** and **open it from the phone**.
Auerswald **TFS** stations connect to COMtrexx via an **a/b (analog) port** (or an ATA
adapter for IP-only systems); **IP door stations** are also supported. Door-opener and
RFID access modules complete the system (Auerswald).

**Who is it for?** Businesses that want **door communication unified with their phones**
— answer the door and buzz people in from any desk phone, DECT handset, or (where
configured) a remote/mobile user.

**Why does Teleprofi sell it?** Door communication, door access and intercom integration
are **core Teleprofi services** (`teleprofi_fulda.md`). Integrating the door into the
COMtrexx solution is a natural **cross-sell** that adds real day-to-day value.

# Teleprofi Recommendation

Recommend an **integrated door system** when the customer wants the door tied into their
telephony — not a standalone intercom. Fit it to the PBX: an **a/b TFS door station
needs an analog port**, so it pairs naturally with **COMtrexx Flex** (4FXS analog
module) or via an **ATA** on **COMtrexx Next** (which has no analog ports) — i.e. a real
door requirement is one of the **"lean Flex" signals** (`comtrexx-family.md`). Which TFS
model / brand and the exact endpoints are scoped per site. The brand Teleprofi
standardises on (Auerswald TFS vs Siedle) is an open question (Q1).

# Typical Customer

Offices, practices, workshops, and multi-tenant/мailbox sites that need controlled
**visitor access** integrated with telephony (`teleprofi_fulda.md`). Often added to a
COMtrexx telephony project rather than sold alone. (Typical door-system customer profile
/ attach rate — Knowledge Needed Q2.)

# Typical Deployment

A door station at the entrance, wired back to the COMtrexx system — **a/b two-wire** to
an analog port (Flex 4FXS) or via an **ATA** (Next/IP), or an **IP door station** on the
LAN — with the **door opener** driven by an a/b switching module (and optional **RFID**
contactless access) (Auerswald). Door calls ring the configured endpoints; the door is
released from the phone. Cabling/network is part of Teleprofi's **network preparation**
(`services/network-preparation.md`).

# Typical Bundle

A door system rides on a complete telephony+network solution — referenced, not duplicated:

| Part | Reference |
|---|---|
| **PBX** | COMtrexx (`comtrexx-family.md`) — analog (Flex 4FXS) or ATA for a/b TFS, or IP door station |
| **Endpoints** | COMfortel **D-series** desk phones / COMfortel **M-series** DECT (ring the door) |
| **Network prep** | `../services/network-preparation.md` (cabling, PoE, IP door station) |
| **Provider + router** | [[provider-preference-philosophy]] / `fritzbox-family.md` (for remote/mobile door access) |
| **Installation + maintenance** | `../services/telephone-system-installation.md`, `../services/maintenance-contract.md` |

Pricing → `pricing/`.

# Strengths

- **Unified door + phone:** answer/open the door from existing phones — no separate intercom system to learn.
- **Flexible connection:** a/b (analog) **or** IP door stations; works with Flex analog
  modules or via ATA (Auerswald).
- **Access control add-ons:** a/b switching modules and **RFID** contactless door opener (Auerswald).
- Native fit into the Auerswald/COMtrexx ecosystem; one partner (Teleprofi) for door + phone + network.

# Limitations

- **Analog (a/b) TFS needs an analog port** — COMtrexx **Next has none** (needs an ATA),
  so an analog door requirement pushes toward **COMtrexx Flex** (`comtrexx-family.md`).
- **Video** at the phone depends on the door station **and** a compatible phone — not all
  endpoints show door video (confirm which COMfortel models — Q-official).
- Physical-access security must be designed deliberately (see Security considerations).

# Typical Installation

Part of Teleprofi's install + network prep: mount the door station, run a/b or LAN
cabling (`services/network-preparation.md`), connect to COMtrexx (analog port / ATA / IP),
configure the **call group** the door rings, set the **door-opener** code/module and any
**RFID** access; validate per [[installation-philosophy]]
(`services/telephone-system-installation.md`). (Teleprofi door-install checklist — Patrick backlog.)

# Integration with COMtrexx

The door station registers/connects to COMtrexx (a/b analog port — natural on **Flex**
with a 4FXS module; via **ATA** on **Next**; or an **IP door station**). COMtrexx routes
the door call to a configured group and handles the **door-opener** trigger. Exact
COMtrexx door-station capacity/config is referenced, not restated (`comtrexx-family.md`;
COMtrexx supports multiple IP door stations). (Confirm per-model door-station limits — Q-official.)

# Integration with COMfortel desk phones

A door call **rings the COMfortel D-series** desk phone; staff talk to the visitor and
**open the door** from the phone. **Door-camera video** may display on compatible phones
(plausibly the larger-screen **D-600**) — **confirm which models support door video** (Q-official).

# Integration with DECT handsets

Door calls can ring **COMfortel M-series** DECT handsets (`comfortel-m710.md` /
`comfortel-m730.md`) so staff answer/open the door **while mobile** on site (e.g. a
workshop with no one at reception). DECT is **audio** (no door video on the handset).
(Confirm DECT door-open workflow specifics — Q-official.)

# Integration with remote/mobile users

Where configured, a door call can reach a **remote/mobile user** via a softphone/mobile
app registered to COMtrexx (e.g. COMfortel SoftPhone), letting them answer and **release
the door remotely** — useful for staff off-site or working from home. Exact capability
and security posture **needs confirmation** (Q-official + Security).

# Security considerations

Door systems control **physical access**, so design deliberately:
- **Who may open the door** — restrict the door-opener function to authorised extensions/users.
- **RFID/transponder management** — issue/revoke transponders; the contactless opener is convenient but must be governed (Auerswald RFID option).
- **Remote door release** — only over authenticated, trusted paths; do **not** expose door
  control to the open internet (provider/router posture per [[provider-preference-philosophy]]).
- **IP door stations & cameras** — segment on the LAN (VLAN), and treat **door-camera video
  as personal data** (privacy/retention). (Teleprofi's actual door-security practice —
  Knowledge Needed Q3; relates to the repo's security posture.)

# Expansion possibilities

Multiple door stations (multi-entrance), additional **RFID** readers / switching modules,
and extra ring endpoints as the site grows (Auerswald). COMtrexx supports multiple door
stations (`comtrexx-family.md`). (Per-model expansion limits — Q-official.)

# Migration scenarios

- **Integrate an existing analog door/mailbox intercom** into the new COMtrexx system via
  **a/b** (TFS-Universal can be fitted to existing door/mailbox systems; Auerswald) — on
  **Next** via an ATA, on **Flex** via the 4FXS module.
- **Replace a legacy standalone intercom** with an integrated TFS/IP door system tied to
  the phones.
- A door requirement discovered during a PBX project is a **signal toward COMtrexx Flex**
  (analog support) — see `comtrexx-family.md`.

# Maintenance expectations

Firmware/updates per [[firmware-policy]] where the door station is IP/updatable; door
hardware (button, opener, RFID) is largely electromechanical — periodic checks. Delivered
under the maintenance contract (`services/maintenance-contract.md`;
[[maintenance-philosophy]]). (Door-system maintenance specifics — Q.)

# AI Recommendation Signals

**Recommend an integrated door system** on signals like *"answer/open the door from our
phones"*, *"ring the door to reception and the workshop DECT"*, *"buzz visitors in"*, or
*"replace our old intercom"*. **Tie it to the PBX:** an **analog/a/b door** requirement is
a **lean-Flex** signal (or needs an ATA on Next). Always scope **endpoints** (which desk
phones / DECT / mobile ring) and **access security**. Door **video** depends on endpoint
support — don't promise it without confirming the model.

# AI Conversation Example

Customer: *"We want staff to see and talk to whoever's at the door and buzz them in from
their desk phones — and ring the workshop cordless when reception is empty."*
→ An **integrated door-communication** signal → recommend a **TFS door station integrated
into COMtrexx**, ringing the **COMfortel desk phones** and the **M-series DECT** in the
workshop, with the **door opener** from the phone. Because it's an analog/a/b door, fit it
to **COMtrexx Flex** (4FXS) — or an **ATA** if they're on **Next** (`comtrexx-family.md`).
Confirm which phones can show **door video** and design the **door-release security**.
*(Cabling/IP-door-station work is part of network preparation,
`services/network-preparation.md`.)*

# Cross-selling Opportunities

- **PBX:** COMtrexx (`comtrexx-family.md`) — often **Flex** for analog door support.
- **Endpoints:** COMfortel **D-series** desk phones / **M-series** DECT (ring the door).
- **Network preparation:** `../services/network-preparation.md` (cabling / PoE / IP door station).
- **Provider + router:** [[provider-preference-philosophy]] / `fritzbox-family.md` (remote door access).
- **Installation + maintenance:** `../services/telephone-system-installation.md`,
  `../services/maintenance-contract.md`.
- **Access control / RFID** add-ons (Auerswald switching modules / RFID).

# Related Products

- `comtrexx-family.md` — the PBX (analog/IP door integration; Flex for a/b door).
- `comfortel-d210.md` / `comfortel-d400.md` / `comfortel-d600.md` — desk phones that ring the door.
- `comfortel-m710.md` / `comfortel-m730.md` — DECT handsets that ring the door.
- `fritzbox-family.md` — the edge/router (remote/mobile door access).

# Related (reusable knowledge)

- Philosophy: [[product-selection-philosophy]], [[installation-philosophy]],
  [[firmware-policy]], [[maintenance-philosophy]], [[provider-preference-philosophy]].
- Services: `../services/network-preparation.md`,
  `../services/telephone-system-installation.md`, `../services/maintenance-contract.md`.

# Teleprofi Knowledge Needed

**Renato (commercial / selection):**
1. Which **door-system brand/line** does Teleprofi standardise on — **Auerswald TFS**,
   **Siedle**, or per-customer — and why? (`teleprofi_fulda.md` flags Siedle models as TBC.)
2. How often is a door system **attached** to a telephony project, and the typical customer?
4. Is the door requirement used as a deliberate **"go Flex"** argument in sales?

**Patrick (technician / hands-on):**
3. Teleprofi's **door-install + access-security** practice (who may open, RFID handling,
   IP-door-station network isolation, camera/privacy).
5. Door-install **checklist** and common **support calls** (opener, a/b vs IP, video).

**Official facts to confirm:**
- Which **COMfortel models display door-camera video**; DECT/mobile door-open workflow.
- Per-COMtrexx-model **door-station limits** (a/b and IP).
- Specific current **TFS models** Teleprofi fits.

# Knowledge History

| Version | Date | Change | Source |
|---|---|---|---|
| 0.1 | 2026-06-25 | Door-communication integration entry (final Phase 1 product): when/how a door system fits the COMtrexx solution, a/b-vs-IP + Flex-analog tie-in, endpoint integration (desk/DECT/mobile), security considerations, migration; specific models/brand/video capability captured as questions (not invented) | repo Teleprofi door services + official Auerswald TFS + comtrexx-family |

# Knowledge Confidence

| Area | Confidence | Reason |
|---|---|---|
| Door integrates with COMtrexx (a/b / ATA / IP) + door opener / RFID | high | official Auerswald TFS |
| Analog door → Flex (4FXS) / ATA on Next | high | official + `comtrexx-family.md` |
| Endpoint integration concept (desk/DECT/mobile ring + open) | medium | concept sound; exact workflows/video to confirm |
| Brand Teleprofi standardises on (TFS vs Siedle) | needs-confirmation | not captured — Q1 (Siedle TBC in `teleprofi_fulda.md`) |
| Door video on phones / DECT / mobile specifics | needs-confirmation | Q-official |
| Door-install & access-security practice | needs-confirmation | Q3 + Patrick backlog |
| Specific TFS models + per-model door limits | needs-confirmation | Q-official |
