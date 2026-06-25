# Providers — connectivity knowledge

This folder holds **provider knowledge**: the Internet, SIP, fiber, DSL and
telephony connectivity that products depend on.

**Providers are NOT products.** Products (`products/`) are devices, software and
licenses. Providers describe the carriers and ISPs that supply the connectivity
*beneath* those products — SIP trunks, fiber/DSL access, All-IP telephony. A
COMtrexx PBX is a product; the Telekom CompanyFlex SIP-trunk it registers to is a
provider service.

## Business vs. technical vs. AI rules

Provider files carry **business knowledge** (market position, customer fit, sales
guidance) and **technical knowledge** (SIP/fiber/DSL/router/PBX compatibility,
configuration considerations). They do **not** contain AI decision rules.

**Recommendation logic — how OrganAIzer chooses a provider — lives in
`ai-rules/`, not here.** A provider file states facts; it never says "recommend
this provider." See [`../ai-rules/provider-selection.md`](../ai-rules/provider-selection.md).

## Rules for provider files

- **Use the template.** Every entry is a copy of
  [`../templates/provider-template.md`](../templates/provider-template.md).
- **Keep the three audiences separate** — Customer View, Sales View, Technician
  View — never blended.
- **Repository evidence first.** Ground claims in repository knowledge where it
  exists. Public vendor documentation may be used where repository information is
  absent.
- **Cite official vendor sources for every technical claim.** No invented specs,
  no invented performance comparisons.
- **No superlatives.** Do not claim a provider is "the best"; state objective
  positioning and Teleprofi's operational experience instead.
- **Reference, don't copy operational config** (ports, certs, COMtrexx values) at
  its single source of truth.
- **No AI decision rules here** — those belong in `ai-rules/`.

## Adding a provider

1. Copy `../templates/provider-template.md` into this folder.
2. Rename it to the provider `id` (kebab-case, e.g. `telekom.md`).
3. Fill in the frontmatter (`provider_type`, `country`, `supported_services`,
   plus the shared fields) and cite sources for technical claims.
4. Have it reviewed; set `status: active` and `last_reviewed`.

> A future indexing/search layer over this knowledge is **(future)** and not
> built — no database/RAG/embeddings work is implied here.
