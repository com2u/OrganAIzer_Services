---
id: provider-preference-philosophy
type: philosophy
owner: unassigned
status: active
last_reviewed: 2026-06-25
sources:
  - Teleprofi operational knowledge (Renato, 2026-06-25)
  - knowledge/ai-rules/provider-selection.md
  - knowledge/providers/telekom.md
  - backend/voice/knowledge/teleprofi_fulda.md
---

# Teleprofi Provider & Router Preference Philosophy

> Reusable principle — the durable "why" behind how Teleprofi chooses **providers
> and routers** for business customers, and how it wires telephony. The concrete
> selection *decision logic* lives in `ai-rules/provider-selection.md`; this entry
> is the principle it applies. Captured from Teleprofi operational knowledge.

## Provider preference

Teleprofi's preferred provider for **new business installations** is **Telekom** —
not because other providers are "bad", but because, from Teleprofi's operational
experience, Telekom delivers the most **consistent business telephony platform**.

**Why Telekom is preferred** (Teleprofi operational experience):

- Reliable SIP-trunk operation.
- Good compatibility with Auerswald COMtrexx systems.
- Mature CompanyFlex platform.
- Stable business support.
- Long-term availability.
- Fewer telephony-related issues during deployment and operation.

**Vodafone and o2 are fully supported.** If a customer already has Vodafone or o2
and the installation works well, Teleprofi does **not** recommend changing provider
simply because Telekom is preferred — existing customer investments are respected.

## When to recommend a provider change

Only when there is a **genuine technical or business advantage**, for example:

- Migration to fiber.
- Repeated provider-related telephony problems.
- Missing business telephony features.
- Poor support experience.
- A major contract renewal where changing makes commercial sense.

So: recommend **Telekom primarily for new business installations**, while respecting
working existing setups.

## Router selection

Router choice is driven **primarily by the customer's internet access technology**
(and future growth), with the provider influencing configuration rather than the
router model. Teleprofi-typical AVM FRITZ!Box choices:

- **DSL installations:** FRITZ!Box 7590 AX, or FRITZ!Box 5690 Pro.
- **Fiber installations:** FRITZ!Box 5590 Fiber, or FRITZ!Box 5690 Pro.

The **5690 Pro is particularly valuable for DSL→fiber migration**: a customer can
start on DSL now and later migrate to fiber **without replacing the router**. This
is a future-proofing choice, consistent with [[product-selection-philosophy]] and
[[growth-planning-philosophy]].

## SIP-trunk registration

Professional business installations should register the **SIP trunk directly in the
COMtrexx PBX whenever practical**, so the **PBX controls business telephony**:

- Call routing, groups, IVR, announcements, call forwarding, and other business
  telephony features belong to the PBX.
- The FRITZ!Box should mainly provide **internet connectivity, firewall, network
  routing, and fiber/DSL termination**.
- The router should **not** unnecessarily replace PBX functionality.

(Applies across PBX deployments; the COMtrexx family references this — see
`products/comtrexx-family.md`.)

## Provider / router combinations to avoid

Teleprofi avoids configurations that unnecessarily complicate business telephony:

- Providers that cannot deliver complete SIP-trunk information.
- Routers that interfere with SIP registration.
- Consumer telephony configurations in business environments.
- Incomplete fiber migrations where provider data is still unavailable.
- Temporary ISP configurations that will shortly change again.

The objective is always **long-term stability over the lowest purchase price**.

## Relationship to decision logic

- **This entry:** the principle (why a preference exists, how routers/trunks are
  chosen, and the guardrails).
- **`ai-rules/provider-selection.md`:** the operational decision logic (priority
  order; when to support existing vs. recommend a change).

> Source: Teleprofi operational knowledge + repository provider/AI-rule knowledge.
