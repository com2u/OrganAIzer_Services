# OrganAIzer Canonical Knowledge Repository

A **markdown-first, version-controlled** home for durable, curated, human-reviewed,
AI-readable knowledge about the company, people, customers, projects,
infrastructure, procedures, and decisions.

This repository is **knowledge**, not data. It is intentionally:

- **Markdown only** — no database, no embeddings, no RAG, no application code.
- **Curated** — every entry is human-reviewed and owned, not auto-generated.
- **Authoritative-by-reference** — operational facts (ports, IPs, env vars,
  COMtrexx values) are *linked* to their single source of truth, never copied.

> Future wiring (e.g. exposing this tree to the Executive Agent or indexing it for
> search) is **(future)** and out of scope here. Today this is plain markdown.

---

## Canonical vs operational (the boundary)

| | Canonical knowledge (this repo) | Operational data (`data/`, untracked) |
|---|---|---|
| Examples | company profiles, ADRs, runbooks, project/people records | uploaded documents, RAG/KB JSON, transcripts, call logs, generated media |
| Lifecycle | durable, curated, reviewed | churny, derived, ephemeral, retention-governed |
| In git? | yes | no |
| PII | stable, non-sensitive only | may contain PII — never promote raw PII here |

When a durable truth emerges from operational data, **promote** it here (curated and
reviewed); the operational copy stays subject to cleanup/retention.

---

## Repository guides

- [`BUILD_ORDER.md`](./BUILD_ORDER.md) — the order to import knowledge classes.
- [`IMPORT_GUIDE.md`](./IMPORT_GUIDE.md) — how to author and review an entry.
- [`ROADMAP.md`](./ROADMAP.md) — the remaining population phases.
- [`BILLING_VOCABULARY.md`](./BILLING_VOCABULARY.md) — canonical billing terms
  shared by services and pricing.
- [`templates/README.md`](./templates/README.md) — the templates index.

---

## Folder taxonomy

| Folder | Holds | Template |
|---|---|---|
| `companies/` | company identity, services, products, hours, tone | `companies/_template.md` |
| `people/` | team members & roles (internal, non-sensitive) | `people/_template.md` |
| `customers/` | stable, non-sensitive customer/account profiles (actual accounts) | `customers/_template.md` |
| `customer-scenarios/` | reusable customer **archetypes** (industry/use-case patterns) | `templates/customer-scenario-template.md` |
| `products/` | durable product knowledge (no pricing) | `templates/product-template.md` |
| `pricing/` | commercial pricing knowledge (sourced, dated) | `templates/pricing-template.md` |
| `providers/` | connectivity providers (SIP, fiber, DSL, carriers) | `templates/provider-template.md` |
| `services/` | business offerings (installation, support, surveys, contracts) | `templates/service-template.md` |
| `solutions/` | what customers buy: products + services + providers composed | `templates/solution-template.md` |
| `business-philosophy/` | reusable Teleprofi operating principles & policies | `templates/base.md` |
| `ai-rules/` | AI decision logic (how to choose), not facts | — |
| `projects/` | active workstreams: goal, scope, status, owners | `projects/_template.md` |
| `infrastructure/` | components **by reference** to authoritative sources | `infrastructure/_template.md` |
| `procedures/` | runbooks / step-by-step operational procedures | `procedures/_template.md` |
| `decisions/` | Architecture Decision Records (ADRs) | `decisions/_template.md` |
| `templates/` | the canonical templates all entries copy from (see `templates/README.md`) | `templates/base.md` |

---

## Frontmatter schema (every entry)

Every markdown entry starts with this YAML frontmatter:

```yaml
---
id:            # stable, kebab-case identifier (decisions use a numeric prefix, e.g. 0001-...)
type:          # company | person | customer | customer-scenario | product | pricing | provider | service | solution | philosophy | project | infrastructure | procedure | decision
owner:         # role or person responsible for keeping this entry accurate
status:        # draft | active | deprecated  (decisions: proposed | accepted | superseded)
last_reviewed: # YYYY-MM-DD of the last human review
sources:       # list of authoritative sources (file paths, URLs, docs) the facts derive from
---
```

