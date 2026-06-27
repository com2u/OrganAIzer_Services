---
id: fritzbox-7590-ax
type: product
owner: unassigned
status: draft
knowledge_version: 0.1   # DSL-only sibling of the 5690 Pro / 5590 Fiber; documents only what is unique
last_reviewed: 2026-06-25
sources:
  - backend/voice/knowledge/teleprofi_fulda.md             # primary: Teleprofi business knowledge
  - Teleprofi operational knowledge (Renato, 2026-06-25)    # primary
  - knowledge/business-philosophy/provider-preference-philosophy.md  # router-by-access-tech rule (not duplicated)
  - knowledge/products/fritzbox-5690-pro.md                 # sibling (shared router knowledge)
  - https://en.avm.de/products/fritzbox/fritzbox-7590-ax/technical-specifications/   # supporting: official AVM
category: router
vendor: AVM
model: FRITZ!Box 7590 AX
lifecycle: current
---

# AVM FRITZ!Box 7590 AX — Teleprofi product knowledge

> The **DSL-only sibling** of the FRITZ!Box 5690 Pro (fibre+DSL) and 5590 Fiber
> (fibre-only). Shared router knowledge (role in front of the PBX, trunk-in-PBX,
> install/maintenance pattern) lives in [`fritzbox-5690-pro.md`](./fritzbox-5690-pro.md);
> router/provider *decision logic* lives in [[provider-preference-philosophy]] and
> `ai-rules/provider-selection.md` — both **referenced, not repeated**. This entry
> documents only what is **unique to the 7590 AX**.
>
> **Knowledge maturity: v0.1 (draft).** Teleprofi-specific gaps are precise questions
> under **[Teleprofi Knowledge Needed](#teleprofi-knowledge-needed)**.

# Executive Summary

**What is it?** AVM's established **DSL** flagship — a **VDSL (Supervectoring 35b, up
to ~300 Mbit/s) / ADSL2+** modem router with **Wi-Fi 6**, 4× Gigabit LAN, a Gigabit
WAN port, an integrated **DECT base** and **2 analog a/b ports** for analog phones/
fax/answering machine (AVM). It has **no fibre (SFP/GPON) interface**.

**Who is it for?** Business customers on **DSL/VDSL with no fibre migration planned**
— the proven, right-sized, lower-cost DSL router.

**Why does Teleprofi sell it?** It's the **DSL workhorse**: a mature, reliable
FRITZ!OS router that covers DSL sites without paying for fibre capability they don't
need ([[product-selection-philosophy]]). It sits upstream of the COMtrexx PBX; the
SIP trunk is registered **in the PBX** ([[provider-preference-philosophy]]).

# Teleprofi Recommendation

Recommend the **7590 AX for DSL/VDSL customers with no planned fibre migration** — it
remains an excellent recommendation for them. Router choice follows **access
technology** ([[provider-preference-philosophy]]); the 7590 AX is the **DSL-only**
option. If fibre is **expected soon**, prefer the **5690 Pro** (avoids replacing the
router); if fibre is **already available**, prefer the **5590 Fiber** (see below).

# Typical Customer

Established DSL/VDSL business sites — common where fibre is not yet available in the
area (`teleprofi_fulda.md`: DSL + provider coordination). (Teleprofi's actual share
of DSL-only sites / how often the 7590 AX is the answer — Knowledge Needed Q1.)

# Typical Deployment

The site **router / internet access** in front of the COMtrexx PBX, terminating the
**DSL/VDSL** line, providing firewall, routing, Wi-Fi and LAN; the PBX owns telephony
and the SIP trunk ([[provider-preference-philosophy]]). Same edge role as the 5690 Pro
— see [`fritzbox-5690-pro.md`](./fritzbox-5690-pro.md). **Note:** although the 7590 AX
has its own DECT base and analog ports, in a Teleprofi business install **telephony is
owned by the COMtrexx PBX** — the FRITZ!Box telephony features are generally not the
business-telephony path (the router should not replace PBX functions —
[[provider-preference-philosophy]]). Whether Teleprofi ever uses the 7590 AX's analog
ports for an odd device is a question (Knowledge Needed Q4).

# Typical Bundle

Same router role/bundle structure as the 5690 Pro (PBX + provider + Wi-Fi mesh +
survey/installation/maintenance) — see [`fritzbox-5690-pro.md`](./fritzbox-5690-pro.md),
Typical Bundle. **7590 AX delta:** it's the bundle's router where the access is **DSL**
and no fibre move is planned. Pricing → `pricing/`.

# Strengths

- **Mature, proven DSL/VDSL** router (Supervectoring 35b / ADSL2+) — reliable, widely
  deployed (AVM; Teleprofi-standard platform, `teleprofi_fulda.md`).
