# Build Order — recommended knowledge import sequence

Knowledge classes depend on each other. Importing them in dependency order means
every entry can reference the things it points to **before** they are needed, so
links resolve and review is straightforward. Import in this order:

| # | Layer | Folder | Why it comes here |
|---|---|---|---|
| 1 | **Products** | `products/` | Foundation. Everything else references products; they reference nothing downstream. |
| 2 | **Services** | `services/` | Business offerings that act on products; reference products + procedures. |
| 3 | **Providers** | `providers/` | Connectivity beneath products/services; independent facts, cited to vendors. |
| 4 | **Pricing** | `pricing/` | Prices for products, services, and provider offerings — needs 1–3 to exist to reference. |
| 5 | **Solutions** | `solutions/` | Composition layer: combines products + services + providers + pricing. Needs 1–4. |
| 6 | **Customer Types** | `customers/` | Archetypes that solutions target; clearer once solutions exist. |
| 7 | **AI Rules** | `ai-rules/` | Decision logic over the facts above; must reference settled facts, so it comes after them. |
| 8 | **Compatibility** | (compatibility knowledge) | Cross-references between products/providers; meaningful only once both are populated. |
| 9 | **Playbooks** | (playbook knowledge) | End-to-end operational/sales playbooks built on everything above. |

## Principles

- **Reference, don't duplicate.** Each layer links to the layers beneath it.
- **Lower layers are more durable;** higher layers (pricing, solutions, rules)
  change faster. Keep volatility high in the stack.
- **A layer is "ready" when its entries are reviewed** (`status: active`,
  `last_reviewed` set), not merely created.
- Layers 8–9 (Compatibility, Playbooks) are **planned** knowledge classes; their
  folder/template homes are defined when that phase begins.

See [`IMPORT_GUIDE.md`](./IMPORT_GUIDE.md) for how to author each entry and
[`ROADMAP.md`](./ROADMAP.md) for the concrete population phases.
