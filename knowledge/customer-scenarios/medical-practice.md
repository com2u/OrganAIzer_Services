---
id: medical-practice
type: customer-scenario
owner: unassigned
status: draft
knowledge_version: 0.1
last_reviewed: 2026-07-22
sources:
  - "Teleprofi candidate interview-answer document (unconfirmed, 2026-07-22)"
industry: medical-practice
typical_company_size: any
---

> **Status: Candidate draft from the Teleprofi interview-answer document.**
> **Requires Patrick/Renato confirmation before merge.**

# Overview

> Arztpraxen (medical practices) — a reusable archetype, not a real customer.

<A **reusable archetype**. Real accounts live in `customers/`; reusable
packages live in `solutions/`. This entry references products/services/
providers/solutions — it does not duplicate them.>

# Typical company size

Not yet captured — the draft does not state a typical headcount range for
this archetype.

# Typical problems

> Candidate content — from the interview draft's "Branche" answers, not yet
> confirmed against real Teleprofi engagements.

- Hohe Erreichbarkeit zu Stoßzeiten (peak-time reachability under pressure).
- Ansagen und Warteschleifen (announcements/queueing) matter more than for a
  typical small office.
- Klare Trennung medizinischer Notfälle von organisatorischen Anliegen (a
  caller with a medical emergency must be routed differently from routine
  administrative calls).
- Datenschutz (data protection) is a stated concern for this archetype.
- Häufig Fax- oder Altgeräte im Einsatz (fax/legacy devices still common).
- Strukturierte Rufgruppen (structured call/ring groups).
- Zuverlässige Vertretungs- und Pausenregeln (reliable
  cover/lunch-break-handling rules).

# Typical infrastructure

Not yet captured.

# Recommended solutions

Not yet determined — needs confirmation before any `solutions/` entry
references this archetype.

# Recommended products

Not yet determined.

# Recommended services

Not yet determined.

# Recommended providers

Not yet determined.

# Pricing references

None — no prices in this entry; see `pricing/` once populated.

# Installation notes

Not yet captured. See `business-philosophy/installation-philosophy.md` for
the generic delivery workflow.

# Sales notes

Draft candidate note: the interview draft's "Branche" answer explicitly
cautions that industry gives hints but never replaces the concrete needs
analysis — two practices in the same field can have very different setups
and risks. Treat the list above as starting questions, not a fixed package.

# Technician notes

Not yet captured.

# Related solutions

None yet.

# Related products

None yet.

# Related services

None yet.

# Related AI rules

None yet.

# Open questions

- Typical company size / employee count for this archetype.
- Which `solutions/`, `products/`, `services/` Teleprofi actually deploys for
  medical practices.
- Whether "medical emergency vs. organisational call" routing implies a
  specific COMtrexx configuration pattern worth documenting.
- Confirm this archetype is distinct enough from a general small-office
  scenario to warrant its own file (vs. folding into `small-office`).

# Knowledge History

| Version | Date | Change | Source |
|---|---|---|---|
| 0.1 | 2026-07-22 | Initial candidate draft from Teleprofi interview-answer document | Teleprofi candidate interview draft (unconfirmed) |

# Knowledge Confidence

| Area | Confidence | Reason |
|---|---|---|
| Typical problems | needs-confirmation | sourced from an unconfirmed candidate interview draft |
| Recommended solutions/products/services | needs-confirmation | not yet captured at all |
