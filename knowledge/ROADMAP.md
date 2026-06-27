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

Populate `products/` for the current Teleprofi catalogue. Strategy: create each as a
high-quality **v0.1 draft** first (reusing family/philosophy/providers/services/
solutions), capturing gaps as interview questions, then deepen via consolidated
Renato/Patrick interviews. Current build order and progress:

**PBX**
- ✅ **COMtrexx Next** — v1.0 (`products/comtrexx-next.md`)
- ✅ **COMtrexx Flex** — v0.2 (`products/comtrexx-flex.md`)
- (family) **COMtrexx family** decision logic (`products/comtrexx-family.md`)

**DECT** (done)
- ✅ **COMfortel M-730** — v0.1 (`products/comfortel-m730.md`)
- ✅ **COMfortel M-710** — v0.1 (`products/comfortel-m710.md`)

**Remaining, reordered by recommendation impact** (routers/migration paths first —
the Executive Agent recommends these more often than individual DECT infrastructure):

1. ✅ **FRITZ!Box 5690 Pro** — v0.1 (`products/fritzbox-5690-pro.md`)
2. ✅ **FRITZ!Box 5590 Fiber** — v0.1 (`products/fritzbox-5590-fiber.md`)
3. ✅ **FRITZ!Box 7590 AX** — v0.1 (`products/fritzbox-7590-ax.md`)
   - (family) ✅ **FRITZ!Box router selection model** (`products/fritzbox-family.md`)
4. ✅ **FRITZ!Repeater 6000** — v0.1 (`products/fritz-repeater-6000.md`)
5. ✅ **WS-500S** (DECT base) — v0.1 (`products/ws-500s.md`)
6. ✅ **Gigaset N670** (DECT base — alternative) — v0.1 (`products/gigaset-n670.md`)
7. ✅ **COMfortel D-210** (desk phone) — v0.1 (`products/comfortel-d210.md`)
8. ✅ **COMfortel D-400** (desk phone) — v0.1 (`products/comfortel-d400.md`)
9. ✅ **COMfortel D-600** (desk phone) — v0.1 (`products/comfortel-d600.md`)
10. ✅ **TFS door systems** — v0.1 (`products/tfs-door-systems.md`)

Each entry is Teleprofi-first (≈60/30/10), references reusable knowledge, and
carries Knowledge History + Knowledge Confidence. No pricing in product entries.

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
