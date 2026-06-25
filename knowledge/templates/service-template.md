---
id: example-service
type: service
owner: unassigned
status: draft
last_reviewed: 2026-06-24
sources: []
service_category:   # installation | maintenance | support | survey | cleanup | consulting | other
billing_model:      # canonical billing term — see ../BILLING_VOCABULARY.md
                    # (purchase | installation | hourly-service | fixed-service |
                    #  maintenance | rental | leasing | factoring | subscription | other)
delivery_mode:      # on-site | remote | hybrid
---

# Overview

> One-line summary: the business offering and the outcome it delivers.

<What this service is, as a **business offering** the customer buys — e.g. fiber
installation, rack cleanup, remote support, a maintenance contract, a Wi-Fi
survey. A service is **not** a procedure: a procedure (`procedures/`) describes
*how* the work is performed; this file describes *what is offered, to whom, and
why*. Link to the procedure(s) that carry out the work rather than restating them.>

# Customer View

## What the customer gets
<The deliverable / outcome in the customer's terms.>

## Benefits
<Why the customer wants this.>

## Typical customer
<Who buys this service.>

# Sales View

## When to recommend
<Scenarios where this service fits.>

## When NOT to recommend
<Disqualifiers / poor-fit cases.>

## Upsell opportunities
<Related services or follow-on work.>

# Scope

## Included
<What the service covers.>

## Not included
<Explicit exclusions to prevent scope creep.>

## Prerequisites
<What must be true / supplied before the service can be delivered.>

# Technician View

<How delivery works at a high level, key considerations, and gotchas. Link to the
`procedures/` runbook(s) that define the actual steps; reference operational
config at its single source of truth rather than copying it.>

# Business Rules

## Billing
<One-time / recurring / per-hour / contract — referenced, not priced here.>

## SLA / response
<Any service-level commitments, if applicable.>

## Contract terms
<Term length, renewal, cancellation for recurring services.>

# Pricing References

> Reference only — no embedded prices. Link to the relevant `pricing/` entries.

<Pointers to the `pricing/` entries for this service.>

# Related Products

<Products this service installs, maintains, or supports (link to `products/`).>

# Related Providers

<Providers involved in delivering this service (link to `providers/`).>

# Related Procedures

<The `procedures/` runbook(s) that define HOW this service is performed.>

# Related Solutions

<Solutions that bundle this service (link to `solutions/`).>

# Related ADRs

<Links to `decisions/` records that constrain this service.>

# Open Questions

<Unresolved items and anything that still needs human confirmation.>

# Knowledge History

> Append one row per meaningful update so the entry's evolution is auditable.

| Version | Date | Change | Source |
|---|---|---|---|
| 0.1 | YYYY-MM-DD | Initial draft | <repo / official docs / Teleprofi> |

# Knowledge Confidence

> Rate each major area. Confidence values: **high | medium | low |
> needs-confirmation**. Low / needs-confirmation areas should map to an Open
> Question.

| Area | Confidence | Reason |
|---|---|---|
| <e.g. Scope / deliverables> | high | captured from Teleprofi |
| <e.g. Billing model> | medium | partial input |
| <e.g. SLA / response> | needs-confirmation | not yet captured |
