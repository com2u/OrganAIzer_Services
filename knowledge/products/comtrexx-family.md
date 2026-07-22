---
id: comtrexx-family
type: product
owner: unassigned
status: draft
knowledge_version: 0.1   # family-level decision knowledge; → 1.0 as the interview questions are answered
last_reviewed: 2026-06-25
sources:
  - backend/voice/knowledge/teleprofi_fulda.md          # primary: Teleprofi business knowledge
  - Teleprofi operational knowledge (Renato, 2026-06-25) # primary
  - knowledge/products/comtrexx-next.md
  - knowledge/infrastructure/comtrexx.md
category: telephony
vendor: Auerswald
model: COMtrexx (family overview)
lifecycle: current
---

# Auerswald COMtrexx — Teleprofi family knowledge

> **Family-level reasoning, not a product spec sheet.** This entry explains how
> Teleprofi *thinks about* the COMtrexx family as a whole — when to choose COMtrexx
> at all, and how to choose between models. It does **not** replace the per-product
> entries (`comtrexx-next.md`, future `comtrexx-flex.md`), which hold the specs and
> product-specific knowledge. Family-level logic lives **here once**, and the
> product files reference it.
>
> **Knowledge maturity: v0.1.** Gaps are precise questions under
> **[Teleprofi Knowledge Needed](#teleprofi-knowledge-needed)**.

## When do we choose COMtrexx at all?

Auerswald COMtrexx is **Teleprofi's standard business PBX platform** — Auerswald is
the telephony manufacturer Teleprofi supports and installs (`teleprofi_fulda.md`,
Supported Manufacturers). The family fits Teleprofi's reliability-first,
easy-to-maintain, long-term-stable approach ([[installation-philosophy]]), and
covers the full small-to-mid business range with one consistent feature set and one
admin experience.

> The explicit "COMtrexx vs. a non-Auerswald alternative" reasoning (what would make
> Teleprofi *not* propose COMtrexx) is not yet captured — see Knowledge Needed Q1.

> **CANDIDATE ADDITION — Teleprofi interview draft, unconfirmed.**
> **Requires Patrick/Renato confirmation before merge. This is a candidate
> answer to Knowledge Needed Q1 below — the question is not removed until
> Patrick/Renato confirm this answer.**
>
> ### Candidate answer to Q1 — when Teleprofi would not propose COMtrexx
>
> Candidate criteria: eine einfache FRITZ!Box-Lösung erfüllt den Bedarf
> vollständig und sauber; der Kunde bevorzugt eine vollständig cloudbasierte
> Plattform; die vorhandene IT-Strategie basiert auf einem anderen
> Ökosystem; nur einzelne Endgeräte müssen ersetzt werden (see
> [`../ai-rules/endpoint-selection.md`](../ai-rules/endpoint-selection.md));
> keine ausreichende Netzwerk- oder Internetqualität ist vorhanden; die
> laufenden Lizenz- und Wartungsmodelle passen nicht zum Kunden; der Kunde
> benötigt Funktionen, die ein anderes System besser abdeckt.
>
> Source: Teleprofi candidate interview-answer document (unconfirmed,
> 2026-07-22), Interview 3 "TELEFONANLAGEN".

## How do we choose Next vs. Flex?

The decision is driven by **future business needs, not just today's headcount**
([[product-selection-philosophy]], [[growth-planning-philosophy]]):

- **COMtrexx Next** — the entry-level choice for genuinely small offices (Teleprofi
  sweet spot ~1–5 users), where a lower entry price than Flex is the main driver and
  no growth/complexity signals are present. Details: `comtrexx-next.md`.
- **COMtrexx Flex** — the scalable, longer-life platform chosen when growth or
  complexity signals appear (see below). Details: future `comtrexx-flex.md`.

Exact capacities live in the product files (and Auerswald docs) — not duplicated
here.

## Signals that mean "do NOT choose Next"

Teleprofi moves to Flex (does not choose Next) when one or more applies (Teleprofi
operational knowledge):

- ~7–8 active users or more.
- Expected company growth.
- More departments.
- More internal call groups.
- More advanced call routing.
- Additional software integration.
- Multiple product lines.
- More analog devices (Next has no analog ports — see `comtrexx-next.md`).
- More advanced door communication / future door expansion.
- Increased general expansion requirements.

## Signals that mean "Flex is worth the higher price"

Flex justifies its higher investment when the customer benefits from
(Teleprofi operational knowledge):

- Greater expandability / headroom for growth.
- A better long-term investment (avoid replacing the PBX after a few years).
- More advanced telephony features.
- More flexible hardware expansion (e.g. analog modules).
- Suitability for larger installations.
- An expectation of growth.

Some functions are also possible on Next, but Flex usually delivers them in a more
scalable and maintainable way (Teleprofi operational knowledge).

**Financing can make Flex attainable.** Where budget is the only reason a customer
leans Next, **leasing (Grenke) may make Flex affordable** and avoid replacing the
PBX in a few years — but technical fit is decided first; financing only supports it
([[financing-philosophy]]).

## AI Conversation Examples

Worked examples of the Next-vs-Flex decision in a customer conversation (the
canonical pair; the product entries each carry their own side):

- **Growth → Flex.** Customer: *"We currently have five employees but expect to
  double within two years."* Five today would fit Next, but doubling to ~10 users
  crosses the ~7–8 evaluation point within the system's lifetime. Size to **future**
  needs ([[growth-planning-philosophy]]) → recommend **COMtrexx Flex despite the
  higher initial investment**: it avoids replacing the PBX in ~2 years and scales via
  floating licences/modules. If the upfront cost is the obstacle, **leasing (Grenke)
  turns it into manageable monthly payments** ([[financing-philosophy]]) — technical
  fit decided first, financing supports it.
- **Small & static → Next.** Customer: *"I only need two desk phones."* A two-phone
  small office sits squarely in Next's 1–5 sweet spot with light telephony and no
  growth / analog / door signals → **COMtrexx Next is sufficient** and right-sized at
  the lowest entry cost ([[product-selection-philosophy]]). (Still confirm there are
  no growth/analog/door signals before finalizing.)

## Knowledge shared by all COMtrexx systems

Applies family-wide; product files reference it rather than restating it:

- **Feature set / platform:** the COMtrexx soft-PBX feature set and admin
  experience are common across the family (Auerswald; see product files for
  per-model capacity).
- **Endpoints:** native Auerswald **COMfortel** phones (D-series desk) and Auerswald
  **DECT** (WS-500S/M bases + COMfortel M-handsets); standards-based SIP phones also
  supported (`teleprofi_fulda.md`; product files).
- **Licensing model:** floating user licensing (the per-model stacking behaviour and
  block sizes differ — see product files).

## Family rules (provider / router / firmware / maintenance)

These reusable rules apply across the whole COMtrexx family — captured once in
`business-philosophy/`, referenced here and from product files:

- **Provider & router:** [[provider-preference-philosophy]] (prefer Telekom for new
  business installs; never pressure a switch; router follows access technology —
  DSL→fiber-friendly FRITZ!Box 5690 Pro). For business installs, **register the SIP
  trunk directly in the COMtrexx PBX** so the PBX owns telephony; the router does
  connectivity/firewall/termination. Provider decision logic:
  `ai-rules/provider-selection.md`. Per-provider encryption specifics:
  `providers/telekom.md`, `providers/vodafone.md`, `providers/o2.md`.
- **Firmware:** [[firmware-policy]] — only proven-stable firmware; the COMtrexx
  firmware status table (e.g. 2.4.6 stable; 2.6.1/2.6.2 not recommended) lives there
  and is shared by all COMtrexx products.
- **Maintenance:** [[maintenance-philosophy]] — firmware/maintenance offered as a
  billed professional service.
- **Installation:** [[installation-philosophy]] — preconfigured, bench-tested,
  plug-and-play delivery.

## Related

- **Products:** `comtrexx-next.md`; future `comtrexx-flex.md`.
- **Providers:** `../providers/telekom.md`, `vodafone.md`, `o2.md`.
- **Services:** `../services/telephone-system-installation.md`,
  `telephone-system-migration.md`, `maintenance-contract.md`, `remote-support.md`.
- **Business philosophy:** `../business-philosophy/product-selection-philosophy.md`,
  `growth-planning-philosophy.md`, `installation-philosophy.md`, `firmware-policy.md`,
  `maintenance-philosophy.md`, `provider-preference-philosophy.md`,
  `financing-philosophy.md`.
- **AI rules:** `../ai-rules/provider-selection.md`; a future product-selection rule
  (Next vs. Flex) should reference *this* family entry.
- **Infrastructure:** `../infrastructure/comtrexx.md` (integration boundary).

## Teleprofi Knowledge Needed

> High-level, reusable interview questions (answers update this family entry and/or
> `business-philosophy/`, benefiting all COMtrexx products).

1. When would Teleprofi **not** propose COMtrexx at all — are there cases you choose
   a different platform, and why?
2. Is there a **user-count band where Next vs. Flex is genuinely a judgement call**
   (e.g. 5–8 users), and what tips it either way?
3. Are there **features or integrations** customers ask for that *only* Flex can do
   (a hard "must be Flex" list)?
4. Across the family, which **COMfortel phone / DECT** combinations do you fit most
   often, and any you avoid?
5. Confirm whether the firmware versions in [[firmware-policy]] are **COMtrexx system
   firmware or COMfortel device firmware** (or both, tracked separately).

## Knowledge History

| Version | Date | Change | Source |
|---|---|---|---|
| 0.1 | 2026-06-25 | Initial family entry; Next-vs-Flex logic centralized here | Teleprofi operational knowledge + repo |
| 0.1 | 2026-06-25 | Added AI conversation examples (canonical Next-vs-Flex pair) | Teleprofi (Renato) |

## Knowledge Confidence

| Area | Confidence | Reason |
|---|---|---|
| Next vs. Flex signals / upgrade triggers | high | captured from Teleprofi (2026-06-25) |
| "Flex worth the price" reasoning | high | captured from Teleprofi (2026-06-25) |
| When to choose COMtrexx at all (vs. alternatives) | needs-confirmation | not yet captured — Q1 |
| Shared endpoints / licensing model | medium | repo + official; per-model detail in product files |
| Firmware version scope (system vs. device) | needs-confirmation | Q5 |
