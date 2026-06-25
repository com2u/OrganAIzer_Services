# Pricing — commercial knowledge

This folder holds **pricing knowledge**: net/gross figures, VAT, recurring vs.
one-time amounts, and validity windows for hardware, licenses, services,
rentals, leasing, factoring calculations, and bundles.

Pricing is **commercial knowledge** and **changes faster than product knowledge**.
It is dated, sourced, and treated as churny by design. Product profiles in
`products/` describe *what a product is*; pricing entries describe *what it costs
and when that was true*. The two are kept separate so product knowledge stays
durable while prices move.

**Product files must reference pricing entries — never embed prices.** A product's
*Pricing References* section points here; it does not restate figures.

## Rules for pricing files

- **Use the template.** Every entry is a copy of
  [`../templates/pricing-template.md`](../templates/pricing-template.md).
- **Always cite a source document.** Every price must name the offer, quote, or
  price list it comes from (`source_document`). No source → the entry is invalid.
- **Offer prices are historical examples** unless explicitly confirmed current
  (`confidence: confirmed-current`). Otherwise mark `offer-historical`.
- **Mark leasing/factoring/rental separately from purchase prices.** Never present
  a financed or recurring figure as a hardware purchase price.
- **List price ≠ customer discount.** Customer-specific discounts must not be
  recorded as the default list price; capture them as exceptions, not the norm.
- **No sensitive customer data.** Do not copy customer names, addresses, contacts,
  or other PII from an offer into a pricing entry — abstract to the priced item.
- **Reference operational config** (article numbers tied to system behavior, etc.)
  at its single source of truth rather than copying it.
- **Date everything.** Set `valid_from` / `valid_until` and bump `last_reviewed`.

## Adding a pricing entry

1. Copy `../templates/pricing-template.md` into this folder.
2. Rename it to a stable `id` (kebab-case, e.g. `comfortel-d-200-hardware-list.md`).
3. Fill in the frontmatter, including `source_document` and `confidence`.
4. Keep customer PII out; mark leasing/factoring/rental distinctly.
5. Have it reviewed; set `status: active` and `last_reviewed`.

> No pricing entries exist yet — this is a placeholder so the taxonomy is in place.
> A future indexing/search layer over this knowledge is **(future)** and not built.
