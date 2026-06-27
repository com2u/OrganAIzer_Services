---
id: comfortel-m710
type: product
owner: unassigned
status: draft
knowledge_version: 0.1   # sibling of M-730; documents only what is unique. Teleprofi gaps are interview questions
last_reviewed: 2026-06-25
sources:
  - backend/voice/knowledge/teleprofi_fulda.md           # primary: Teleprofi business knowledge
  - Teleprofi operational knowledge (Renato, 2026-06-25)  # primary
  - https://www.auerswald.de/de/produkt/comfortel-m-710   # supporting: official
  - knowledge/products/comfortel-m730.md                  # sibling (shared DECT-handset knowledge)
category: dect
vendor: Auerswald
model: COMfortel M-710
lifecycle: current
---

# Auerswald COMfortel M-710 — Teleprofi product knowledge

> The **office/entry-level sibling** of the COMfortel M-730. Shared DECT-handset
> knowledge (deployment, bundle, support, installation, maintenance, firmware) lives
> in [`comfortel-m730.md`](./comfortel-m730.md) and is **referenced, not repeated**;
> this entry documents only what is **unique to the M-710**. Reusable reasoning lives
> in `business-philosophy/`.
>
> **Knowledge maturity: v0.1 (draft).** Built from repository Teleprofi knowledge,
> official Auerswald data, and existing philosophy. Teleprofi-specific gaps are
> precise questions under **[Teleprofi Knowledge Needed](#teleprofi-knowledge-needed)**.

# Executive Summary

**What is it?** The COMfortel M-710 is Auerswald's **entry-level office DECT
handset** — "das ideale Einsteigermodell in der IP-DECT-Welt" (Auerswald) — for
normal indoor/office use. It registers to Auerswald DECT bases (WS-500S/M) behind a
COMtrexx PBX, exactly like the M-730.

**Who is it for?** Offices and indoor workplaces that need cordless mobility at a
**favourable price**, **especially installations with many handsets** (Auerswald).
It is the volume/cost-effective handset; the M-730 is the rugged one.

**Why does Teleprofi sell it?** It's the **current** entry DECT handset
(`teleprofi_fulda.md`) and the cost-effective default where ruggedness isn't needed.

# Teleprofi Recommendation

Recommend the **M-710** for **ordinary office/indoor** DECT, and particularly for
**larger, cost-sensitive handset fleets** where per-handset price matters (Auerswald).
Choose the **M-730 instead** when the environment is harsh or hygiene-critical (see
below and `comfortel-m730.md`). The decision is **environment-driven**, per the
M-730 entry — the M-710 is the "no special environment" choice
([[product-selection-philosophy]]: right-sized, not cheapest-by-reflex but
cost-effective where it fits).

# Typical Customer

Standard offices and indoor workplaces — the broad middle of Teleprofi's customer
base (`teleprofi_fulda.md`) — needing cordless handsets without rugged/IP65
requirements. Often **multiple handsets per site**, where the M-710's pricing is
attractive. (Real M-710 vs. M-730 split — Knowledge Needed Q1, shared with the M-730.)

# Typical Deployment

**Same DECT deployment as the M-730** (site survey → coverage testing → base
placement → registration → onboarding; `comfortel-m730.md`, Typical Deployment;
`services/dect-site-survey.md`). The M-710 is simply the office handset within that
process — frequently in **higher quantities** per site.

# Typical Bundle

Same bundle structure as the M-730 (PBX + DECT base + provider/router + licensing +
optional headset + services) — see [`comfortel-m730.md`](./comfortel-m730.md),
Typical Bundle. **M-710 delta:** it is the handset of choice when the bundle includes
**many handsets** on a budget. Each handset consumes a floating user licence on
COMtrexx (`comtrexx-family.md`). Pricing → `pricing/`.

# Strengths

- **Entry-level price**, attractive for **many-handset** installations (Auerswald).
- Office-friendly; Bluetooth, Micro-USB, 3.5 mm jack (Auerswald).
- Native Auerswald DECT integration (WS-500S/M + COMtrexx), same ecosystem as M-730.

# Limitations

- **Not the rugged option** — it lacks the M-730's highlighted IP65/disinfectant
  ruggedness; not for workshop/warehouse/outdoor/wet/hygiene-critical use (use M-730).
- DECT coverage dependency and battery-as-consumable apply as for any handset
  (`comfortel-m730.md`, Limitations).
- Exact M-710 display/battery/IP figures are **not stated** on the official page —
  see Open/Confirmation items.

# When Teleprofi recommends the M-710

Normal **office/indoor** use; and especially **cost-sensitive fleets with many
handsets**, where the lower per-handset price compounds.

# When Teleprofi recommends the M-730 instead

Harsh or hygiene-critical environments — dust, moisture, outdoors, drop-risk,
disinfectant wiping. The M-730 is purpose-built for these (IP65, disinfectant-
resistant); see [`comfortel-m730.md`](./comfortel-m730.md).

# Common customer questions

- "What's the difference vs. the M-730?" → the M-710 is the cost-effective office
  handset; the M-730 is rugged (IP65) for tough/hygiene environments.
- "We need a lot of handsets cheaply — which one?" → M-710 (priced for volume).
- "Can it cope with our warehouse/outdoors?" → no — that's the M-730.
- "Does it work with our Auerswald system?" → yes, via WS-500S/M bases + COMtrexx.

# Typical support issues

Same DECT-handset support profile as the M-730 — registration/pairing,
coverage/roaming, battery wear, firmware (`comfortel-m730.md`, Typical support
issues). (Most common M-710 support call not yet captured — Knowledge Needed Q4.)

# Installation expectations

Same DECT install process as the M-730 ([[installation-philosophy]];
`services/dect-site-survey.md`). **M-710 delta:** larger fleets mean more handsets
to register/onboard, so onboarding effort scales with quantity. (Teleprofi DECT
checklist — Patrick backlog, shared with the M-730.)

# Maintenance expectations

Same as the M-730: firmware via [[firmware-policy]] (proven-stable; billed service
per [[maintenance-philosophy]]); batteries are consumables — across a **large fleet**
this is a more significant lifecycle cost to plan for.

# Firmware / update policy

Governed by the shared [[firmware-policy]] — only proven-stable firmware, evaluated
first, updates as a billed service. Not restated here.

# AI Recommendation Signals

**Lean M-710** when signals are **office/indoor** and/or **cost-sensitive at volume**
(many handsets). **Lean M-730** on any **rugged/hygiene** signal (dust, moisture,
outdoors, disinfectant). Decisive signal = **environment**, with **quantity/price**
as the tie-breaker toward M-710 for plain offices. Don't push the pricier M-730
where the environment doesn't require it ([[product-selection-philosophy]]).

# AI Conversation Example

Customer: *"We're fitting out the office with cordless phones for about 15 staff and
want to keep the per-handset cost down."*
→ Indoor office use, **many handsets, cost-sensitive** → recommend the **COMfortel
M-710**: the entry-level office DECT handset, priced attractively for multi-handset
installations (Auerswald). No rugged/IP65 need here, so the M-730 would be over-spec
([[product-selection-philosophy]]). Confirm DECT coverage for the office floorplan
(`services/dect-site-survey.md`).

# Cross-Selling Opportunities

Natural follow-ons an experienced Teleprofi consultant would attach (referenced, not
described here):

- **DECT base(s):** Auerswald **WS-500S/M** — required for coverage (`products/` to come).
- **PBX:** COMtrexx (`comtrexx-family.md`) if not already in place.
- **Provider + router:** per [[provider-preference-philosophy]] (`providers/`).
- **Headset:** Bluetooth / 3.5 mm headset (Jabra line, `teleprofi_fulda.md`).
- **DECT site survey:** `../services/dect-site-survey.md` — especially for larger fleets.
- **Installation:** `../services/telephone-system-installation.md`.
- **Maintenance contract:** `../services/maintenance-contract.md` (fleet firmware/batteries).
- **Training / onboarding:** user onboarding for larger handset rollouts
  (`teleprofi_fulda.md`, DECT onboarding).

# Related products

- [`comfortel-m730.md`](./comfortel-m730.md) — the rugged sibling (IP65, harsh/hygiene).
- Auerswald **WS-500S/M** DECT bases (required; `products/` entry to come).
- `comtrexx-family.md` / `comtrexx-next.md` / `comtrexx-flex.md` — the PBX.

# Related (reusable knowledge)

- Philosophy: [[product-selection-philosophy]], [[installation-philosophy]],
  [[firmware-policy]], [[maintenance-philosophy]], [[provider-preference-philosophy]],
  [[financing-philosophy]].
- Services: `../services/dect-site-survey.md`,
  `../services/telephone-system-installation.md`, `../services/maintenance-contract.md`.

# Teleprofi Knowledge Needed

> Mostly **shared with the M-730** (answer once, update both). Interview questions:

**Renato (commercial / selection):**
1. The real **M-710 vs. M-730 split** — at what point does the office case still take
   the M-730 (and vice versa)? *(shared with M-730 Q1/Q2)*
2. Typical **handset quantities** where the M-710's volume pricing drives the choice.
3. Do larger M-710 fleets routinely get a **site survey + training** attached?

**Patrick (technician / hands-on):**
4. Most common **M-710 support call** (registration, coverage, battery)?
5. Any **bulk registration/onboarding** tooling or shortcuts for large M-710 fleets.

# Knowledge History

| Version | Date | Change | Source |
|---|---|---|---|
| 0.1 | 2026-06-25 | Sibling entry to the M-730: office/entry-level + many-handset positioning; shared DECT knowledge referenced not duplicated; AI signals + conversation example + cross-selling | repo Teleprofi knowledge + official Auerswald + M-730 entry |

# Knowledge Confidence

| Area | Confidence | Reason |
|---|---|---|
| Positioning (office/entry, volume pricing) | high | official Auerswald M-710 page |
| Connectivity (BT / USB / jack) | high | official Auerswald |
| M-710 vs. M-730 decision (environment-driven) | high | official positioning of both |
| Real Teleprofi office-vs-rugged split / quantities | needs-confirmation | not captured — Q1/Q2 |
| Support issues / install detail | needs-confirmation | shared with M-730 (Q4 / Patrick) |
| Display / battery / IP rating figures | needs-confirmation | not stated on official M-710 page |
