# Business Philosophy — reusable Teleprofi operating principles

> This folder is **Teleprofi business philosophy**: the cross-cutting operating
> principles and policies that drive how Teleprofi sells, plans, installs and
> supports — independent of any one product. (Renamed from `philosophy/` to make
> the "business" scope explicit.)

This folder holds **Teleprofi's cross-cutting operating principles and policies** —
the durable "how Teleprofi thinks and works" knowledge that applies across many
products, services and solutions.

These entries exist so that principles are written **once** and **referenced**
everywhere, instead of being re-explained (and drifting) inside every product file.
A product's *AI Recommendation Notes* or *Installation Process* should link to the
relevant philosophy entry rather than restating it.

## What lives here

- **Product selection philosophy** — how Teleprofi decides what to recommend.
- **Growth planning philosophy** — sizing to future business needs, not today's count.
- **Installation philosophy** — how Teleprofi delivers systems.
- **Firmware policy** — how Teleprofi handles firmware/stability.
- **Maintenance philosophy** — how Teleprofi keeps systems stable as a service.
- **Provider & router preference philosophy** — how Teleprofi chooses providers and
  routers and wires telephony (trunk-in-PBX).
- **Financing philosophy** — purchase vs. rental vs. leasing (Grenke); technical
  fit first, financing supports it.

## Relationship to `ai-rules/`

Philosophy = the **why / principle** (durable Teleprofi values). `ai-rules/` =
concrete **decision logic** the agent applies, which *references* these principles.
Product-specific thresholds (e.g. the exact user count to switch from Next to Flex)
live in the product entry and/or an `ai-rules/` file; the underlying principle lives
here.

## Rules

- Keep entries **product-agnostic** — reusable across the portfolio.
- Mark **Teleprofi operational experience** clearly and separately from vendor facts.
- Reference operational config / pricing at its single source of truth; don't copy.

> These are durable, curated principles. Wiring them into the Executive Agent or any
> AI prompt is **(future)** and out of scope here.
