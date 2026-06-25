---
id: example-provider
type: provider
owner: unassigned
status: draft
last_reviewed: 2026-06-24
sources: []
provider_type:        # carrier | isp | sip-trunk | fiber | dsl | mobile | reseller
country:              # primary country of operation, e.g. DE
supported_services:   # list, e.g. [sip-trunk, fiber, dsl, all-ip]
---

# Overview

> One-line summary: who the provider is and what connectivity it supplies.

<What the provider is and the role it plays as connectivity *beneath* products.
Providers are NOT products: they describe Internet, SIP, fiber and telephony
connectivity that products (PBX, routers, phones) depend on. This file holds
business and technical knowledge only — it contains **no AI decision rules**.
Recommendation logic lives in `ai-rules/`.>

# Business Position

<The provider's market position and segment focus (business vs. consumer),
objectively stated. No "best"/superlative claims; no invented comparisons.>

# Customer View

## Benefits
<What the customer gains from this provider.>

## Typical customers
<The customer profile this provider tends to fit.>

## Limitations
<Honest constraints, gaps, or trade-offs.>

# Sales View

## When to recommend
<Scenarios where this provider is a good fit.>

## When NOT to recommend
<Disqualifiers and poor-fit scenarios.>

## Migration scenarios
<Moving to/from this provider; portability and cutover considerations.>

## Upsell opportunities
<Complementary services or capacity tiers.>

# Technician View

> For every technical claim, cite an official vendor source. Reference operational
> config (ports, certs, COMtrexx values) at its single source of truth rather than
> copying it. Do not invent specs or performance numbers.

## SIP compatibility
<SIP-trunk support, transport, encryption requirements — with vendor citations.>

## Fiber compatibility
<Fiber access options relevant to business telephony.>

## DSL compatibility
<DSL/VDSL access options.>

## Router compatibility
<Which routers are supported/required (e.g. AVM FRITZ!Box).>

## PBX compatibility
<Compatibility with the PBXs Teleprofi deploys (e.g. Auerswald COMtrexx).>

## Typical configuration considerations
<Recurring setup parameters and prerequisites.>

## Common issues
<Recurring problems seen with this provider.>

## Troubleshooting references
<Link to `procedures/` runbooks and official vendor troubleshooting docs.>

# Support Experience

<Operational experience dealing with this provider's business support: channels,
responsiveness, escalation reality. Mark experiential statements as such.>

# Related Products

<Link to `products/` entries that depend on or pair with this provider.>

# Related Procedures

<Link to `procedures/` runbooks for provisioning or troubleshooting.>

# Related ADRs

<Link to `decisions/` records that constrain how this provider is used.>

# Related Providers

<Link to other `providers/` entries (alternatives, predecessors, successors).>

# Open Questions

<Unresolved items and anything that still needs human confirmation.>
