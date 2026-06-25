---
id: example-pricing
type: pricing
owner: unassigned
status: draft
last_reviewed: 2026-06-24
sources: []
product_or_service:     # what is priced (link to products/ entry where one exists)
sku_or_article_number:  # vendor/internal article number; "" if none
price_type:             # canonical billing term — see ../BILLING_VOCABULARY.md
                        # (purchase | installation | hourly-service | fixed-service |
                        #  maintenance | rental | leasing | factoring | subscription | other)
net_price:              # net amount in EUR; "" if not applicable
gross_price:            # gross amount in EUR; "" if not applicable
vat_rate:               # e.g. 19% (German standard); "" if not applicable
monthly_price:          # recurring monthly amount; "" for one-time only
one_time_price:         # one-off amount; "" for recurring only
billing_interval:       # one-time | monthly | quarterly | yearly | per-term
valid_from:             # YYYY-MM-DD this price became effective
valid_until:            # YYYY-MM-DD this price expires; "" if open-ended
source_document:        # REQUIRED: offer/quote/price-list reference this price is cited from
confidence:             # confirmed-current | offer-historical | estimated | needs-confirmation
notes:                  # caveats, conditions, scope of the price
---

# <Pricing Entry Title>

> One-line summary: what is priced, the price type, and whether it is current.

## What is priced

<The product, license, service, or bundle this entry prices. Link to the
`products/` entry where one exists. Pricing is commercial knowledge and changes
faster than product knowledge — keep this entry narrow and dated.>

## Price details

<Restate the relevant figures from the frontmatter in context: net/gross, VAT,
one-time vs. recurring, billing interval, and the term the price covers. State
the currency (EUR) and whether figures are net or gross explicitly.>

## Price type

<Set `price_type` to a **canonical billing term** from
[`../BILLING_VOCABULARY.md`](../BILLING_VOCABULARY.md) — the same vocabulary
services use for `billing_model`. State any type-specific conditions here:>

- **purchase** — one-time purchase of a device/unit; customer owns it.
- **installation** — one-off labour/setup/on-site work.
- **hourly-service** — work billed per hour.
- **fixed-service** — work billed as a fixed price for a defined scope.
- **maintenance** — ongoing maintenance/care, typically under a contract.
- **rental** — recurring rental of hardware (customer does not own it).
- **leasing** — financed acquisition over a term; **not** a purchase price.
- **factoring** — factoring-partner calculation; **not** a purchase price.
- **subscription** — recurring license/service fee (per-user, per-device, per-term).
- **other** — note specifics and flag under Needs Human Confirmation.

> **`leasing`, `factoring`, and `rental` are never presented as `purchase`.**
> Never present a financed or recurring figure as a hardware purchase price.

## Source & validity

<Cite the `source_document` (offer number, quote, price list, vendor sheet) this
price comes from. State `valid_from` / `valid_until` and whether the figure is
confirmed current or a historical example.>

- **Every price must cite a source document.** No source → the entry is invalid.
- **Prices taken from offers are historical examples** unless explicitly
  confirmed as current (`confidence: confirmed-current`).
- **Customer-specific discounts are not list price.** Do not record a negotiated
  or discounted figure as the default; capture list price, and note discounts as
  exceptions only.
- **No sensitive customer data.** Do not copy customer names, addresses, contacts,
  or other PII from an offer into a pricing entry — abstract to the priced item.

## Related pricing

<Link to alternative price types for the same item (e.g. purchase vs. leasing vs.
rental) so they are never confused.>

## Needs Human Confirmation

<List any unresolved pricing-policy questions or figures awaiting confirmation —
e.g. "Is this offer price still current?", "Which VAT rate applies to this
service?", "Is this the list price or a customer-specific discount?". Set
`confidence: needs-confirmation` while any item here is open.>