### Field conventions

- **id** — stable and unique within its folder; kebab-case (`teleprofi-fulda`).
  Decisions are numbered: `0001-deflect-not-bridge`.
- **type** — must match the folder.
- **owner** — a named role/person; "unassigned" is allowed for drafts.
- **status** — `draft` until reviewed, then `active`; `deprecated` when retired.
  Decisions use `proposed` → `accepted` → `superseded`.
- **last_reviewed** — bump on every meaningful review; stale entries are defects.
- **sources** — a YAML list. For any operational fact, point to its single source
  of truth (e.g. `docker-compose.yml`, `backend/voice/config.py`,
  `backend/voice/freeswitch/README.md`). Empty list (`[]`) only for self-contained
  knowledge.

---

## One source of truth (do not duplicate)

Some facts already have an authoritative home. Entries here **reference** them and
must not restate the values (to avoid drift):

- **Ports / container topology** → `docker-compose.yml`
- **Env vars** → `backend/voice/config.py` + `backend/.env.example`
- **COMtrexx / IPs / orbits (`003010`, `778`, `779`)** → `backend/voice/config.py`
  + `backend/voice/freeswitch/README.md`
- **CI gate / test runner** → `pipeline-guardian` skill

See `docs/PROJECT_OPERATING_SYSTEM.md` for the full single-source-of-truth model.

---

## Products are knowledge, not pricing

`products/` holds **canonical product knowledge** — what a product is, who it is
for, and how it is sold, installed, and maintained — across the whole portfolio
(telephony, routers, repeaters, DECT, phones, cameras, switches, door systems,
software, licenses, and future classes). Every product file is a copy of
`templates/product-template.md` and keeps **Customer View**, **Sales View**, and
**Technician View** as distinct sections.

**Pricing must never be embedded in a product profile.** Prices, discounts, and
quotes live in `pricing/`, not here. Product files carry a *Pricing References*
pointer that links to the relevant `pricing/` entries — they never restate
figures. Like all entries, products **reference** operational config (firmware,
ports, COMtrexx values) at its single source of truth rather than copying it.

See `products/README.md` for the folder's rules.

---

## Pricing is commercial knowledge (separate from products)

`pricing/` holds **commercial pricing knowledge** — net/gross figures, VAT,
one-time vs. recurring amounts, and validity windows for hardware, licenses,
services, rentals, leasing, factoring calculations, and bundles. Every entry is a
copy of `templates/pricing-template.md`.

Pricing **changes faster than product knowledge**: it is dated, must cite a
`source_document`, and offer-derived figures are historical examples unless
confirmed current. Leasing/factoring/rental prices are marked separately from
purchase prices, and customer-specific discounts are never recorded as list
price. **Product files must reference pricing entries, never embed prices.**

See `pricing/README.md` for the folder's rules. Indexing or exposing this
knowledge for search is **(future)** — no database/RAG/embeddings work is built.

---

## Providers are connectivity knowledge, not products — and not AI rules

`providers/` holds **connectivity providers** — the Internet, SIP, fiber, DSL and
telephony carriers (Telekom, Vodafone, o2, …) that products depend on. Providers
are **not** products: a COMtrexx PBX is a product; the SIP-Trunk it registers to
is a provider service. Every entry is a copy of `templates/provider-template.md`.

Provider files contain **business knowledge** (market position, customer fit,
sales guidance) and **technical knowledge** (SIP/fiber/DSL/router/PBX
compatibility, configuration). Every technical claim **cites an official vendor
source**; repository evidence comes first, public vendor docs fill gaps, and no
performance comparisons are invented.