- **Wi-Fi 6**, 4× Gigabit LAN, Gigabit WAN, 2× USB 3.0 (AVM).
- Built-in **DECT base + 2 analog a/b ports** (AVM) — available if ever needed,
  though business telephony stays on the PBX.
- Lower cost than the 5690 Pro where fibre capability isn't needed.

# Limitations

- **No fibre interface** — if the site moves to fibre, the 7590 AX must be
  **replaced** (that future is exactly why the 5690 Pro exists). Not for
  fibre-now or fibre-soon sites.
- **Wi-Fi 6**, not Wi-Fi 7.
- DECT base / analog ports are consumer-oriented; **Auerswald COMfortel handsets use
  WS-500 bases**, and business telephony is owned by the COMtrexx PBX (Q4).

# When Teleprofi recommends the 7590 AX

**DSL/VDSL, no planned fibre migration.** The proven, cost-effective choice.

# When Teleprofi recommends the 5690 Pro instead

**Fibre expected soon / uncertain timing**, or the customer wants one router across a
DSL→fibre migration — the 5690 Pro does both, avoiding a later router swap
([`fritzbox-5690-pro.md`](./fritzbox-5690-pro.md); [[provider-preference-philosophy]]).

# When Teleprofi recommends the 5590 Fiber instead

**Fibre already available** and no DSL needed — the fibre-native 5590 is simpler/
cheaper ([`fritzbox-5590-fiber.md`](./fritzbox-5590-fiber.md)).

> Full model comparison and decision table:
> [`fritzbox-family.md`](./fritzbox-family.md).

## Migration Scenarios

> Router/provider decision logic referenced from [[provider-preference-philosophy]]
> and `ai-rules/provider-selection.md` — not duplicated.

- **DSL now, no fibre planned → 7590 AX.** The straightforward DSL case.
- **DSL now, fibre soon → NOT the 7590 AX.** It has no fibre modem, so a fibre move
  means replacing it. Teleprofi generally prefers the **5690 Pro** here (runs DSL now,
  fibre later, no swap).
- **Fibre already live → 5590 Fiber** (or 5690 Pro if DSL fallback/Wi-Fi 7 wanted).
- **Behind an external modem.** The 7590 AX's Gigabit WAN port can run **behind a
  separate cable/fibre modem** as a plain router, but that is not Teleprofi's typical
  fibre recommendation (a fibre-native FRITZ!Box is preferred) — confirm if/when
  Teleprofi does this (Knowledge Needed Q5).
- **Telekom recommendation.** Where the preferred-provider rule applies (new business
  → Telekom; [[provider-preference-philosophy]], `ai-rules/provider-selection.md`),
  the 7590 AX pairs with Telekom **DSL/VDSL**.

# Common customer questions

- "We're on DSL with no fibre here — which router?" → 7590 AX.
- "Fibre is coming next year — should we still buy the 7590 AX?" → no; the 5690 Pro
  avoids replacing the router at migration.
- "We already have fibre — is the 7590 AX right?" → no; that's the 5590 Fiber (or 5690 Pro).
- "Can we plug analog phones / our fax into it?" → technically yes (2 a/b ports), but
  business telephony runs through the COMtrexx PBX.

# Typical support issues

Same router-class profile as the 5690 Pro — DSL line sync/activation at provisioning,
Wi-Fi coverage, port-forwarding/firewall, firmware (`fritzbox-5690-pro.md`, Typical
support issues; `teleprofi_fulda.md` internet-access issues). (Most common 7590 AX
support call — Knowledge Needed Q2.)

# Installation expectations

Edge install: terminate the **DSL/VDSL** line, configure WAN/Wi-Fi/firewall; ensure
the **SIP trunk is provisioned in the COMtrexx PBX**, not the router
([[provider-preference-philosophy]]); validate per [[installation-philosophy]].
(Teleprofi router preconfig/bench checklist — Patrick backlog, shared across the
FRITZ!Box routers.)

# Maintenance expectations

FRITZ!OS firmware per [[firmware-policy]] (proven-stable; updates as a billed service
per [[maintenance-philosophy]]). Mature, long-lived platform; the main "maintenance"
event in its life is the eventual **fibre migration**, at which point it is replaced
(by a 5690 Pro / 5590 Fiber).

# Firmware / update policy

Shared [[firmware-policy]] — only proven-stable FRITZ!OS, evaluated first; updates as
a billed service. Not restated here. *(FRITZ!OS-vs-Auerswald firmware scope is the
open question already tracked in [[firmware-policy]].)*

# AI Recommendation Signals

