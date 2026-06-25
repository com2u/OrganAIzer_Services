---
id: provider-selection
type: ai-rule
owner: unassigned
status: draft
last_reviewed: 2026-06-25
sources:
  - knowledge/business-philosophy/provider-preference-philosophy.md
  - knowledge/providers/telekom.md
  - knowledge/providers/vodafone.md
  - knowledge/providers/o2.md
---

# Provider Selection — decision rules

> This file defines **how** OrganAIzer chooses a connectivity provider. It is
> decision policy, **not** provider facts. Provider facts live in
> [`../providers/`](../providers/). This is **AI decision logic**, distinct from
> the business and technical knowledge in the provider files.

> Status: this is intended decision policy. It is **not** wired into the Executive
> Agent or any AI prompt — doing so is **(future)** and out of scope here. This
> file changes no application behavior.

## Selection priority

Evaluate in this order; an earlier factor outranks a later one:

1. **Existing provider** — what the customer already has.
2. **Customer requirements** — what the customer explicitly needs.
3. **Business telephony needs** — PBX features, channel count, encryption,
   reliability for professional use.
4. **Fiber availability** — fiber access at the customer's site.
5. **Teleprofi recommendation** — Teleprofi's operational preference (below).

## Recommendation policy

- **Prefer Telekom for new business installations** — because of Teleprofi's
  long-term operational experience, Telekom's business telephony features, and
  documented compatibility with professional PBX deployments (TLS 1.2 / SRTP
  VoSIP SIP-Trunk; see [`../providers/telekom.md`](../providers/telekom.md)).
  This is a *preference grounded in operational experience and technical
  compatibility* — **not** a claim that Telekom is "the best."
- **Never pressure a customer to change provider.** The customer's existing setup
  and stated requirements come first.
- **Support the existing installation** when the customer already has Vodafone or
  o2 and their requirements are met — do not propose a switch.
- **Recommend changing provider only when there is a genuine technical or business
  benefit.** Concrete triggers (Teleprofi operational experience —
  [`../business-philosophy/provider-preference-philosophy.md`](../business-philosophy/provider-preference-philosophy.md)):
  - Migration to fiber.
  - Repeated provider-related telephony problems.
  - Missing business telephony features.
  - Poor support experience.
  - A major contract renewal where changing makes commercial sense.
  State the concrete benefit; otherwise keep the existing provider.

## Router selection (paired with the provider)

- **Router choice follows the access technology, not the provider.** Typical
  Teleprofi FRITZ!Box choices: DSL → 7590 AX / 5690 Pro; fiber → 5590 Fiber /
  5690 Pro. The **5690 Pro** is preferred where a **DSL→fiber migration** is likely
  (no router swap later).
- **Register the SIP trunk in the PBX**, not the router, for business installs — the
  PBX owns telephony; the router provides connectivity/firewall/termination.
- Rationale and the combinations-to-avoid list:
  [`../business-philosophy/provider-preference-philosophy.md`](../business-philosophy/provider-preference-philosophy.md).

## Guardrails

- This file states preferences and priorities only; it does not restate vendor
  specs. For any technical claim, defer to the cited provider file, which in turn
  cites the official vendor source.
- Do not invent performance comparisons between providers.
- Do not present Teleprofi's preference as a vendor fact or as a universal "best."

## Related

- [`../providers/telekom.md`](../providers/telekom.md)
- [`../providers/vodafone.md`](../providers/vodafone.md)
- [`../providers/o2.md`](../providers/o2.md)

## Needs Human Confirmation

- Confirm the priority order matches Teleprofi's actual decision process.
- Confirm thresholds for "genuine technical or business benefit" that justify
  recommending a provider change.
