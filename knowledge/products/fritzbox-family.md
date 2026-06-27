---
id: fritzbox-family
type: product
owner: unassigned
status: draft
knowledge_version: 0.1   # canonical router selection model; centralizes the decision, not the specs
last_reviewed: 2026-06-25
sources:
  - backend/voice/knowledge/teleprofi_fulda.md             # primary: Teleprofi business knowledge
  - Teleprofi operational knowledge (Renato, 2026-06-25)    # primary
  - knowledge/business-philosophy/provider-preference-philosophy.md  # router/provider principle (not duplicated)
  - knowledge/products/fritzbox-5690-pro.md
  - knowledge/products/fritzbox-5590-fiber.md
  - knowledge/products/fritzbox-7590-ax.md
category: router
vendor: AVM
model: FRITZ!Box (router family overview)
lifecycle: current
---

# AVM FRITZ!Box routers — Teleprofi family knowledge

> **Family-level router selection model, not a spec sheet.** This entry gives the
> Executive Agent **one canonical way to choose a FRITZ!Box** from the customer's
> access technology and migration outlook. It does **not** restate per-model specs —
> those live in the product entries. Router/provider *principle* (router follows
> access technology; trunk-in-PBX; Telekom preferred for new business) lives in
> [[provider-preference-philosophy]] and `ai-rules/provider-selection.md` and is
> **referenced, not repeated** — this entry holds the concrete decision.
>
> Scope: the three current FRITZ!Box routers. The **FRITZ!Repeater** (Wi-Fi mesh) is
> a different category and not covered here.
>
> **Knowledge maturity: v0.1 (draft).** Gaps are precise questions under
> **[Teleprofi Knowledge Needed](#teleprofi-knowledge-needed)**.

# Executive Summary

Teleprofi standardises on **AVM FRITZ!Box** routers as the internet-access edge in
front of the COMtrexx PBX (`teleprofi_fulda.md`). Three current models cover the
business range, and the **right one is decided by access technology + migration
outlook** — never by price alone. For full specs see each product entry:

| Model | WAN capability | Wi-Fi | One-line role |
|---|---|---|---|
| [5690 Pro](./fritzbox-5690-pro.md) | **Fibre + DSL** (dual) | Wi-Fi 7 | the migration-proof / future-proof router |
| [5590 Fiber](./fritzbox-5590-fiber.md) | **Fibre only** | Wi-Fi 6 | the fibre-native router |
| [7590 AX](./fritzbox-7590-ax.md) | **DSL only** | Wi-Fi 6 | the DSL workhorse |

(Decision-relevant axes only — port counts/throughput are in the product entries.)

# Teleprofi Router Philosophy

The principle is captured once in [[provider-preference-philosophy]]:

- **Router follows the customer's access technology** (DSL / fibre), and their
  **migration outlook** — not the lowest price.
- The **router provides connectivity / firewall / termination; the COMtrexx PBX owns
  telephony**, and the **SIP trunk is registered in the PBX**, not the router.
- **Provider choice** (Telekom preferred for new business installs) follows
  `ai-rules/provider-selection.md`.

This entry applies that principle to the three models. Where budget pressures the
choice, fit comes first ([[product-selection-philosophy]]); financing applies to the
wider solution ([[financing-philosophy]]).

# Router Selection Decision Table

| Customer situation (signal) | Recommend | Why |
|---|---|---|
| **Fibre already live**, no DSL needed | **5590 Fiber** | fibre-native, simpler/cheaper than dual-WAN |
| Fibre live, but wants **DSL fallback** or **Wi-Fi 7** | **5690 Pro** | dual WAN + Wi-Fi 7 |
| **DSL now, fibre expected soon / timing uncertain** | **5690 Pro** | runs DSL now, fibre later — **no router swap** at migration |
| **DSL now, no fibre planned** | **7590 AX** | proven DSL/VDSL, cost-effective |
| "Buy once / **future-proof** the edge" | **5690 Pro** | covers both technologies |

# Access Technology Decision Matrix

| Access today → outlook | Recommended | Fallback / note |
|---|---|---|
| **DSL** → no fibre planned | 7590 AX | replace later only if fibre eventually arrives |
| **DSL** → fibre soon / uncertain | 5690 Pro | avoids a second router at migration |
| **Fibre** → fibre only | 5590 Fiber | 5690 Pro if DSL fallback / Wi-Fi 7 wanted |
| **Fibre** → already on fibre, wants headroom | 5690 Pro | Wi-Fi 7, 2.5G, dual-WAN insurance |

Decisive signals: **access technology** + **migration outlook** (+ a Wi-Fi 7 / higher
throughput need as a secondary tie-breaker toward the 5690 Pro).

# Migration Strategy

> Provider/router principle referenced from [[provider-preference-philosophy]] and
> `ai-rules/provider-selection.md`; composed migration → `solutions/fiber-migration.md`.

## DSL → Fibre migration
The defining FRITZ!Box decision. If a DSL customer will move to fibre within the
system's life, choose the **5690 Pro now** so the move is a **re-cable to the fibre
SFP — no router replacement, no edge re-install** (`fritzbox-5690-pro.md`). Choosing a
single-WAN router (7590 AX) to save money today forces a swap later
([[product-selection-philosophy]]).

## Fibre already available
Choose the **5590 Fiber** (fibre-native, simpler/cheaper) — or the **5690 Pro** if the
customer wants a DSL fallback or Wi-Fi 7 (`fritzbox-5590-fiber.md`).

## Long-term planning
Size the router for the **investment's lifetime and the access roadmap**, consistent
with [[growth-planning-philosophy]]: ask about fibre availability and timeline before
recommending, exactly as the sales-qualification checklist captures.

## Future-proofing
The **5690 Pro** is the future-proof default where the access path is uncertain — one
router across DSL→fibre. Recommend it on uncertainty, not by default everywhere
(don't over-spec a settled DSL-only or fibre-only site).

## ISP ONT considerations
The fibre-capable models (5690 Pro, 5590 Fiber) have an **integrated ONT** (SFP) and
can often **replace a separate ISP ONT/media converter** — but this is
**provider/fibre-type dependent** (AON vs GPON vs XGS-PON, and provider policy).
Confirm per provider before promising direct termination (see the product entries'
Knowledge Needed).

## Fibre-ID overview
Activating a fibre line typically needs the **provider's fibre-line activation data**
(e.g. a Fiber-/Glasfaser-ID). The exact item and procedure are **provider-specific**
(esp. Telekom) and are tracked as interview items in the product entries — do not
assume a single process.

# Common customer questions

- "DSL now, fibre coming — what do we buy?" → 5690 Pro (one router for both).
- "We already have fibre." → 5590 Fiber (or 5690 Pro for DSL fallback / Wi-Fi 7).
- "DSL, no fibre here." → 7590 AX.
- "Will we have to replace the router when fibre arrives?" → not if you start on the
  5690 Pro.
- "Can the router handle our phones?" → telephony stays on the COMtrexx PBX; the
  router provides internet/firewall ([[provider-preference-philosophy]]).

# AI Recommendation Signals

Map the customer's words to the table above:
- **"fibre is here / we just got fibre"** → 5590 Fiber (5690 Pro if fallback/Wi-Fi 7).
- **"on DSL but fibre is coming / might come / not sure when"** → 5690 Pro.
- **"DSL, no fibre / no plans"** → 7590 AX.
- **"want to buy once / future-proof"** → 5690 Pro.
Never decide on price alone; if budget blocks the right migration path, evaluate
financing on the wider solution ([[financing-philosophy]]).

# AI Conversation Examples

- **DSL → fibre soon → 5690 Pro.** *"We're on DSL but fibre is being rolled out and
  we'll switch within a year."* → 5690 Pro: runs DSL now, fibre later, no router swap.
- **Fibre already live → 5590 Fiber.** *"We've just had fibre installed, no DSL
  anymore."* → 5590 Fiber: fibre-native, no need to pay for unused DSL capability.
- **DSL, no fibre → 7590 AX.** *"VDSL here, no fibre in our area, no plans."* →
  7590 AX: proven DSL router, right-sized and cheaper.

# Cross-Selling Opportunities

Common to all three (referenced, not described): **PBX** (`comtrexx-family.md`),
**provider line + SIP trunk** ([[provider-preference-philosophy]] /
`ai-rules/provider-selection.md`), **Wi-Fi mesh** (`fritz-repeater-6000.md`, to come),
**Wi-Fi site survey** (`../services/wifi-site-survey.md`), **fibre installation /
migration** (`../services/fiber-installation.md`, `../solutions/fiber-migration.md`),
**installation + maintenance contract** (`../services/telephone-system-installation.md`,
`../services/maintenance-contract.md`), and a **DECT base** (Auerswald WS-500S/M) where
cordless is needed.

# Related products

- [`fritzbox-5690-pro.md`](./fritzbox-5690-pro.md) — fibre+DSL, Wi-Fi 7 (migration-proof).
- [`fritzbox-5590-fiber.md`](./fritzbox-5590-fiber.md) — fibre-only, Wi-Fi 6.
- [`fritzbox-7590-ax.md`](./fritzbox-7590-ax.md) — DSL-only, Wi-Fi 6.
- `comtrexx-family.md` — the PBX the router sits in front of.

# Related (reusable knowledge)

- Philosophy: [[provider-preference-philosophy]], [[product-selection-philosophy]],
  [[growth-planning-philosophy]], [[financing-philosophy]].
- AI rules: `../ai-rules/provider-selection.md`.
- Providers / solutions: `../providers/telekom.md`, `../solutions/fiber-migration.md`.

# Teleprofi Knowledge Needed

> Reusable router-selection questions (answers update this table + the product
> entries).

1. In practice, how often do DSL customers with **no firm fibre date** get the
   5690 Pro for future-proofing vs. the 7590 AX? Where do you draw the line?
2. When fibre is **already live**, when do you still choose the 5690 Pro over the
   5590 Fiber (DSL fallback? Wi-Fi 7 demand? site type)?
3. Which **providers/fibre types** let the fibre models replace the ISP ONT, and the
   per-provider **fibre activation (Fiber-ID)** procedure (esp. Telekom)? *(Patrick)*
4. Any site types where you deviate from this table (e.g. very small sites, temporary
   connections)?

# Knowledge History

| Version | Date | Change | Source |
|---|---|---|---|
| 0.1 | 2026-06-25 | Created canonical router selection model: decision table + access-tech matrix + migration strategy; specs/principle referenced not duplicated; consolidates the selection triangle previously spread across the three product entries | Teleprofi philosophy + the three router entries + official AVM |

# Knowledge Confidence

| Area | Confidence | Reason |
|---|---|---|
| Router selection table / access-tech matrix | high | reuses [[provider-preference-philosophy]] + official model capabilities |
| Migration strategy (DSL→fibre, fibre-now, future-proof) | high | Teleprofi knowledge (Renato) + product capabilities |
| Model capability axes (WAN / Wi-Fi) | high | official AVM (full specs in product entries) |
| Where Teleprofi draws the future-proofing line | needs-confirmation | not captured — Q1/Q2 |
| ISP-ONT / Fiber-ID per-provider specifics | needs-confirmation | provider-specific — Q3 |
| Deviations for edge site types | needs-confirmation | Q4 |