**Lean 7590 AX** on a **DSL/VDSL, no-fibre-planned** signal. **Lean 5690 Pro** on a
**migration/uncertainty** signal (fibre soon / unknown). **Lean 5590 Fiber** on a
**fibre-already-here** signal. Decisive signal = **access technology + migration
outlook**, not price; don't put a fibre-bound customer on a 7590 AX to save money now
and force a swap later ([[product-selection-philosophy]]).

# AI Conversation Example

Customer: *"We're on VDSL and there's no fibre in our area, no plans for it."*
→ A **DSL-only, no-migration** signal → recommend the **FRITZ!Box 7590 AX**: the
proven VDSL router, right-sized and cheaper than paying for the 5690 Pro's fibre
capability they won't use ([[product-selection-philosophy]]). Provider follows
[[provider-preference-philosophy]]. *(If fibre were "coming soon", the answer would
flip to the 5690 Pro to avoid a later router swap.)*

# Cross-Selling Opportunities

- **PBX:** COMtrexx (`comtrexx-family.md`) if telephony is in scope.
- **Provider:** DSL line + SIP trunk per [[provider-preference-philosophy]] / `ai-rules/provider-selection.md`.
- **Wi-Fi mesh:** **FRITZ!Repeater 6000** (`fritz-repeater-6000.md` to come).
- **Wi-Fi site survey:** `../services/wifi-site-survey.md`.
- **Installation + maintenance contract:** `../services/telephone-system-installation.md`,
  `../services/maintenance-contract.md`.
- **Future fibre move:** `../services/fiber-installation.md` / `../solutions/fiber-migration.md`
  (at which point the router becomes a 5690 Pro / 5590 Fiber).
- **DECT base** (if cordless needed): Auerswald **WS-500S/M** (`products/` to come).

# Related products

- [`fritzbox-family.md`](./fritzbox-family.md) — **canonical router selection model**
  (decision table, access-tech matrix, migration strategy across all three routers).
- [`fritzbox-5690-pro.md`](./fritzbox-5690-pro.md) — fibre+DSL migration sibling (Wi-Fi 7).
- [`fritzbox-5590-fiber.md`](./fritzbox-5590-fiber.md) — fibre-only sibling (Wi-Fi 6).
- `fritz-repeater-6000.md` — Wi-Fi mesh extension (to come).
- `comtrexx-family.md` — the PBX the router sits in front of.

# Related (reusable knowledge)

- Philosophy: [[provider-preference-philosophy]], [[product-selection-philosophy]],
  [[installation-philosophy]], [[firmware-policy]], [[maintenance-philosophy]].
- AI rules: `../ai-rules/provider-selection.md`.
- Providers / services / solutions: `../providers/telekom.md`,
  `../services/wifi-site-survey.md`, `../solutions/fiber-migration.md`.

# Teleprofi Knowledge Needed

**Renato (commercial / selection):**
1. What share of Teleprofi sites are DSL-only, and how often is the 7590 AX the answer
   vs. proactively steering to the 5690 Pro for future-proofing?
2. Do you ever recommend the 5690 Pro to a no-fibre-planned DSL customer anyway (just
   in case), or hold to the 7590 AX until fibre is real?

**Patrick (technician / hands-on):**
3. Most common 7590 AX support call (DSL sync, Wi-Fi, port-forwarding)?
4. Do you ever use the 7590 AX's **analog a/b ports or DECT base** in a business
   install, or is everything always on the COMtrexx PBX?
5. Do you ever run the 7590 AX **behind an external fibre/cable modem** via its WAN
   port, and when?

# Knowledge History

| Version | Date | Change | Source |
|---|---|---|---|
| 0.1 | 2026-06-25 | DSL-only sibling completing the router trio: DSL-workhorse positioning, when-5690/when-5590, Migration Scenarios, AI signals + conversation example + cross-selling; router/provider logic referenced not duplicated | Teleprofi philosophy + repo + official AVM |

# Knowledge Confidence

| Area | Confidence | Reason |
|---|---|---|
| DSL/VDSL / Wi-Fi 6 / DECT + analog ports / no-fibre specs | high | official AVM |
| Positioning vs. 5690 Pro / 5590 Fiber | high | reuses [[provider-preference-philosophy]] + official product lines |
| "DSL-only, no migration → 7590 AX" rule | high | Teleprofi knowledge (Renato) + no-fibre fact |
| Teleprofi DSL-site share / proactive-future-proofing habit | needs-confirmation | not captured — Q1/Q2 |
| Use of FRITZ analog/DECT or WAN-behind-modem in practice | needs-confirmation | Q4/Q5 |
| FRITZ!OS firmware scope in firmware-policy | needs-confirmation | open in [[firmware-policy]] |
