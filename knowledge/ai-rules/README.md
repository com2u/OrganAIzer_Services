# AI Rules — decision logic

This folder holds **AI decision rules**: how OrganAIzer *chooses* between options.
It is deliberately separate from the fact folders.

## The separation

- **Business knowledge** — market position, customer fit, sales guidance → lives
  in the relevant fact folder (`providers/`, `products/`, `companies/`).
- **Technical knowledge** — compatibility, configuration, specs (with sources) →
  also in the fact folders.
- **AI decision rules** — *how to choose* given the facts → **here**.

A fact file says "Telekom's SIP-Trunk supports TLS 1.2/SRTP." A rule file says
"prefer Telekom for new business installations, and never pressure a customer to
switch." Keeping these apart means facts can change without rewriting policy, and
policy can change without touching facts.

## Rules for rule files

- State decision logic only — priorities, preferences, guardrails.
- Do **not** restate provider/product facts; **link** to the fact files instead.
- Recommendation policy must be explicit, reviewable, and owned.
- Never encode a recommendation as if it were a vendor fact.

> These files describe intended decision policy. Wiring them into the Executive
> Agent or any model prompt is **(future)** — creating a rule here does **not**
> change application behavior or AI prompts.
