# Templates — index

The canonical templates every knowledge entry copies from. Copy a template into
its target folder, rename to the entry `id` (kebab-case), fill in the frontmatter,
and follow the section structure.

| Template | For folder | `type` | Purpose |
|---|---|---|---|
| [`base.md`](./base.md) | (any) | — | The shared frontmatter + minimal body all entries build on. |
| [`product-template.md`](./product-template.md) | `products/` | `product` | Durable product knowledge (Customer/Sales/Technician views). No pricing. |
| [`pricing-template.md`](./pricing-template.md) | `pricing/` | `pricing` | Sourced, dated commercial pricing (hardware, license, service, rental, leasing, factoring, bundle). |
| [`provider-template.md`](./provider-template.md) | `providers/` | `provider` | Connectivity providers (SIP, fiber, DSL, carriers). Cite official sources. |
| [`service-template.md`](./service-template.md) | `services/` | `service` | Business offerings (installation, support, surveys, contracts). Links to procedures for the "how". |
| [`solution-template.md`](./solution-template.md) | `solutions/` | `solution` | The composition layer: products + services + providers + pricing + install + AI rules. References, never duplicates. |
| [`customer-scenario-template.md`](./customer-scenario-template.md) | `customer-scenarios/` | `customer-scenario` | Reusable customer **archetypes** (industry/use-case patterns). References solutions/products/services. |

Folders that use the shared `base.md` (no class-specific template): `business-philosophy/`.

Folders with an in-folder `_template.md` (these are not duplicated here):

| Folder | Template |
|---|---|
| `companies/` | `companies/_template.md` |
| `people/` | `people/_template.md` |
| `customers/` | `customers/_template.md` |
| `infrastructure/` | `infrastructure/_template.md` |
| `procedures/` | `procedures/_template.md` |
| `decisions/` | `decisions/_template.md` |
| `projects/` | `projects/_template.md` |

> Two template homes exist by history: the original folders keep an in-folder
> `_template.md`; newer knowledge classes (products, pricing, providers, services,
> solutions) keep their template here in `templates/`. The taxonomy table in
> [`../README.md`](../README.md) is the source of truth for which template each
> folder uses.

## Shared frontmatter

Every template starts from the shared schema in `base.md` (`id`, `type`, `owner`,
`status`, `last_reviewed`, `sources`) and adds class-specific fields. See
[`../README.md`](../README.md) for field conventions and the one-source-of-truth
rule.

## Knowledge History & Knowledge Confidence

**Major knowledge entries** (products, services, solutions, customer-scenarios) are
expected to carry two standard sections, included in their templates:

- **Knowledge History** — a versioned changelog (`Version | Date | Change | Source`)
  so an entry's evolution is auditable, paired with the `knowledge_version`
  frontmatter field.
- **Knowledge Confidence** — a per-area rating (`Area | Confidence | Reason`) using
  **high | medium | low | needs-confirmation**. Low / needs-confirmation areas
  should map to an Open Question or a *Knowledge Needed* item.

See [`../IMPORT_GUIDE.md`](../IMPORT_GUIDE.md) for how to maintain them.
