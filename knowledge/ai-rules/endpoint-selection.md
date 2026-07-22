---
id: endpoint-selection
type: ai-rule
owner: unassigned
status: active
last_reviewed: 2026-07-23
sources:
  - "Teleprofi candidate interview-answer document (confirmed by Renato, 2026-07-23)"
---

# Endpoint Selection — decision rules

> This file defines **how** OrganAIzer chooses between desk phone, headset,
> softphone, and DECT for a given need. It is decision policy, **not**
> product facts — device facts live in
> [`../products/`](../products/) (`comfortel-d210.md`, `comfortel-d400.md`,
> `comfortel-d600.md`, `comfortel-m710.md`, `comfortel-m730.md`,
> `ws-500s.md`, `gigaset-n670.md`). This mirrors the existing
> [`provider-selection.md`](./provider-selection.md) pattern: cross-product
> "how to choose" logic belongs here, not in any single product's fact
> file, per `knowledge/IMPORT_GUIDE.md`'s rule against putting recommendation
> logic in fact files.
>
> Confirmed by Renato, 2026-07-23. It is not wired into any AI prompt —
> doing so is **(future)** and out of scope here, same as
> `provider-selection.md`. This file changes no application behavior.

## Selection guidance

> From the interview draft's Interview 3 "TELEFONE" section.

- **Tischtelefon (desk phone):** fester Arbeitsplatz, häufige Gespräche,
  zentrale Funktionen, klare Bedienung, gute Sprachqualität, und dort, wo
  physische Tasten wichtig sind.
- **Headset:** hohes Gesprächsaufkommen, gleichzeitige Bildschirmarbeit,
  Service- oder Vertriebsarbeitsplätze, ergonomische Anforderungen.
- **Softphone:** Homeoffice, mobile Mitarbeiter, wechselnde Arbeitsplätze,
  Laptop-zentrierte Arbeit, wenn physische Telefonhardware nicht
  erforderlich ist.
- **DECT:** Bewegung innerhalb eines Gebäudes oder Geländes (Lager,
  Werkstatt, Hotel, Praxis, Gastronomie, Produktion). Vorher müssen
  Flächen, Materialien, Reichweite, Roaming und Basisstationen geprüft
  werden — see `site-visit-checklist.md`.

## When endpoints alone are the answer, not a new PBX

> From the supplementary "PRODUKTAUSWAHL" section of the interview draft
> ("Wann empfehlen Sie nur Telefone oder Headsets und keine neue
> Telefonanlage?").

Recommend endpoints only (no new telephone system) when the existing PBX is
still technically adequate and the actual problem is one of:

- Ergonomie (ergonomics).
- Mobilität (mobility).
- Sprachqualität (voice quality).
- Endgerätebedienung (device usability).
- Einzelne Arbeitsplätze (individual workstations, not the whole system).
- Fehlende Headset-Unterstützung (missing headset support).

A new PBX is not justified when the core platform continues to reliably
meet the actual need — this is the same principle
[`../business-philosophy/product-selection-philosophy.md`](../business-philosophy/product-selection-philosophy.md)
already states for products generally, applied specifically to endpoints.

## Guardrails

- This file states selection guidance only; it does not restate device
  specs — for any technical claim, defer to the cited product file.
- No prices, firmware versions, or capacity numbers are stated or implied
  here.
- Do not treat "DECT is suitable" as confirmed without the site-visit
  checks noted above.

## Related

- [`../products/comfortel-d210.md`](../products/comfortel-d210.md),
  [`comfortel-d400.md`](../products/comfortel-d400.md),
  [`comfortel-d600.md`](../products/comfortel-d600.md) (desk phones)
- [`../products/comfortel-m710.md`](../products/comfortel-m710.md),
  [`comfortel-m730.md`](../products/comfortel-m730.md),
  [`ws-500s.md`](../products/ws-500s.md),
  [`gigaset-n670.md`](../products/gigaset-n670.md) (DECT)
- [`../procedures/site-visit-checklist.md`](../procedures/site-visit-checklist.md)
- [`../business-philosophy/product-selection-philosophy.md`](../business-philosophy/product-selection-philosophy.md)

## Open Questions

- Whether any of the four categories above have Teleprofi-specific
  thresholds or exceptions not yet captured here.
