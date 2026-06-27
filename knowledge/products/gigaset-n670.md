---
id: gigaset-n670
type: product
owner: unassigned
status: draft
knowledge_version: 0.1   # alternative DECT base; value is the WS-500S↔N670 recommendation boundary (largely an open interview target)
last_reviewed: 2026-06-25
sources:
  - backend/voice/knowledge/teleprofi_fulda.md            # primary: Teleprofi business knowledge (lists N670 IP PRO as supported)
  - Teleprofi operational knowledge (Renato, 2026-06-25)   # primary
  - knowledge/products/ws-500s.md                          # the Auerswald-native alternative (DECT design method not duplicated)
  - https://www.gigaset.com/pro/hq_en/gigaset-n670-ip-pro/ # supporting: official Gigaset
category: dect
vendor: Gigaset
model: Gigaset N670 IP PRO
lifecycle: current
---

# Gigaset N670 IP PRO — Teleprofi product knowledge

> The **alternative DECT base** to the Auerswald [`ws-500s.md`](./ws-500s.md). The
> point of this entry is **not** to explain the N670 — it is to teach the
> **recommendation boundary between WS-500S and N670**. The general DECT design method
> (survey → size → single/multi-cell) lives in `ws-500s.md` → DECT Infrastructure
> Philosophy and is **referenced, not duplicated**. Reusable principles live in
> `business-philosophy/`.
>
> **Knowledge maturity: v0.1 (draft).** The core boundary (why/when Teleprofi picks
> Gigaset over Auerswald) is largely **operational knowledge not yet captured** — it
> is the headline interview question, not invented here.

# Executive Summary

**What is it?** A **single-cell IP-DECT base** (base + manager combined) — **up to 20
handsets, 8 simultaneous calls** (Gigaset), i.e. the **same raw capacity** as the
WS-500S. It is **standards-based SIP** (works with on-prem or cloud IP telephony, can
hold up to 20 VoIP PBX/provider profiles, uses the Gigaset Professional handset range)
and is **multicell-upgradeable** (mini-multicell of up to 3 N670s without extra
licence; larger/multi-location via the N870 integrator).

**Who is it for?** Cordless sites where the **Gigaset ecosystem** is the better fit
rather than Auerswald-native WS-500 — see "Why Teleprofi chooses Gigaset."

**Why does Teleprofi sell it?** It's the **current alternative DECT base** Teleprofi
supports (`teleprofi_fulda.md` lists *Gigaset N670 IP PRO*). The decision vs. WS-500S
is an **ecosystem** decision, not a capacity one.

# Teleprofi Recommendation

For a COMtrexx/COMfortel cordless system, Teleprofi's **default DECT base is the
Auerswald WS-500S** (ecosystem coherence — see `ws-500s.md`). The **N670 is the
exception**, chosen when specific factors favour the Gigaset ecosystem (below). Because
raw capacity is the same (20 handsets / 8 calls), **the choice is rarely about
numbers** — it's about ecosystem, handsets, and scale model. The actual Teleprofi
trigger for choosing N670 is the key open question (Q1).

# Typical Customer

Cordless sites where Gigaset fits better than Auerswald-native — e.g. **existing
Gigaset handset fleets**, **non-Auerswald/standards-based SIP** environments, or
**multi-location** DECT centrally managed via N870. (Teleprofi's real N670 customer
profile — Knowledge Needed Q1/Q2.)

# Typical Deployment

Same DECT design process as any base — **survey → placement → registration →
coverage test → onboarding** (`ws-500s.md`, DECT Infrastructure Philosophy;
`services/dect-site-survey.md`). **N670 deltas:** single-cell by default;
**mini-multicell** by combining up to 3 N670s (no extra licence); larger multicell /
multi-site via **N870** central management (Gigaset).

# Typical Bundle

DECT infrastructure within a cordless solution — referenced, not duplicated:

| Part | Reference |
|---|---|
| **Handsets** | **Gigaset Professional** range (the N670's native handsets) — **not** the COMfortel M-730/M-710 (those are the WS-500 handsets; whether COMfortel M-series register to the N670 is open — Q4) |
| **PBX** | the SIP PBX — COMtrexx (`comtrexx-family.md`) or a third-party SIP/cloud platform (the N670's standards-based nature suits non-Auerswald PBXs) |
| **Survey / installation / maintenance** | `../services/dect-site-survey.md`, `../services/telephone-system-installation.md`, `../services/maintenance-contract.md` |

Pricing → `pricing/`.

# Why Teleprofi chooses Gigaset

> **Default is Auerswald WS-500** within a COMtrexx/COMfortel system (ecosystem
> coherence). The N670 is chosen for specific reasons. The **objective** factors that
> can favour the N670 are:

- **Standards-based / vendor-neutral SIP:** works with any SIP PBX or cloud telephony
  and holds up to **20 VoIP profiles** (Gigaset) — a fit where the environment is
  **not** pure Auerswald/COMtrexx, or must serve multiple PBXs/providers.
- **Existing Gigaset handsets:** the customer already runs the Gigaset Professional
  range and wants to keep them.
- **Multi-location / larger multicell:** central management of bases across sites via
  the **N870** integrator (Gigaset).

> **What is NOT yet captured (do not assume):** Teleprofi's *actual* operational
> driver for choosing N670 over WS-500S — price, availability, specific handset
> features, customer request, or technical preference. This is the document's core
> open question (Q1). Until answered, the agent should **default to WS-500S in the
> Auerswald ecosystem** and treat N670 as the deliberate exception.

# Strengths

- **Same single-cell capacity** as WS-500S (20 handsets / 8 calls) — no trade-off
  there (Gigaset).
- **Vendor-neutral SIP** flexibility (up to 20 VoIP profiles; any SIP PBX/cloud).
- **Mini-multicell** of up to 3 bases without extra licence; **N870** multi-site
  scaling (Gigaset).

# Limitations

- **Outside the Auerswald ecosystem** — loses the native WS-500↔COMtrexx/COMfortel
  integration coherence that is Teleprofi's default (`ws-500s.md`).
- Uses **Gigaset handsets**, not COMfortel — mixing handset ecosystems on one estate
  adds management surface; COMfortel-M-on-N670 compatibility is unconfirmed (Q4).
- Same single-cell coverage/placement dependency as any DECT base (survey-driven).

# Coverage

Single-cell coverage like the WS-500S — one base, one cell; survey decides reach
(`ws-500s.md`, Coverage). N670 delta: **mini-multicell (up to 3 bases)** extends the
covered area while keeping 20 handsets / 8 calls (Gigaset).

# Roaming

Single base = no inter-base handover; **roaming requires multicell** (mini-multicell
of up to 3 N670s, or N870-managed multicell) (Gigaset). Same design principle as
`ws-500s.md`, Roaming — the ecosystem differs, not the concept.

# Capacity

**20 handsets / 8 simultaneous calls** single-cell (Gigaset) — **identical to
WS-500S**. Larger capacity needs multicell/N870. Capacity is therefore **not** a
WS-500S-vs-N670 differentiator (this is the key point for the agent).

# When Teleprofi recommends the N670

When the **Gigaset ecosystem** is the better fit — existing Gigaset handsets,
non-Auerswald/standards-based SIP environment, or multi-location central management
(N870). *(Confirm Teleprofi's real triggers — Q1.)*

# When WS-500S is the better choice

The **default** for a COMtrexx/COMfortel system — Auerswald-native integration,
COMfortel M-730/M-710 handsets, single ecosystem to manage and support
(`ws-500s.md`). Choose WS-500S unless a specific Gigaset factor applies.

# Common customer questions

- "We already have Gigaset cordless phones — can we keep them?" → yes, the N670 is the
  Gigaset base.
- "Is it as capable as the Auerswald base?" → same capacity (20/8); the difference is
  ecosystem, not numbers.
- "We have several sites — can it be managed centrally?" → yes, via N870 multicell.
- "Will it work with our (non-Auerswald) phone system?" → yes, it's standards-based SIP.

# Typical support issues

Same DECT-infrastructure profile as the WS-500S — coverage, placement, registration,
capacity at peak, firmware (`ws-500s.md`, Typical support issues). **N670 delta:**
support spans the **Gigaset** management/firmware world rather than Auerswald's. (Most
common N670 support call — Knowledge Needed Q5.)

# Installation expectations

Same DECT process as the WS-500S (`ws-500s.md`, Installation; `services/dect-site-survey.md`;
`services/telephone-system-installation.md`), per [[installation-philosophy]] — but in
the **Gigaset** provisioning/management toolset. (Teleprofi N670 placement/registration
checklist — Patrick backlog.)

# Maintenance expectations

Firmware per [[firmware-policy]] (proven-stable; updates as a billed service per
[[maintenance-philosophy]]) — but on the **Gigaset** firmware track, separate from the
Auerswald estate (a reason ecosystem-coherence usually favours WS-500S). (Gigaset
firmware specifics — confirm.)

# Firmware / update policy

Shared [[firmware-policy]] principle (only proven-stable, evaluated first; updates as a
billed service) applied to the **Gigaset** firmware line. Not restated here.

# AI Recommendation Signals

**Default to WS-500S** for a COMtrexx/COMfortel cordless system. **Lean N670** only on
a specific **Gigaset-ecosystem** signal: *"we already have Gigaset handsets"*,
*"non-Auerswald / standards-based SIP / multiple PBX profiles"*, or *"multi-site
centrally managed DECT (N870)"*. **Capacity is not a signal** (both are 20/8). When in
doubt, recommend the Auerswald-native WS-500S and flag the N670 question for Teleprofi.

# AI Conversation Example

Customer: *"We already use Gigaset cordless handsets across the company and want to
keep them when we modernise the phone system."*
→ A clear **Gigaset-ecosystem** signal → the **Gigaset N670** base lets them retain
their Gigaset handsets, while the new PBX can still be COMtrexx (the N670 is
standards-based SIP). Confirm coverage with a survey (`services/dect-site-survey.md`).
*(Without an existing-Gigaset / non-Auerswald / multi-site reason, the default would be
the Auerswald WS-500S for ecosystem coherence.)*

# Cross-Selling Opportunities

- **Gigaset Professional handsets** (the N670's native handsets).
- **PBX:** COMtrexx (`comtrexx-family.md`) or third-party SIP/cloud.
- **DECT site survey:** `../services/dect-site-survey.md`.
- **Multicell expansion:** additional N670s (mini-multicell) or **N870** for multi-site.
- **Installation + maintenance:** `../services/telephone-system-installation.md`,
  `../services/maintenance-contract.md`.

# Related products

- [`ws-500s.md`](./ws-500s.md) — the **Auerswald-native default** DECT base (the boundary partner).
- [`comfortel-m730.md`](./comfortel-m730.md) / [`comfortel-m710.md`](./comfortel-m710.md)
  — Auerswald handsets (WS-500 ecosystem; N670 uses Gigaset handsets — Q4).
- `comtrexx-family.md` — the PBX behind the DECT system.

# Related (reusable knowledge)

- Philosophy: [[product-selection-philosophy]], [[installation-philosophy]],
  [[firmware-policy]], [[maintenance-philosophy]].
- AI rules: `../ai-rules/provider-selection.md` (wider solution).
- Services: `../services/dect-site-survey.md`, `../services/telephone-system-installation.md`.

# Teleprofi Knowledge Needed

**Renato (commercial / selection) — the core of this document:**
1. **What actually makes Teleprofi choose the N670 over the WS-500S?** (existing
   Gigaset handsets? non-Auerswald PBX? multi-site/N870? price? customer request?)
2. How **often** is the N670 chosen vs. WS-500S — is it a rare exception or a regular
   alternative?
3. Does Teleprofi prefer to **keep a customer on one ecosystem** (never mix
   Auerswald + Gigaset on one estate), or is mixing acceptable?

**Patrick (technician / hands-on):**
4. Can **COMfortel M-730/M-710 handsets register to the N670**, or only Gigaset
   handsets? (Defines whether the base choice forces the handset choice.)
5. Most common **N670 support call**, and any Gigaset-specific provisioning/firmware
   gotchas vs. the WS-500.

# Knowledge History

| Version | Date | Change | Source |
|---|---|---|---|
| 0.1 | 2026-06-25 | Alternative DECT base entry focused on the WS-500S↔N670 boundary: same-capacity / ecosystem-difference framing, objective Gigaset-favouring factors, default-to-WS-500S; Teleprofi's real N670 driver captured as the headline interview question (not invented); DECT design method referenced not duplicated | repo Teleprofi knowledge + official Gigaset + ws-500s |

# Knowledge Confidence

| Area | Confidence | Reason |
|---|---|---|
| N670 capacity = WS-500S (20/8); multicell/N870 model | high | official Gigaset |
| Standards-based SIP / vendor-neutral nature | high | official Gigaset |
| Objective Gigaset-favouring factors (boundary) | medium | inferred from objective differences, not Teleprofi practice |
| **Teleprofi's actual N670-vs-WS-500S driver** | needs-confirmation | not captured — Q1 (the document's core gap) |
| COMfortel-M-on-N670 compatibility | needs-confirmation | Q4 |
| N670 support / Gigaset firmware specifics | needs-confirmation | Q5 |
