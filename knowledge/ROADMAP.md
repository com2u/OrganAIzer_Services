# Roadmap — knowledge population phase

Framework v1 is **complete**: the taxonomy, templates, READMEs, billing
vocabulary, build order, and import guide all exist. This roadmap covers only the
**population phase** — filling the framework with real, reviewed knowledge. It
does **not** re-list completed framework work.

Population follows the dependency sequence in [`BUILD_ORDER.md`](./BUILD_ORDER.md)
(Products → Services → Providers → Pricing → Solutions → Customer Types → AI
Rules → Compatibility → Playbooks) and the per-entry workflow in
[`IMPORT_GUIDE.md`](./IMPORT_GUIDE.md).

> Scope guardrails for the whole phase: knowledge repository only — no application
> code, tests, AI-prompt wiring, database, or RAG.

## Phase 1 — Products (foundation)

Populate `products/` for the current Teleprofi catalogue, in this order:

1. **COMtrexx Next** (PBX)
2. **COMtrexx Flex** (PBX)
3. **COMfortel M-710** (DECT handset)
4. **COMfortel M-730** (DECT handset)
5. **WS-500S** (DECT base)
6. **WS-500M** (DECT base)
7. **FRITZ!Box family** (routers — current + legacy/supported)
8. **FRITZ!Repeater family** (WLAN repeaters)
9. **TFS systems** (door / Türsprech systems)

Each as a full product entry (Customer/Sales/Technician views, no pricing).

## Phase 2 — Teleprofi services

Promote the 10 service placeholders in `services/` to reviewed entries with real
scope, prerequisites, billing model (canonical vocabulary), and links to the
`procedures/` runbooks that perform them.

## Phase 3 — Pricing from offers

Populate `pricing/` from existing offers/quotes. Each entry cites its
`source_document`; offer-derived figures are marked historical unless confirmed
current. No customer PII; list price ≠ customer discount.

## Phase 4 — Grenke leasing

Add leasing pricing via the Grenke partner, marked distinctly as `leasing`
(never as `purchase`). Capture factoring calculations separately where they apply.

## Phase 5 — Customer types

Populate `customers/` archetypes (by segment / company size — suggested segments
plus custom ranges) so solutions have real targets to reference.

## Phase 6 — Solution population

Fill the six solution placeholders (and any new ones) with real composition:
referenced products, services, providers, pricing, install procedures — each with
the **why** behind the selection.

## Phase 7 — AI recommendation rules

Expand `ai-rules/` beyond `provider-selection.md` to cover product/solution
recommendation logic, grounded in the now-populated facts. Decision logic only;
wiring into the Executive Agent / prompts remains **(future)**, out of scope here.

## Later (defined when reached)

- **Compatibility** knowledge (cross-references between products/providers).
- **Playbooks** (end-to-end operational/sales playbooks).

Both get their folder/template homes when their phase begins.
