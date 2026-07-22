---
id: logistics-company
type: customer-scenario
owner: unassigned
status: draft
knowledge_version: 0.1
last_reviewed: 2026-07-22
sources:
  - "Teleprofi candidate interview-answer document (unconfirmed, 2026-07-22)"
industry: logistics-company
typical_company_size: any
---

> **Status: Candidate draft from the Teleprofi interview-answer document.**
> **Requires Patrick/Renato confirmation before merge.**

# Overview

> Logistikunternehmen (logistics companies) — a reusable archetype, not a
> real customer. Overlaps with `warehouse` (not yet created) — the draft's
> answer mentions both office and warehouse areas together; a human reviewer
> should decide whether these stay one archetype or split.

<A **reusable archetype**. Real accounts live in `customers/`; reusable
packages live in `solutions/`.>

# Typical company size

Not yet captured.

# Typical problems

> Candidate content — from the interview draft's "Branche" answers, not yet
> confirmed.

- Hohe Verfügbarkeit (high availability) is a named requirement.
- Mehrere Standorte (multiple sites) common.
- Lager- und Bürobereiche (warehouse and office areas together) — note the
  overlap with a possible future `warehouse` archetype.
- DECT oder robuste mobile Geräte (DECT or ruggedised mobile devices).
- Schichtbetrieb (shift operation).
- Schnelle Eskalation bei Ausfällen (fast escalation on outages).
- Häufig schwierige Funk- und Gebäudestrukturen (often difficult RF/building
  structures for wireless coverage) — relevant to
  `services/wifi-site-survey.md` / `services/dect-site-survey.md`.

# Typical infrastructure

Not yet captured.

# Recommended solutions

Not yet determined.

# Recommended products

Not yet determined.

# Recommended services

Candidate link (not yet confirmed): `services/wifi-site-survey.md` and
`services/dect-site-survey.md` may be relevant given the "schwierige Funk-
und Gebäudestrukturen" note above — needs confirmation before treating as a
standard recommendation for this archetype.

# Recommended providers

Not yet determined.

# Pricing references

None — no prices in this entry.

# Installation notes

Not yet captured.

# Sales notes

Not yet captured beyond the problem list above.

# Technician notes

Draft candidate note: difficult RF/building structures are called out
explicitly — worth flagging to a technician early that a site survey may be
warranted more often for this archetype than for a typical small office.

# Related solutions

None yet.

# Related products

None yet.

# Related services

`../services/wifi-site-survey.md`, `../services/dect-site-survey.md`
(candidate link, unconfirmed).

# Related AI rules

None yet.

# Open questions

- Whether this archetype should stay combined with, or split from, a future
  `warehouse` archetype.
- Typical company size / employee count.
- Which `solutions/`, `products/` Teleprofi actually deploys.

# Knowledge History

| Version | Date | Change | Source |
|---|---|---|---|
| 0.1 | 2026-07-22 | Initial candidate draft from Teleprofi interview-answer document | Teleprofi candidate interview draft (unconfirmed) |

# Knowledge Confidence

| Area | Confidence | Reason |
|---|---|---|
| Typical problems | needs-confirmation | sourced from an unconfirmed candidate interview draft |
| Recommended solutions/products/services | needs-confirmation | not yet captured at all |