Provider files do **not** contain AI decision rules. **Recommendation logic — how
OrganAIzer chooses a provider — belongs in `ai-rules/`** (see
`ai-rules/provider-selection.md`), keeping facts and decision policy cleanly
separated. The `ai-rules/` files describe intended policy only; wiring them into
the Executive Agent or any AI prompt is **(future)** and changes no application
behavior today.

---

## Services are business offerings, not procedures

`services/` holds **business offerings** — what a customer can buy as a service:
*fiber installation*, *rack cleanup*, *remote support*, a *maintenance contract*,
a *Wi-Fi survey*. Every entry is a copy of `templates/service-template.md`.

A **service is not a procedure.** A service describes the *offering* (what is
sold, to whom, what it includes, why); a `procedures/` runbook describes *how the
work is performed*. "Wi-Fi survey" is a service; "how to run a Wi-Fi survey" is a
procedure. Service files **reference** the procedures that deliver them, are priced
via `pricing/`, and are composed into `solutions/`. See `services/README.md`.

---

## Business philosophy is reusable Teleprofi operating knowledge

`business-philosophy/` holds **cross-cutting Teleprofi operating principles and
policies** — how Teleprofi selects products, plans for growth, installs systems,
handles firmware, maintains systems, and prefers providers. These are written
**once** and **referenced** by products/services/solutions, so a principle is never
re-explained (and never drifts) across many files. A product links to
`business-philosophy/product-selection-philosophy.md` rather than restating the
reasoning.

Business philosophy is the durable **why / principle**; `ai-rules/` is the concrete
**decision logic** that applies it. Product-specific thresholds live in the product
entry; the underlying principle lives in `business-philosophy/`. See
`business-philosophy/README.md`.

---

## Reusable archetypes vs. actual records

Four folders are easy to confuse — keep the **reusable pattern** separate from the
**actual instance**:

| Folder | Kind | Holds |
|---|---|---|
| `customer-scenarios/` | **reusable archetype** | Industry/use-case *patterns* (e.g. "dentist office", "hotel") — typical size, problems, infrastructure, and what Teleprofi usually recommends. Not a real customer. |
| `customers/` | **actual record** | Real, stable, non-sensitive customer/account profiles. |
| `solutions/` | **reusable package** | Repeatable product+service+provider compositions (e.g. "small-office telephony"). |
| `projects/` | **actual workstream** | Specific, time-bound customer engagements. |

Rule of thumb: a **scenario** describes a *type* of customer; a **customer** is one
real account. A **solution** is a *reusable* package; a **project** is one real
engagement that may *apply* a solution to a customer (often matching a scenario).

---

## Solutions are what customers buy (the composition layer)

Customers buy **solutions, not products**. `solutions/` is the composition layer:
each entry combines **products + services + providers + pricing references +
installation guidance + AI recommendation rules** into one coherent answer to a
business need. Every entry is a copy of `templates/solution-template.md`.

Solutions **never duplicate** product or pricing descriptions — they **reference**
`products/`, `pricing/`, `providers/`, `procedures/`, and `ai-rules/`, and they
explain **why** each part is selected for the customer's need. A COMtrexx PBX is a
product; "small-office telephony" is a solution that references it. See
`solutions/README.md` for the folder's rules.

**Solutions vs. projects:** a solution is **reusable knowledge** (a repeatable
answer to a common need); a `project` is an **actual customer engagement** (a
specific, time-bound piece of work). A project may apply a solution — the solution
stays generic, the project records what actually happened.

---

## Adding an entry

1. Copy `templates/base.md` (or the folder's `_template.md`) to a new file.
2. Fill in the frontmatter (`id`, `type`, `owner`, `status`, `last_reviewed`,
   `sources`).
3. Keep operational facts as references, not copies.
4. Keep PII out — non-sensitive, stable knowledge only.
5. Have it reviewed; set `status: active` and `last_reviewed`.

> Do not move existing files into this tree as part of scaffolding. The voice AI's
> client knowledge (`backend/voice/knowledge/teleprofi_fulda.md`) is loaded by code
> from its current path; any consolidation is a separate, deliberate decision.
