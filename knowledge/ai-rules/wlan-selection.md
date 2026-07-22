---
id: wlan-selection
type: ai-rule
owner: unassigned
status: draft
last_reviewed: 2026-07-22
sources:
  - "Teleprofi candidate interview-answer document (unconfirmed, 2026-07-22)"
---

> **Status: Candidate draft from the Teleprofi interview-answer document.**
> **Requires Patrick/Renato confirmation before merge.**

# WLAN Topology Selection — decision rules

> This file defines **how** OrganAIzer chooses between a single access
> point, a mesh system, and a paid WLAN survey. It is decision policy, not
> product facts — device facts live in
> [`../products/fritz-repeater-6000.md`](../products/fritz-repeater-6000.md)
> and [`fritzbox-family.md`](../products/fritzbox-family.md). Mirrors the
> `provider-selection.md`/`endpoint-selection.md` pattern.
>
> Status: candidate decision policy from an unconfirmed interview draft, not
> wired into any AI prompt. This file changes no application behavior.

## Selection guidance

> Candidate content — from the interview draft's Interview 3 "ROUTER UND
> WLAN" section, not yet confirmed.

- **Ein einzelner Access Point reicht**, wenn: die Fläche klein und
  überschaubar ist, die bauliche Struktur günstig ist, die Nutzerzahl
  gering ist, und die Leistungsanforderungen moderat sind.
- **Mesh** ist sinnvoll, wenn: mehrere Bereiche versorgt werden müssen, die
  Verkabelung teilweise eingeschränkt ist, und eine einfache zentrale
  Funkversorgung wichtiger ist als maximale Planbarkeit.
  **Wichtige Einschränkung aus dem Entwurf:** für gewerbliche,
  zeitkritische Umgebungen sollte Mesh **nicht automatisch** die erste
  Lösung sein — kabelgebundene Access Points mit professioneller Planung
  sind häufig verlässlicher. This is directionally consistent with the
  existing (already `high`-confidence)
  [`../products/fritz-repeater-6000.md`](../products/fritz-repeater-6000.md)
  "Limitations" / "When another solution would be more appropriate"
  content — treat that file's existing guidance as the primary source and
  this note as corroborating, not overriding it.
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
  (already has an existing, higher-confidence open question — Q3 — on this
  exact AP-vs-mesh-vs-cabling threshold; this file's guidance should be
  reconciled with that open question, not treated as a separate answer)
- [`../products/fritzbox-family.md`](../products/fritzbox-family.md)
- [`../services/wifi-site-survey.md`](../services/wifi-site-survey.md)
- [`../procedures/site-visit-checklist.md`](../procedures/site-visit-checklist.md)

## Needs Human Confirmation

- Confirm this matches Teleprofi's actual practice — sourced from a single
  unconfirmed candidate interview draft.
- Reconcile with `fritz-repeater-6000.md`'s existing open Q3 rather than
  leaving two separate unresolved answers to the same question.
