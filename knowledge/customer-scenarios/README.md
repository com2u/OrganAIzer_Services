# Customer Scenarios — reusable customer archetypes

This folder holds **reusable customer archetypes**: real-world buying/use-case
*patterns* by industry or situation — not individual customers. Each captures what
Teleprofi typically encounters and recommends for that kind of customer.

## Scenario vs. customer vs. solution vs. project

- **customer-scenario** (this folder) — a *type* of customer (e.g. "dentist
  office", "hotel"): typical size, problems, infrastructure, and what Teleprofi
  usually recommends. Reusable.
- **`customers/`** — an *actual* customer/account profile. One real account.
- **`solutions/`** — a *reusable package* (products + services + providers).
- **`projects/`** — an *actual* time-bound engagement, which may apply a solution
  to a customer that matches a scenario.

A scenario typically **points to** one or more solutions; it does not duplicate
them.

## Candidate archetypes (examples only — not yet created)

dentist-office · medical-practice · law-office · small-office · logistics-company ·
warehouse · retail-shop · hotel · municipality · restaurant.

> These are illustrative. Do **not** invent industries or recommendations — create a
> scenario only when Teleprofi knowledge for it exists, and capture gaps as Open
> Questions / *Knowledge Needed* items.

> **CANDIDATE ADDITION — Teleprofi interview draft, unconfirmed.**
> **Requires Patrick/Renato confirmation before merge.**
>
> `handwerksbetrieb` (trade/craft business) was not in the original
> candidate list above — it is proposed as an addition by the interview
> draft (Interview 2 "BRANCHE"), which also drafted content for
> `medical-practice`, `law-office`, `logistics-company`, `hotel`, and
> `restaurant` from the existing list. See
> [`./handwerksbetrieb.md`](./handwerksbetrieb.md) for the draft content;
> confirm before treating it as an established archetype.

## Rules for scenario files

- **Use the template.** Every entry copies
  [`../templates/customer-scenario-template.md`](../templates/customer-scenario-template.md).
- **Reference, don't duplicate** products/services/providers/solutions/pricing.
- **Defer choice logic to `ai-rules/`** and reasoning to `business-philosophy/`.
- **No embedded prices**; link to `pricing/`.
- **Include Knowledge History and Knowledge Confidence** (expected in major entries).

## Adding a scenario

1. Copy `../templates/customer-scenario-template.md` into this folder.
2. Rename to the archetype `id` (kebab-case, e.g. `dentist-office.md`).
3. Fill in `industry`, `typical_company_size`, and the body — referencing other
   knowledge rather than restating it.
4. Have it reviewed; set `status: active` and `last_reviewed`.

> No scenario files exist yet — this is a placeholder so the taxonomy is in place.
