# Billing Vocabulary — canonical

One shared vocabulary for **how something is charged**, used consistently across
`services/` (`billing_model`) and `pricing/` (`price_type`). Templates reference
this list instead of maintaining diverging enumerations, so the two folders never
drift apart.

> This is the **single source of truth** for billing/charge model terms. Do not
> invent synonyms; if a real case doesn't fit, use `other` and raise it under
> *Open Questions* so the vocabulary can be extended deliberately.

## Canonical terms

| Term | Meaning |
|---|---|
| `purchase` | One-time purchase of hardware/goods; customer owns it. |
| `installation` | One-off labour/setup/on-site work to deploy something. |
| `hourly-service` | Work billed per hour (e.g. ad-hoc remote/on-site support). |
| `fixed-service` | Work billed as a fixed price for a defined scope. |
| `maintenance` | Ongoing maintenance/care, typically under a contract. |
| `rental` | Recurring rental of hardware; customer does not own it. |
| `leasing` | Financed acquisition over a term; **not** a purchase price. |
| `factoring` | Factoring-partner calculation; **not** a purchase price. |
| `subscription` | Recurring license/service fee (per-user, per-device, per-term). |
| `other` | Anything not covered above — note the specifics and flag it. |

## Rules

- **`leasing`, `factoring`, and `rental` are never presented as `purchase`.** A
  financed or recurring figure must never be shown as a hardware purchase price.
- **Use the most specific term** that applies; reserve `other` for genuine gaps.
- **Same term, both folders:** a service's `billing_model` and the matching
  `pricing/` entry's `price_type` should use the same canonical term.

## Used by

- `templates/service-template.md` → `billing_model`
- `templates/pricing-template.md` → `price_type`
