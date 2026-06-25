# Products — canonical product knowledge

This folder holds **durable, curated product knowledge**: what a product is, who it
is for, how it is sold, and how it is installed and maintained. It covers the full
portfolio — telephony systems, routers, repeaters, DECT systems, phones, cameras,
switches, door systems, software, licenses, and future product classes.

This is **knowledge, not pricing**. Prices, discounts, and quotes are operational
and churny; they belong in a separate pricing structure (future) and must never be
embedded here.

## Rules for product files

- **Use the template.** Every product file is a copy of
  [`../templates/product-template.md`](../templates/product-template.md). Do not
  invent a different structure.
- **Separate the three audiences.** Each file must keep **Customer View**,
  **Sales View**, and **Technician View** as distinct sections — never blend them.
- **No embedded prices.** Do not write prices, discounts, or quotes. The
  *Pricing References* section is a pointer only; pricing lives in its own
  (separate, future) structure.
- **Reference, don't copy operational config.** Firmware versions, ports, IPs,
  env vars, and COMtrexx parameters are referenced via their single source of
  truth — never restated here, so this knowledge can never drift.
- **Curated and reviewed.** Set `owner`, bump `last_reviewed`, and promote to
  `status: active` only after human review.

## Adding a product

1. Copy `../templates/product-template.md` into this folder.
2. Rename it to the product `id` (kebab-case, e.g. `auerswald-comfortel-d-200.md`).
3. Fill in the frontmatter (`category`, `vendor`, `model`, `lifecycle`, plus the
   shared `id` / `type: product` / `owner` / `status` / `last_reviewed` / `sources`).
4. Keep prices out and operational facts as references.
5. Have it reviewed; set `status: active` and `last_reviewed`.

> No product files exist yet — this is a placeholder so the taxonomy is in place.
