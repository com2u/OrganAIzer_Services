# Import Guide — how to author a knowledge entry

How to turn a piece of real knowledge into a reviewed entry in this repository.
Read [`README.md`](./README.md) for the taxonomy and [`BUILD_ORDER.md`](./BUILD_ORDER.md)
for the sequence; this guide is the per-entry workflow.

## 1. Pick the right template

Use [`templates/README.md`](./templates/README.md) to choose. In short:

| If the knowledge is… | Folder | Template |
|---|---|---|
| a device / software / license | `products/` | `templates/product-template.md` |
| a business offering (install, support, survey, contract) | `services/` | `templates/service-template.md` |
| a connectivity carrier/ISP | `providers/` | `templates/provider-template.md` |
| a price (sourced, dated) | `pricing/` | `templates/pricing-template.md` |
| what a customer buys (composition) | `solutions/` | `templates/solution-template.md` |
| a reusable customer **archetype** (industry/use-case) | `customer-scenarios/` | `templates/customer-scenario-template.md` |
| a reusable Teleprofi operating principle | `business-philosophy/` | `templates/base.md` |
| how to choose between options | `ai-rules/` | (see `ai-rules/README.md`) |
| an actual customer/account profile | `customers/` | `customers/_template.md` |
| a runbook (how to perform work) | `procedures/` | `procedures/_template.md` |
| a decision record | `decisions/` | `decisions/_template.md` |

Copy the template, rename to the entry `id` (kebab-case), and fill it in.

## 2. Fill in mandatory sections

- **All entries** carry the shared frontmatter: `id`, `type`, `owner`, `status`,
  `last_reviewed`, `sources` (see `README.md` field conventions), plus the
  class-specific frontmatter fields in the template.
- **Keep every mandatory section** the template defines — do not delete headings.
  If a section genuinely doesn't apply, say so explicitly (e.g. "Not applicable")
  rather than removing it.
- Class-specific musts:
  - **Products / Services / Providers** — keep Customer / Sales / Technician views
    separate.
  - **Solutions** — reference parts and explain **why** each is selected.
  - **Pricing** — every entry needs a `source_document` and a `confidence`.

## 3. Reference other knowledge — never duplicate

- **Link, don't copy.** Solutions reference products/services/providers/pricing;
  services reference the procedures that perform them; pricing references the
  product/service it prices. Restating another entry's content creates drift.
- Use relative markdown links (e.g. `[`telekom`](../providers/telekom.md)`).
- A product's price lives in `pricing/`, not in the product file. A service's
  steps live in `procedures/`, not in the service file.

## 4. One source of truth

- **Operational config is referenced, never copied.** Ports, IPs, env vars, and
  COMtrexx values (`003010`, `778`, `779`) live in their authoritative source —
  link to it. See `README.md` → "One source of truth".
- **Billing terms** come from [`BILLING_VOCABULARY.md`](./BILLING_VOCABULARY.md):
  services' `billing_model` and pricing's `price_type` use the **same** canonical
  vocabulary.

## 5. Citation requirements

- **Repository evidence first**, then public/official documentation for gaps.
- **Every technical claim cites an official source** (vendor doc, spec sheet) in
  `sources` and/or inline. Do not invent specs or performance comparisons.
- **Every price cites a `source_document`** (offer/quote/price list). No source →
  the entry is invalid. Offer prices are historical unless confirmed current.

## 5a. Knowledge History & Knowledge Confidence (major entries)

Major entries — **products, services, solutions, customer-scenarios** — carry two
standard sections (already in their templates). They make an entry's maturity and
trustworthiness explicit, supporting the iterative interview workflow.

- **Knowledge History** — a changelog, one row per meaningful update:

  | Version | Date | Change | Source |
  |---|---|---|---|

  Pair it with the `knowledge_version` frontmatter field (e.g. `0.1` → `1.0` as the
  *Knowledge Needed* questions get answered). Append rows; don't rewrite history.

- **Knowledge Confidence** — a per-area rating:

  | Area | Confidence | Reason |
  |---|---|---|

  Confidence values: **high | medium | low | needs-confirmation**.
  - `high` — official source or confirmed Teleprofi knowledge.
  - `medium` — partial / indirect evidence.
  - `low` — weak / assumed; flag prominently.
  - `needs-confirmation` — unverified; **must** map to an Open Question or a
    *Knowledge Needed* item.

Update both sections on every meaningful review, alongside `last_reviewed`.

## 6. Marking "Needs Human Confirmation"

When a fact is unverified, do **not** guess. Instead:

- Put the item under the entry's **Open Questions** (or **Needs Human
  Confirmation**) section, phrased as a concrete question.
- For pricing, set `confidence: needs-confirmation` while any item is open.
- Mark experiential statements (e.g. support experience) as experience, dated.
- Never present an unconfirmed assumption as an established fact.

## 7. Review workflow

1. Author the entry as `status: draft`, `owner` set (or `unassigned` only briefly).
2. Fill all mandatory sections; add references and citations.
3. Resolve or explicitly flag open questions.
4. Human review for accuracy, citations, no-duplication, no embedded prices/PII.
5. On approval: set `status: active` and bump `last_reviewed` (YYYY-MM-DD).
6. Re-review on change; a stale `last_reviewed` is a defect, not cosmetic.

## 8. Common mistakes to avoid

- ❌ **Duplicating** a product/pricing description instead of linking to it.
- ❌ **Embedding prices** in product/service/solution files (pricing → `pricing/`).
- ❌ **Copying operational config** (ports, IPs, COMtrexx values) instead of referencing it.
- ❌ **Inventing specs or performance comparisons** to fill a gap — flag it instead.
- ❌ **Putting recommendation logic in fact files** — that belongs in `ai-rules/`.
- ❌ **Confusing services with procedures** — service = offering, procedure = how.
- ❌ **Copying customer PII** from offers into pricing/other entries.
- ❌ **Diverging billing terms** — always use `BILLING_VOCABULARY.md`.
- ❌ **Leaving `status: active` without a fresh `last_reviewed`.**
- ❌ **Deleting mandatory sections** instead of marking them "Not applicable".
