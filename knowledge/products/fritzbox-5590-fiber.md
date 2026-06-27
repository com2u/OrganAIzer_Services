---
id: fritzbox-5590-fiber
type: product
owner: unassigned
status: draft
knowledge_version: 0.1   # fiber-only sibling of the 5690 Pro; documents only what is unique
last_reviewed: 2026-06-25
sources:
  - backend/voice/knowledge/teleprofi_fulda.md             # primary: Teleprofi business knowledge
  - Teleprofi operational knowledge (Renato, 2026-06-25)    # primary
  - knowledge/business-philosophy/provider-preference-philosophy.md  # router-by-access-tech rule (not duplicated)
  - knowledge/products/fritzbox-5690-pro.md                 # sibling (shared router knowledge)
  - https://en.fritz.com/products/fritzbox/fritzbox-5590-fiber/technical-specifications/   # supporting: official AVM
category: router
vendor: AVM
model: FRITZ!Box 5590 Fiber
lifecycle: current
---

# AVM FRITZ!Box 5590 Fiber — Teleprofi product knowledge

> The **fiber-first sibling** of the FRITZ!Box 5690 Pro. Shared router knowledge
> (the router's role in front of the PBX, trunk-in-PBX, install/maintenance pattern)
> lives in [`fritzbox-5690-pro.md`](./fritzbox-5690-pro.md) and reusable router/
> provider *decision logic* lives in [[provider-preference-philosophy]] and
> `ai-rules/provider-selection.md` — both **referenced, not repeated**. This entry
> documents only what is **unique to the 5590 Fiber**.
>
> **Knowledge maturity: v0.1 (draft).** Teleprofi-specific gaps are precise questions
> under **[Teleprofi Knowledge Needed](#teleprofi-knowledge-needed)**.

# Executive Summary

**What is it?** AVM's **fiber-only** FRITZ!Box — a pure **fibre-optic modem router**
(AON / GPON / XGS-PON via included FRITZ!SFP modules) with **Wi-Fi 6**, a 2.5 Gbit/s
WAN port and 4× Gigabit LAN (AVM). It has **no DSL modem**.

**Who is it for?** Business customers who **already have a fibre connection** (or are
being connected to fibre now) and want a fibre-native router — without paying for DSL
capability they will never use.

**Why does Teleprofi sell it?** It's the **right-sized fibre router** when fibre is
already the access technology — simpler and cheaper than the dual-WAN 5690 Pro
([[product-selection-philosophy]]: fit, not over-spec). It sits upstream of the
COMtrexx PBX; the SIP trunk is registered **in the PBX** ([[provider-preference-philosophy]]).

# Teleprofi Recommendation

Recommend the **5590 Fiber when fibre is already available** at the site. Router
choice follows **access technology** — canonical rule in
[[provider-preference-philosophy]]; the 5590 is the **fibre-native** option. It is
**not** the DSL→fibre migration router (it cannot run DSL) — for a customer on DSL
with fibre planned soon, Teleprofi generally prefers the **5690 Pro** to avoid
replacing the router later (see When… instead).

# Typical Customer

Businesses **on fibre now** (newly connected or already fibre-served) running a
COMtrexx telephony install (`teleprofi_fulda.md`: fibre + provider coordination).
(Teleprofi's actual fibre-router customer profile / how often 5590 vs 5690 —
Knowledge Needed Q1.)

# Typical Deployment

The site **router / internet access** in front of the COMtrexx PBX, terminating the
**fibre** line (integrated ONT via SFP), providing firewall, routing, Wi-Fi and LAN;
the PBX owns telephony and the SIP trunk ([[provider-preference-philosophy]]). Often
paired with a FRITZ!Repeater for Wi-Fi coverage. Same edge role as the 5690 Pro —
see [`fritzbox-5690-pro.md`](./fritzbox-5690-pro.md), Typical Deployment.

# Typical Bundle

Same router role/bundle structure as the 5690 Pro (PBX + provider + Wi-Fi mesh +
survey/installation/maintenance) — see [`fritzbox-5690-pro.md`](./fritzbox-5690-pro.md),
Typical Bundle. **5590 delta:** it's the bundle's router **only where fibre is the
access** and no DSL fallback is wanted. Pricing → `pricing/`; composed deployments →
`solutions/` (e.g. `fiber-migration.md` once the customer is on fibre).

# Strengths

- **Fibre-native:** integrated ONT supporting **AON / GPON / XGS-PON** via included
  SFP modules — can often replace a separate ISP ONT (AVM).
- **Wi-Fi 6**, 2.5 Gbit/s WAN, 4× Gigabit LAN, 2× USB 3.0 (AVM).
- Simpler / lower-cost than the dual-WAN 5690 Pro where DSL is not needed.
- Teleprofi-standard FRITZ!OS platform (`teleprofi_fulda.md`).

# Limitations

- **No DSL** — cannot serve a customer who is still on DSL; **not a migration
  router** (a later DSL→fibre journey would have meant a router that already does
  both, i.e. the 5690 Pro).
- **Wi-Fi 6**, not Wi-Fi 7 (the 5690 Pro is Wi-Fi 7) — relevant only where Wi-Fi 7 /
  higher wireless throughput is actually required.
- Integrated **DECT base** is consumer-oriented; **Auerswald COMfortel handsets use
  WS-500 bases**, not the FRITZ!Box DECT base (confirm — Knowledge Needed Q3).
- Direct fibre termination (replacing the ISP ONT) is **provider/fibre-type
  dependent** (see Migration Scenarios).

# When Teleprofi recommends the 5590 Fiber

Fibre is **already present** (or being installed now), the customer is fibre-native,
and there is **no need for DSL**. The simpler, cheaper fibre router.

# When Teleprofi recommends the 5690 Pro instead

The customer is **on DSL today but fibre is planned soon**, fibre timing is
**uncertain**, or they want **one router across the migration** — the 5690 Pro does
**both** fibre and DSL, avoiding a router swap later ([`fritzbox-5690-pro.md`](./fritzbox-5690-pro.md);
[[provider-preference-philosophy]]).

# When the 7590 AX is sufficient

The customer is **DSL-only with no fibre migration expected** — the DSL-only
[7590 AX](./fritzbox-7590-ax.md) covers it at lower cost.

> Full model comparison and decision table:
> [`fritzbox-family.md`](./fritzbox-family.md).

## Migration Scenarios

> Router/provider decision logic referenced from [[provider-preference-philosophy]]
> and `ai-rules/provider-selection.md` — not duplicated.

- **Fibre already available → 5590 Fiber.** The straightforward fibre-native case.
- **DSL today, fibre later → NOT the 5590.** Because the 5590 has no DSL, deploying
  it now would mean running… nothing until fibre, or a router swap at migration.
  Teleprofi generally prefers the **5690 Pro** here (runs DSL now, fibre later, no
  swap).
- **Fibre standards.** AON / GPON / XGS-PON via included SFP modules (AVM) — confirm
  the provider's fibre type is supported before promising direct termination.
- **ISP ONT transition.** The 5590's integrated ONT can often **replace a separate
  ISP ONT/media converter**, but this is **provider/fibre-type dependent** — confirm
  per provider (Knowledge Needed Q4); do not assume.
- **Telekom recommendation.** Where the preferred-provider rule applies (new business
  → Telekom; [[provider-preference-philosophy]], `ai-rules/provider-selection.md`),
  the 5590 pairs with Telekom **fibre**. Exact Telekom-fibre provisioning steps —
  confirm (Patrick backlog).

# Common customer questions

- "We just got fibre — which router?" → 5590 Fiber (fibre-native).
- "We're on DSL but fibre is coming — should we get the 5590 now?" → no; the 5690 Pro
  avoids replacing the router at migration.
- "Can it replace the provider's fibre box (ONT)?" → often yes, provider-dependent.
- "Is Wi-Fi 6 enough?" → usually yes; choose the 5690 Pro (Wi-Fi 7) only if higher
  wireless throughput is genuinely needed.

# Typical support issues

Same router-class profile as the 5690 Pro — fibre line activation/sync at
provisioning, Wi-Fi coverage, port-forwarding/firewall, firmware
(`fritzbox-5690-pro.md`, Typical support issues; `teleprofi_fulda.md` internet-access
issues). (Most common 5590 support call — Knowledge Needed Q2.)

# Installation expectations

Edge install: terminate the **fibre** line (SFP/ONT), configure WAN/Wi-Fi/firewall;
ensure the **SIP trunk is provisioned in the COMtrexx PBX**, not the router
([[provider-preference-philosophy]]); validate per [[installation-philosophy]]. Fibre
activation may involve the provider's ONT/line data (see Migration Scenarios).
(Teleprofi router preconfig/bench checklist — Patrick backlog, shared with the 5690 Pro.)

# Maintenance expectations

FRITZ!OS firmware per [[firmware-policy]] (proven-stable; updates as a billed service
per [[maintenance-philosophy]]). Long-lived edge device; being fibre-only, it has no
DSL fallback if fibre is ever interrupted — a planning note for fibre-only sites.

# Firmware / update policy

Shared [[firmware-policy]] — only proven-stable FRITZ!OS, evaluated first; updates as
a billed service. Not restated here. *(FRITZ!OS-vs-Auerswald firmware scope is the
open question already tracked in [[firmware-policy]].)*

# AI Recommendation Signals

**Lean 5590 Fiber** on a clean **fibre-already-here** signal with no DSL need. **Lean
5690 Pro** on any **migration/uncertainty** signal (DSL now, fibre later, unknown
timing) or a Wi-Fi 7 requirement. **Lean 7590 AX** on **DSL-only, no migration**.
Decisive signal = **access technology + migration outlook**, not price; don't choose
the 5590 for a customer who will shortly need DSL→fibre flexibility
([[product-selection-philosophy]]).

# AI Conversation Example

Customer: *"We've just had a fibre line installed and need a router for it — we don't
have DSL anymore."*
→ A **fibre-already-present, no-DSL** signal → recommend the **FRITZ!Box 5590 Fiber**:
fibre-native, simpler and cheaper than the dual-WAN 5690 Pro, and the customer has no
DSL to fall back on anyway ([[product-selection-philosophy]]). Provider follows
[[provider-preference-philosophy]]. *(If they were still on DSL with fibre "coming
soon", the answer would instead be the 5690 Pro to avoid a later router swap.)*

# Cross-Selling Opportunities

- **PBX:** COMtrexx (`comtrexx-family.md`) if telephony is in scope.
- **Provider:** fibre line + SIP trunk per [[provider-preference-philosophy]] / `ai-rules/provider-selection.md`.
- **Wi-Fi mesh:** **FRITZ!Repeater 6000** (`fritz-repeater-6000.md` to come).
- **Wi-Fi site survey:** `../services/wifi-site-survey.md`.
- **Fibre installation:** `../services/fiber-installation.md`; solution `../solutions/fiber-migration.md`.
- **Installation + maintenance contract:** `../services/telephone-system-installation.md`,
  `../services/maintenance-contract.md`.
- **DECT base** (if cordless needed): Auerswald **WS-500S/M** (`products/` to come).

# Related products

- [`fritzbox-family.md`](./fritzbox-family.md) — **canonical router selection model**
  (decision table, access-tech matrix, migration strategy across all three routers).
- [`fritzbox-5690-pro.md`](./fritzbox-5690-pro.md) — fibre+DSL migration sibling (Wi-Fi 7).
- [`fritzbox-7590-ax.md`](./fritzbox-7590-ax.md) — DSL-only sibling (Wi-Fi 6).
- `fritz-repeater-6000.md` — Wi-Fi mesh extension (to come).
- `comtrexx-family.md` — the PBX the router sits in front of.

# Related (reusable knowledge)

- Philosophy: [[provider-preference-philosophy]], [[product-selection-philosophy]],
  [[growth-planning-philosophy]], [[installation-philosophy]], [[firmware-policy]],
  [[maintenance-philosophy]].
- AI rules: `../ai-rules/provider-selection.md`.
- Providers / services / solutions: `../providers/telekom.md`,
  `../services/fiber-installation.md`, `../services/wifi-site-survey.md`,
  `../solutions/fiber-migration.md`.

# Teleprofi Knowledge Needed

**Renato (commercial / selection):**
1. How often do you deploy the 5590 vs. the 5690 Pro, and what decides it (price,
   "definitely no DSL ever", Wi-Fi needs)?
2. Do you ever fit the 5590 at sites where fibre is "imminent but not yet live", or
   only once fibre is active?

**Patrick (technician / hands-on):**
3. Do Auerswald COMfortel handsets ever use the FRITZ!Box DECT base, or always
   WS-500S/M? *(shared with the 5690 Pro)*
4. Which providers/fibre types let the 5590 terminate fibre directly (replace the ISP
   ONT), and which require keeping the ISP ONT?
5. Telekom (and other) fibre provisioning steps for the 5590.

# Knowledge History

| Version | Date | Change | Source |
|---|---|---|---|
| 0.1 | 2026-06-25 | Fiber-only sibling of the 5690 Pro: fibre-native positioning, "not a migration router", when-5690/when-7590, Migration Scenarios, AI signals + conversation example + cross-selling; router/provider logic referenced not duplicated | Teleprofi philosophy + repo + official AVM |

# Knowledge Confidence

| Area | Confidence | Reason |
|---|---|---|
| Fibre-only / AON-GPON-XGS / Wi-Fi 6 / ports specs | high | official AVM |
| Positioning vs. 5690 Pro (fibre-native vs. migration) | high | reuses [[provider-preference-philosophy]] + official capability |
| "Not the migration router" rule | high | Teleprofi knowledge (Renato) + the no-DSL fact |
| Teleprofi deployment frequency / 5590-vs-5690 split | needs-confirmation | not captured — Q1 |
| Direct fibre termination per provider | needs-confirmation | provider-specific — Q4 |
| COMfortel-vs-FRITZ DECT base | needs-confirmation | Q3 |
| FRITZ!OS firmware scope in firmware-policy | needs-confirmation | open in [[firmware-policy]] |
