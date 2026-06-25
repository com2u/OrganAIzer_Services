# Solutions — what customers actually buy

This folder holds **solution knowledge**. Customers buy **solutions, not
products**: a coherent outcome that combines products, services, providers,
pricing references, installation guidance, and AI recommendation rules into one
answer to a business need.

A solution is the **composition layer**. A COMtrexx PBX is a product; "small-office
telephony for a 5-person practice" is a solution that *references* that product
plus the services, a provider, pricing, and a deployment procedure.

## What a solution combines

- **Products** — referenced from `products/`.
- **Services** — installation/configuration/migration/support.
- **Providers** — connectivity, referenced from `providers/`.
- **Pricing references** — pointers into `pricing/` (never embedded prices).
- **Installation guidance** — referenced from `procedures/`.
- **AI recommendation rules** — referenced from `ai-rules/`.

## Rules for solution files

- **Use the template.** Every entry is a copy of
  [`../templates/solution-template.md`](../templates/solution-template.md).
- **Never duplicate product descriptions.** Solutions **reference** products; the
  product detail stays in `products/`.
- **Reference pricing, never embed it.** Link to `pricing/` entries.
- **Explain WHY.** A solution must justify *why* each product/service/provider is
  selected for the customer's need — not just list them.
- **Defer choice logic to AI rules.** Provider/option selection logic lives in
  `ai-rules/`; solutions link to it rather than hard-coding decisions.
- **Reference operational config** at its single source of truth; don't copy
  ports, IPs, COMtrexx values, or env vars.

## Solutions vs. projects

A **solution** is **reusable knowledge** — a repeatable, templated answer to a
common customer need ("small-office telephony"). A **project** (`projects/`) is an
**actual customer engagement** — a specific, time-bound piece of work for one
customer. A project may *apply* a solution; the solution stays generic and
reusable, the project records what actually happened.

## Adding a solution

1. Copy `../templates/solution-template.md` into this folder.
2. Rename it to a stable `id` (kebab-case, e.g. `small-office-telephony.md`).
3. Fill in the frontmatter (`solution_category`, `target_customer`,
   `company_size`, plus the shared fields).
4. Reference products/services/providers/pricing/procedures — do not duplicate.
5. Have it reviewed; set `status: active` and `last_reviewed`.

> The entries currently in this folder are **placeholders** establishing the
> canonical structure — they are not yet filled with detailed content. A future
> indexing/search layer over this knowledge is **(future)** and not built.
