---
id: fritz-repeater-6000
type: product
owner: unassigned
status: draft
knowledge_version: 0.1   # first networking entry; sets the networking standard. Teleprofi gaps are interview questions
last_reviewed: 2026-06-25
sources:
  - backend/voice/knowledge/teleprofi_fulda.md             # primary: Teleprofi business knowledge
  - Teleprofi operational knowledge (Renato, 2026-06-25)    # primary
  - knowledge/products/fritzbox-family.md                   # router context (not duplicated)
  - https://fritz.com/en/products/fritz-repeater-6000-20002908   # supporting: official AVM
category: repeater
vendor: AVM
model: FRITZ!Repeater 6000
lifecycle: current
---

# AVM FRITZ!Repeater 6000 — Teleprofi product knowledge

> Captures **Teleprofi's** knowledge of when, why and how it sells, installs and
> supports the FRITZ!Repeater 6000. This is the **first networking entry** and sets
> the networking-product pattern. Router selection lives in
> [`fritzbox-family.md`](./fritzbox-family.md); reusable principles in
> `business-philosophy/` — both **referenced, not repeated**. The repeater extends a
> FRITZ!Box network; it is **not** a router and is not part of the router-selection
> table.
>
> **Knowledge maturity: v0.1 (draft).** Teleprofi-specific gaps are precise questions
> under **[Teleprofi Knowledge Needed](#teleprofi-knowledge-needed)**.

# Executive Summary

**What is it?** AVM's flagship **tri-band Wi-Fi 6 mesh repeater** — three radios
(2× 5 GHz, 1× 2.4 GHz, up to ~6 Gbit/s aggregate), with a **2.5-Gigabit and a
1-Gigabit LAN port** for wired backhaul or wired clients, joining a FRITZ! Mesh (AVM).

**Who is it for?** Customers with **Wi-Fi coverage gaps** (dead spots, distant rooms,
upper floors) who already run — or are getting — a **FRITZ!Box**, and want to extend
coverage **within the AVM ecosystem**.

**Why does Teleprofi sell it?** It extends Wi-Fi coverage while keeping the whole
network in **one AVM ecosystem** (FRITZ! Mesh) — which simplifies management and
support for both Teleprofi and the customer (see Mesh philosophy). Wi-Fi/coverage work
is a core Teleprofi service (`teleprofi_fulda.md`: Wi-Fi deployment, coverage
planning/testing, repeater installation/validation).

# Teleprofi Recommendation

Recommend the Repeater 6000 to **extend coverage of an existing/planned FRITZ!Box
network**, ideally **scoped by a coverage survey** so placement and quantity are right
(`services/wifi-site-survey.md`). It is positioned as **part of a complete solution
with the appropriate FRITZ!Box** ([`fritzbox-family.md`](./fritzbox-family.md)) — not
as a standalone fix bolted onto an unknown network. Where coverage needs are large or
structural, a **wired approach** may fit better (see "When another solution…").

# Typical Customer

Existing Teleprofi telephony/network customers with **patchy Wi-Fi** — back offices,
warehouses, upper floors, outbuildings (`teleprofi_fulda.md`: typical wireless issues
— coverage, roaming, registration). Usually already on a FRITZ!Box edge. (Teleprofi's
typical repeater count per site / when one isn't enough — Knowledge Needed Q1.)

# Typical Deployment

Added to a FRITZ!Box network to fill coverage gaps, joined to the **FRITZ! Mesh**
(one Wi-Fi name, coordinated band steering). Teleprofi's Wi-Fi work routinely includes
**coverage planning, coverage testing, repeater installation, repeater validation and
performance verification** — including **repeater-to-repeater and repeater-to-router**
checks and coverage measurements (`teleprofi_fulda.md`, Wireless Infrastructure).
Backhaul can be wireless or **wired (2.5G/1G LAN)** where cabling exists — wired
backhaul is preferred for stability where practical (confirm Teleprofi default —
Knowledge Needed Q2).

# Mesh philosophy

**Stay in one AVM ecosystem.** A FRITZ!Box + FRITZ!Repeater(s) form a single
**FRITZ! Mesh**: one SSID, automatic band/AP steering, and **one management surface**
(the FRITZ!Box / FRITZ!OS). Why Teleprofi favours this:

- **Simpler management:** one admin UI, one mesh, one firmware lineage (FRITZ!OS) —
  not a mix of vendors and controllers.
- **Simpler support:** for both Teleprofi and the customer — coverage, roaming and
  updates behave consistently; troubleshooting is one ecosystem, not an integration.
- **Consistent with the router standard:** the router is already a FRITZ!Box
  ([`fritzbox-family.md`](./fritzbox-family.md)); the repeater keeps the edge coherent.
- **Firmware** is governed by the shared [[firmware-policy]] across the whole AVM
  estate.

This is an ecosystem-coherence argument, not a claim that mesh beats wired everywhere
(see below).

# Typical Bundle

The Repeater 6000 is a **coverage add-on within a FRITZ!Box solution** — referenced,
not duplicated:

| Part | Reference |
|---|---|
| **Router** | the matching FRITZ!Box ([`fritzbox-family.md`](./fritzbox-family.md)) |
| **Coverage survey** | `../services/wifi-site-survey.md` (placement / quantity) |
| **Additional repeaters / cabling** | more 6000s for mesh, or structured cabling for wired backhaul (`teleprofi_fulda.md`: Ethernet/fibre cabling) |
| **Installation + validation** | `../services/telephone-system-installation.md`; performance verification (`teleprofi_fulda.md`) |
| **Maintenance contract** | `../services/maintenance-contract.md` |

Composed coverage work → `../solutions/wifi-coverage-improvement.md`. Pricing → `pricing/`.

# Strengths

- **Tri-band Wi-Fi 6**, up to ~6 Gbit/s, **12 antennas** — strong coverage/throughput
  per unit (AVM).
- **2.5G + 1G LAN** — supports **wired backhaul** (more stable than wireless backhaul)
  or wired clients (AVM).
- **FRITZ! Mesh** — seamless single-ecosystem management with the FRITZ!Box (AVM).
- Keeps the customer in **one AVM ecosystem** (management/support simplicity).

# Limitations

- **Wi-Fi 6**, not Wi-Fi 7.
- A repeater **extends** an existing network — it does not fix a weak/incorrect core
  network design; coverage still depends on **placement** (hence a survey).
- For **large/dense/multi-floor** sites, **structured cabling + access points** can
  outperform wireless mesh — a repeater is not always the right tool (see below).
- Wireless backhaul shares airtime; **wired backhaul** is preferable where cabling
  exists.

# When Teleprofi recommends the Repeater 6000

Extending a FRITZ!Box network to **fill coverage gaps** where mesh is adequate and the
customer benefits from staying in the AVM ecosystem — ideally after a quick survey.

# When another solution would be more appropriate

- **Large / dense / multi-floor coverage** → **structured cabling + access points**
  may be better than wireless mesh (Teleprofi does Ethernet/fibre cabling, switches,
  PoE, VLAN — `teleprofi_fulda.md`). The repeater suits gap-filling, not whole-site
  enterprise Wi-Fi.
- **Wired backhaul available everywhere** → cabling to APs can beat wireless repeating.
- (Teleprofi's actual threshold for "repeater vs. cabling + APs" — Knowledge Needed Q3.)

# Common customer questions

- "Wi-Fi doesn't reach the back office/upper floor — can you fix it?" → yes, typically
  a Repeater 6000 (after confirming placement with a survey).
- "Will it work with my FRITZ!Box?" → yes — it joins the FRITZ! Mesh.
- "One network name everywhere?" → yes, FRITZ! Mesh presents a single Wi-Fi.
- "Do I need cabling instead?" → for big/complex sites possibly; a survey decides.

# Typical support issues

Wireless support: **coverage/roaming** gaps, repeater **placement/backhaul** quality,
mesh join/steering behaviour, firmware (`teleprofi_fulda.md`: coverage/roaming/
registration issues). Often resolved by **re-placement** or **wired backhaul**.
(Most common Repeater 6000 support call — Knowledge Needed Q4.)

# Installation expectations

Part of Teleprofi's Wi-Fi process: **coverage planning → placement → mesh join →
coverage testing → performance verification** (`teleprofi_fulda.md`;
`services/wifi-site-survey.md`), validated per [[installation-philosophy]]. Use
**wired backhaul** where cabling allows. (Teleprofi repeater placement/validation
checklist — Patrick backlog.)

# Maintenance expectations

FRITZ!OS firmware per [[firmware-policy]] (proven-stable; updates as a billed service
per [[maintenance-philosophy]]) — kept in lockstep with the FRITZ!Box across the mesh.
Low-touch otherwise; coverage may need re-checking if the customer changes the space.

# Firmware / update policy

Shared [[firmware-policy]] — only proven-stable FRITZ!OS, evaluated first; updates as a
billed service, kept consistent across the AVM mesh. Not restated here.

# AI Recommendation Signals

**Lean Repeater 6000** on a **Wi-Fi coverage-gap** signal ("dead spot", "doesn't
reach", "weak upstairs/back") **where a FRITZ!Box is/will be present** and mesh is
adequate. **Lean wired cabling + APs** on **large/dense/multi-floor** signals or where
wired backhaul is everywhere. Always **scope with a survey** before promising a fix —
coverage depends on placement, not just the device.

# AI Conversation Example

Customer: *"Our Wi-Fi is fine near the router but drops out in the back office and the
upstairs storeroom."*
→ A **coverage-gap** signal on an AVM network → recommend a **FRITZ!Repeater 6000** to
extend the FRITZ! Mesh into those areas, **after a quick coverage survey** to confirm
placement (one unit vs. more, wireless vs. wired backhaul)
(`services/wifi-site-survey.md`). Staying on AVM keeps it one network, one admin, one
support path (Mesh philosophy). If the building were large/multi-floor, propose
**structured cabling + access points** instead.

# Cross-Selling Opportunities

- **Router:** the matching FRITZ!Box ([`fritzbox-family.md`](./fritzbox-family.md)).
- **Wi-Fi site survey:** `../services/wifi-site-survey.md` (scope placement/quantity).
- **Additional repeaters** (mesh) or **structured cabling** for wired backhaul/APs
  (`teleprofi_fulda.md`: cabling, switches).
- **Installation + performance verification:** `../services/telephone-system-installation.md`.
- **Maintenance contract:** `../services/maintenance-contract.md`.
- **Coverage solution:** `../solutions/wifi-coverage-improvement.md`.
- **PBX / provider** where it's part of a wider telephony+network project
  (`comtrexx-family.md`; [[provider-preference-philosophy]]).

# Related products

- [`fritzbox-family.md`](./fritzbox-family.md) — the router it extends (selection model).
- [`fritzbox-5690-pro.md`](./fritzbox-5690-pro.md) / [`fritzbox-5590-fiber.md`](./fritzbox-5590-fiber.md)
  / [`fritzbox-7590-ax.md`](./fritzbox-7590-ax.md) — the specific routers.
- `comtrexx-family.md` — the PBX, where the project also includes telephony.

# Related (reusable knowledge)

- Philosophy: [[installation-philosophy]], [[firmware-policy]], [[maintenance-philosophy]],
  [[product-selection-philosophy]].
- Services / solutions: `../services/wifi-site-survey.md`,
  `../solutions/wifi-coverage-improvement.md`, `../services/maintenance-contract.md`.

# Teleprofi Knowledge Needed

**Renato (commercial / selection):**
1. Typical **repeater count per site**, and when one Repeater 6000 isn't enough.
3. Teleprofi's **threshold** for recommending **repeater(s) vs. structured cabling +
   access points** (site size, density, floors).
5. Is the Repeater 6000 usually sold **with a survey**, or added reactively to fix
   complaints?

**Patrick (technician / hands-on):**
2. Default **backhaul** choice (wireless vs. wired) and when you insist on wired.
4. Most common **Repeater 6000 support call** (placement, roaming, backhaul, firmware).
6. Teleprofi's **placement / coverage-validation / performance-verification** checklist.

# Knowledge History

| Version | Date | Change | Source |
|---|---|---|---|
| 0.1 | 2026-06-25 | First networking entry (sets the networking standard): Wi-Fi coverage extension + AVM-ecosystem/mesh philosophy, repeater-vs-cabling boundary, AI signals + conversation example + cross-selling; router logic referenced not duplicated | repo Teleprofi Wi-Fi knowledge + official AVM + fritzbox-family |

# Knowledge Confidence

| Area | Confidence | Reason |
|---|---|---|
| Wi-Fi 6 tri-band / LAN / mesh specs | high | official AVM |
| AVM-ecosystem / mesh management rationale | high | official mesh + Teleprofi single-vendor logic |
| Coverage-extension positioning | high | Teleprofi Wi-Fi service knowledge (`teleprofi_fulda.md`) |
| Repeater-vs-cabling threshold | needs-confirmation | not captured — Q3 |
| Typical counts / backhaul default / survey-attach | needs-confirmation | Q1/Q2/Q5 |
| Support issues / placement checklist | needs-confirmation | Q4 + Patrick backlog |
| FRITZ!OS firmware scope in firmware-policy | needs-confirmation | open in [[firmware-policy]] |
