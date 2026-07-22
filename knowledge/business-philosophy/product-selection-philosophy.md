---
id: product-selection-philosophy
type: philosophy
owner: unassigned
status: active
last_reviewed: 2026-06-25
sources:
  - backend/voice/knowledge/teleprofi_fulda.md
  - Teleprofi operational knowledge (Renato, 2026-06-25)
---

# Teleprofi Product Selection Philosophy

> Reusable principle. Products reference this instead of restating it. See also
> [[growth-planning-philosophy]] and [[installation-philosophy]].

## Principle

Teleprofi does **not** recommend a product simply because it is cheaper, or simply
because it satisfies the customer's requirements **today**. The objective is to
avoid having to replace the system after only a few years.

A recommendation is made only after evaluating:

- **Current customer requirements** (what they need today, active users).
- **Expected growth** (more employees, departments, locations).
- **Desired lifetime of the investment** (how long it must last).
- **Expandability** (headroom to grow without replacement).
- **Future expansion plans** (devices, integrations, product lines).
- **Telephony complexity** (call groups, routing, software integration, analog needs).
- **Maintenance effort** (how sustainable it is to support long-term).
- **Future migration possibilities** (e.g. DSL→fiber without a forklift change).

Only then is the appropriate product recommended. The AI should recommend the
solution that best supports the customer's **business over the coming years**, not
only today's requirements.

## In practice

- **Always discuss the future**, not just the present: expected growth, future
  locations, additional employees, future telephony requirements.
- When growth is expected, **discuss the larger/long-term platform early** in the
  consultation — even if the customer could start smaller today.
- A lower entry price is a legitimate advantage, but it is **never the sole reason**
  to recommend a smaller system.

## Technical fit comes before financing

Decide in this order: **(1) technically correct solution → (2) commercially
appropriate solution → (3) financing model.** Financing *supports* the
recommendation and can make a better long-term system attainable (e.g. leasing a
larger PBX instead of undersizing to fit today's budget), but it must **never
determine the technical architecture**. See [[financing-philosophy]].

## Why

Replacing a PBX after a few years is costly and damages trust. Right-sizing for the
investment's intended lifetime protects the customer and the long-term relationship,
consistent with Teleprofi's reliable, non-salesy approach (`teleprofi_fulda.md`).

> Source: Teleprofi operational knowledge. Concrete per-product thresholds (e.g.
> the user count at which to move from one model to another) live in the product
> entry, which references this philosophy.

---

> Confirmed by Renato, 2026-07-23. Placed here per explicit instruction —
> no `ai-rules/` version created yet.

## When Teleprofi advises against a product

Criteria for explicitly advising a customer against a product:

- Das Produkt erfüllt die Kernanforderung nicht zuverlässig.
- Die Lösung würde nur mit dauerhaften Workarounds funktionieren.
- Die Infrastruktur des Kunden ist ungeeignet.
- Notwendige Sicherheitsupdates oder Herstellerunterstützung fehlen.
- Folgekosten stehen in keinem vernünftigen Verhältnis zum Nutzen.
- Die Lösung ist nicht sinnvoll erweiterbar.
- Der Kunde erwartet eine Funktion, die das Produkt in der Praxis nicht
  stabil leistet.
- Ein vorhandenes Gerät kann durch Konfiguration statt Austausch
  weitergenutzt werden.
- Ein anderes System passt besser zur bestehenden Umgebung.

An honest "davon würde ich Ihnen abraten" (I would advise against this) is
treated as one of the strongest trust signals in a consultation — see also
[`../companies/teleprofi-fulda.md`](../companies/teleprofi-fulda.md)'s
Trust section.

## Stated solution vs. actual need

Framing of the most common consultation mistake: mistaking the
solution a customer *names* for the need they actually *have*. Example: a
customer says "Ich brauche eine neue Telefonanlage," but the actual need
might be bessere Erreichbarkeit, stabileres WLAN, ein geeignetes Headset,
eine andere Rufverteilung, mobile Nutzung, Ersatz eines einzelnen Telefons,
ein Providerproblem, or eine neue Türsprechstelle. The task of a
consultation is to understand the underlying problem, not to immediately
confirm the customer's first product idea.

## Budget vs. future-proofing — a 3-tier framework

Framing for balancing budget against future-proofing, distinguish between:

1. **zwingend erforderlich** (strictly required now),
2. **sinnvoll für die nächsten Jahre** (worthwhile for the coming years),
3. **optional oder später nachrüstbar** (optional, or addable later).

The goal: a solution that is reliable at its core and allows growth at the
right points — avoiding both the cheapest dead end and expensive
"just in case" over-provisioning. "Zukunftssicher" (future-proof) should
never be used as an empty sales word — any price premium for future-proofing
must be justified by a concrete, named risk or benefit, not asserted on its
own.

Source: Teleprofi candidate interview-answer document (confirmed by Renato,
2026-07-23), Interview 1 "BERATUNG UND EMPFEHLUNGEN".
