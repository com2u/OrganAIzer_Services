---
id: wlan-selection
type: ai-rule
owner: unassigned
status: active
last_reviewed: 2026-07-23
sources:
  - "Teleprofi candidate interview-answer document (confirmed by Renato, 2026-07-23)"
---

# WLAN Topology Selection — decision rules

> This file defines **how** OrganAIzer chooses between a single access
> point, a mesh system, a wired access-point deployment, and a paid WLAN
> survey. It is decision policy, not product facts — device facts live in
> [`../products/fritz-repeater-6000.md`](../products/fritz-repeater-6000.md)
> and [`fritzbox-family.md`](../products/fritzbox-family.md). Mirrors the
> `provider-selection.md`/`endpoint-selection.md` pattern.
>
> **This file is the single canonical home for the single-AP vs. mesh vs.
> wired-AP vs. WLAN-survey decision (reconciliation decision, 2026-07-22).**
> `fritz-repeater-6000.md` previously carried an overlapping, independently
> unresolved version of this same question (its own Knowledge Needed Q3) —
> that file now links here instead of restating the decision logic. Any
> product-specific characterization (e.g. what the Repeater 6000 itself is
> good for) still lives in that product file; the cross-product "how do we
> choose" logic lives only here.
>
> Confirmed by Renato, 2026-07-23. Not wired into any AI prompt. This file
> changes no application behavior.

## Selection guidance

> From the interview draft's Interview 3 "ROUTER UND WLAN" section.

- **Ein einzelner Access Point reicht**, wenn: die Fläche klein und
  überschaubar ist, die bauliche Struktur günstig ist, die Nutzerzahl
  gering ist, und die Leistungsanforderungen moderat sind.
- **Mesh** ist sinnvoll, wenn: mehrere Bereiche versorgt werden müssen, die
  Verkabelung teilweise eingeschränkt ist, und eine einfache zentrale
  Funkversorgung wichtiger ist als maximale Planbarkeit.
- **Kabelgebundene Access Points (wired AP)** sind vorzuziehen, wenn:
  gewerbliche, zeitkritische Umgebungen professionelle Planbarkeit
  benötigen; die Fläche groß, dicht oder mehrgeschossig ist; oder
  Verkabelung ohnehin überall verfügbar ist. Mesh sollte in solchen Fällen
  **nicht automatisch** die erste Lösung sein — this is directionally
  consistent with the pre-existing (already `high`-confidence)
  characterization in
  [`../products/fritz-repeater-6000.md`](../products/fritz-repeater-6000.md)
  ("Limitations" / gap-filling vs. whole-site coverage), which this file's
  guidance now supersedes as the canonical decision logic (see note above).
- **Eine WLAN-Ausleuchtung** wird durchgeführt, wenn: die Fläche groß oder
  verwinkelt ist; Stahl, Beton, Glas oder Regalsysteme den Funk
  beeinflussen; DECT/WLAN-Telefonie oder Echtzeitanwendungen genutzt
  werden; viele Nutzer gleichzeitig arbeiten; zuverlässiges Roaming
  erforderlich ist; bestehende WLAN-Probleme nicht eindeutig lokalisierbar
  sind; ein Ausfall geschäftskritisch wäre. Delivered as the paid service
  [`../services/wifi-site-survey.md`](../services/wifi-site-survey.md).

## Guardrails

- This file states selection guidance only; it does not restate device
  specs or survey-service pricing.
- No prices, firmware versions, or capacity numbers are stated or implied
  here.
- Do not present the mesh caution above as a blanket "never recommend
  mesh" rule — the source draft frames it as "not automatically the first
  choice" for time-critical commercial environments, not a prohibition.

## Related

- [`../products/fritz-repeater-6000.md`](../products/fritz-repeater-6000.md)
  — device facts and product-specific characterization; its former Q3
  ("repeater vs. cabling + APs threshold") is now tracked here instead of
  independently in that file.
- [`../products/fritzbox-family.md`](../products/fritzbox-family.md)
- [`../services/wifi-site-survey.md`](../services/wifi-site-survey.md)
- [`../procedures/site-visit-checklist.md`](../procedures/site-visit-checklist.md)

## Notes

This file carries the single AP-vs-mesh-vs-wired-AP-vs-survey threshold
question for the whole repository (absorbing `fritz-repeater-6000.md`'s
former Q3) — the answer lives here only; do not re-open it in the product
file.
