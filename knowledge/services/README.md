# Services — business offerings

This folder holds **service knowledge**: the business offerings a customer can
buy — for example *fiber installation*, *rack cleanup*, *remote support*, a
*maintenance contract*, or a *Wi-Fi survey*.

## Services are NOT procedures

This is the key distinction:

- A **service** (this folder) is a **business offering** — what is sold, to whom,
  what it includes, and why. It is commercial/positioning knowledge.
- A **procedure** (`procedures/`) describes **how the work is performed** — the
  operational runbook the technician follows.

"Wi-Fi survey" is a service. "How to run a Wi-Fi survey" is a procedure. A service
file **references** the procedure(s) that deliver it; it never restates the steps.

## Where services fit

Services are referenced by `solutions/` (a solution combines products + services +
providers + pricing + installation + AI rules) and are priced via `pricing/`
(service / installation prices). Services reference `products/` they act on and
`providers/` they coordinate with.

## Rules for service files

- **Use the template.** Every entry is a copy of
  [`../templates/service-template.md`](../templates/service-template.md).
- **A service is an offering, not a runbook.** Link to `procedures/` for the how.
- **Reference pricing, never embed it.** Link to `pricing/` entries.
- **Reference products/providers**, don't duplicate their descriptions.
- **Reference operational config** at its single source of truth.

## Adding a service

1. Copy `../templates/service-template.md` into this folder.
2. Rename it to a stable `id` (kebab-case, e.g. `fiber-installation.md`).
3. Fill in the frontmatter (`service_category`, `billing_model`, `delivery_mode`,
   plus the shared fields).
4. Reference the `procedures/` runbook(s) that perform the work.
5. Have it reviewed; set `status: active` and `last_reviewed`.

> No service entries exist yet — this is a placeholder so the taxonomy is in
> place. A future indexing/search layer is **(future)** and not built.
