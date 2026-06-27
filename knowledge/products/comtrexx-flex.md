---
id: comtrexx-flex
type: product
owner: unassigned
status: draft
knowledge_version: 0.2   # v0.1 + official-doc firm-ups (form factor, licensing, capabilities); Teleprofi operational gaps remain interview questions
last_reviewed: 2026-06-25
sources:
  - backend/voice/knowledge/teleprofi_fulda.md          # primary: Teleprofi business knowledge
  - Teleprofi operational knowledge (Renato, 2026-06-25) # primary
  - knowledge/products/comtrexx-family.md                # family-level decision logic (not duplicated)
  - knowledge/products/comtrexx-next.md                  # the smaller sibling
  - https://www.auerswald.de/de/produkt/comtrexx-flex/reseller   # supporting: official
category: telephony
vendor: Auerswald
model: COMtrexx Flex
lifecycle: current
---

# Auerswald COMtrexx Flex — Teleprofi product knowledge

> Captures **Teleprofi's** knowledge of when, why and how it sells, installs and
> supports COMtrexx Flex. Family-level reasoning (when to choose COMtrexx at all,
> and the canonical Next-vs-Flex decision) lives in
> [`comtrexx-family.md`](./comtrexx-family.md) and is **referenced, not repeated**;
> reusable principles live in `business-philosophy/`. This entry documents only what
> is **unique to Flex**.
>
> **Knowledge maturity: v0.2 (draft).** v0.1 (family + philosophy + official) plus
> official-documentation firm-ups (form factor, licensing, Flex capabilities).
> Flex-specific **Teleprofi operational** detail is still captured as precise
> questions under **[Teleprofi Knowledge Needed](#teleprofi-knowledge-needed)**.

# Executive Summary

**What is this product?**
COMtrexx Flex is the **scalable, expandable** member of the Auerswald COMtrexx
family — a desktop appliance (with an **optional 19″ rack** bracket) that grows to
**up to 250 users** (Auerswald). It runs the same COMtrexx platform as Next but is
built for larger, more demanding, longer-life installations.

**Why does Teleprofi sell it?**
Because it is **the better long-term platform**: greater expandability, more
flexible hardware expansion (including analog modules), advanced telephony, and
suitability for larger installations — the right choice when a customer expects to
grow or has more complex requirements (Teleprofi operational knowledge;
[[product-selection-philosophy]], [[growth-planning-philosophy]]).

**Who is it for?**
Businesses **around 7–8 users or more**, or any size with growth expected or more
advanced telephony needs (departments, call groups, routing, integrations, analog,
stronger expansion). The full "which COMtrexx" logic is in
[`comtrexx-family.md`](./comtrexx-family.md).

# Teleprofi Recommendation

**Why Teleprofi recommends Flex / when it is better than Next.** Flex is preferred
when the business case points beyond Next's small-office sweet spot. In short
(canonical list in [`comtrexx-family.md`](./comtrexx-family.md)):

- **~7–8 active users or more**, or growth expected.
- More **departments**, internal **call groups**, or advanced **call routing**.
- Additional **software integration** / multiple product lines.
- **Analog devices** that must stay analog (Flex takes analog modules; Next has none).
- More advanced **door communication** / future door expansion.
- Stronger **expandability** and a longer **investment lifetime**.

**Next may be cheaper — but price alone must not decide.** Choosing Next purely on
today's budget risks replacing the PBX in a few years
([[product-selection-philosophy]]).

**Future-proofing.** Flex protects the investment: a customer near the boundary
grows on Flex via licences/modules instead of a forklift PBX swap off Next.

**Leasing can make Flex the right choice.** Where budget is the only reason a
customer leans Next, **leasing (Grenke) can make Flex affordable** — technical fit
first, financing supports it ([[financing-philosophy]]).

# Typical Teleprofi Customer

- **Company size:** roughly **7–8 users and upward** (up to 250 technically;
  Teleprofi's typical Flex band to be confirmed — see Knowledge Needed Q1).
- **Profile:** businesses with departments / call groups / routing needs, analog
  equipment to retain, growth plans, or multiple sites — i.e. beyond a simple small
  office.
- **Typical industries:** the larger / more structured end of Teleprofi's customer
  base (`teleprofi_fulda.md`); the specific Flex-leaning industries are open
  (Knowledge Needed Q2).

# Sales Qualification

Qualification is the same reusable flow as for any PBX (the canonical checklist
sits in `comtrexx-next.md` and will move to a `business-philosophy/` sales-
qualification standard). For Flex, the **decision-tipping** answers are: headcount
vs. ~7–8, growth plans, number of departments/groups, routing complexity, analog/
fax needs, door-communication scope, and integrations. These map directly to the
Flex signals above.

# Typical Teleprofi Solution

A typical Flex solution (Flex-specific deltas vs. the Next bundle in
`comtrexx-next.md`):

| Component | Why it's normally included |
|---|---|
| **COMtrexx Flex** | The scalable PBX — desktop or optional 19″ rack, grows to 250 users (Auerswald). |
| **Analog module(s)** (COMpact 4FXS) | Where analog devices/fax must be retained — up to 12 analog ports (Auerswald). *(Which installs are typical: Knowledge Needed Q3.)* |
| **Endpoints** | Auerswald COMfortel desk + DECT; typically more endpoints / groups than a Next site (family entry). |
| **Provider SIP trunk** (often **Telekom CompanyFlex**) | Preferred for new business installs ([[provider-preference-philosophy]]). |
| **AVM FRITZ!Box** | Internet/router by access technology; trunk registered in the PBX ([[provider-preference-philosophy]]). |
| **Installation / migration / maintenance services** | As per `services/` (see Next bundle). |
| **Leasing (Grenke)** where it makes Flex attainable | [[financing-philosophy]]. |

Pricing lives in `pricing/`. See `solutions/growing-business-telephony.md` for the
composed solution.

# Teleprofi Installation Process

Same standard delivery workflow as the family ([[installation-philosophy]]) —
preconfigure → bench-test → install → configure → test → train → document →
support. **Flex-specific deltas:** it can be **19″ rack-mounted** (optional bracket)
or sit as a desktop appliance, and **analog modules (COMpact 4FXS — up to 3 slots /
12 ports)** or the **optional GbE-NET** second-Ethernet module may need fitting and
per-port configuration. Exact Flex preconfiguration / bench-test specifics are
hands-on technician detail — see Interview Backlog (Patrick).

# Teleprofi Operational Experience

> Teleprofi's own observations, separated from official documentation. Most
> Flex-specific operational lore is not yet captured — see Knowledge Needed.

- **Shared with the family:** firmware handled per [[firmware-policy]] (only
  proven-stable; current COMtrexx version list lives there); maintenance billed as a
  service ([[maintenance-philosophy]]); typical SIP-registration / provisioning /
  firmware support patterns (`teleprofi_fulda.md` §8).
- **Flex-specific patterns** (common mistakes, regret cases, advanced-feature
  gotchas): open — Knowledge Needed Q4–Q6.

# Migration

Delivered as a migration service (`services/telephone-system-migration.md`) using
[[installation-philosophy]]. **Flex-specific:** unlike Next, Flex can **retain
analog devices** via COMpact 4FXS modules, so analog/fax-heavy migrations off ISDN
or legacy PBXs that would force IP-only on Next can stay partly analog on Flex. It
is also the **target** of a Next→Flex upgrade when a customer outgrows Next (that
decision is family-level — [`comtrexx-family.md`](./comtrexx-family.md)).

# Maintenance

Firmware updates and maintenance as a billed professional service
([[maintenance-philosophy]]); firmware approach and the stable/avoid version list in
[[firmware-policy]]. Flex's expansion modules (analog 4FXS, optional GbE-NET) add
some physical surface vs. Next; specifics are open (Knowledge Needed Q5).

# Official Product Information

> Concise, referenced — not a rewrite of the manual. See the Auerswald COMtrexx
> Flex page (in `sources`) for the full specification.

- **Capacity:** up to **250 users**; up to **500 registered devices** (~5 per user);
  up to **48 simultaneous calls** (Auerswald).
- **Form factor:** **desktop appliance** (~325 × 88 × 240 mm) with an **optional 19″
  rack** mounting bracket — not rack-only (Auerswald).
- **Analog:** expandable with **COMpact 4FXS** modules — **4 ports per module, up to
  3 module slots = max 12 analog ports** (Auerswald).
- **Networking:** optional **GbE-NET** module adds a second Gigabit Ethernet port
  (Auerswald).
- **Licensing:** base package includes **10 floating COMtrexx user licences**;
  scales **up to 250** by adding further floating licences (a floating licence is
  shared across users as long as active users ≤ total licences). This **scales up**,
  in contrast to Next's fixed, non-stacking licence blocks (Auerswald).
- **Platform / capabilities:** same COMtrexx feature set; native Auerswald COMfortel
  phones + DECT; standards-based SIP. Official Flex capabilities include **integrated
  conferencing (up to 10 rooms × 10 participants)**, **zero-touch provisioning** for
  D-series phones, and **COMfortel SoftPhone 2** apps. *(Which capabilities are
  Flex-only vs. shared with Next is still open — Open Questions.)* Provider
  encryption specifics → `providers/`.

# AI Recommendation Notes

> Business reasoning only — not a product description, not an AI prompt. The full
> Next-vs-Flex decision is family-level ([`comtrexx-family.md`](./comtrexx-family.md));
> this note states the **Flex side**.

**Lean Flex** when growth or complexity signals are present: ~7–8+ users, expected
growth, multiple departments/call groups, advanced routing, software integration,
analog devices to retain, or advanced door communication. Business logic: Flex is
the scalable, longer-life platform — recommending it early avoids a forced PBX
replacement and protects the customer's investment ([[growth-planning-philosophy]]).
**Never reject Flex on price alone** — if budget is the blocker, evaluate leasing
([[financing-philosophy]]) before undersizing to Next. Technical fit is decided
first; financing supports it.

**Conversation example.** Customer: *"We currently have five employees but expect to
double within two years."* → Five today would fit Next, but doubling to ~10 crosses
the ~7–8 evaluation point within the system's life. Size to **future** needs
([[growth-planning-philosophy]]) → recommend **Flex despite the higher initial
investment**; it avoids replacing the PBX in ~2 years and scales via floating
licences/modules. If the upfront cost is the blocker, **leasing (Grenke)** makes it
manageable ([[financing-philosophy]]). Contrasting pair in
[`comtrexx-family.md`](./comtrexx-family.md).

# Knowledge Status

**This entry is v0.1.** It is grounded in the family decision logic, official
Auerswald data, and existing Teleprofi philosophy. Reaching higher maturity needs
Flex-specific operational input (below). Reusable reasoning is referenced, not
repeated.

## Interview Backlog (Patrick / technician)

- **Flex preconfiguration / bench-test:** what differs from Next (rack, modules).
- **Analog modules:** typical COMpact 4FXS fitting/config gotchas.
- **Door communication:** Flex IP door-station capacity and typical setups.
- **Advanced features:** which COMtrexx features are used mainly on Flex sites
  (groups, routing, integrations) and their install/config caveats.

## Teleprofi Knowledge Needed (Renato)

1. What is Teleprofi's **typical Flex customer size band** (and the usual upper end
   you actually install, vs. the 250 technical max)?
2. Which **industries / situations** specifically lean Flex over Next?
3. How often do Flex installs include **analog (4FXS) modules**, and for what
   (fax, door, alarm, legacy handsets)?
4. What is the **most common mistake** when selecting or deploying Flex?
5. Any **Flex-specific maintenance** considerations beyond the family norm?
6. A concrete case where **Flex clearly paid off** (growth/feature it enabled that
   Next could not) — to make the recommendation vivid.
7. How often does **leasing (Grenke)** decide a Flex sale in practice?

# Related Products

- [`comtrexx-family.md`](./comtrexx-family.md) — **family-level** logic: when to
  choose COMtrexx, and the canonical Next-vs-Flex decision.
- [`comtrexx-next.md`](./comtrexx-next.md) — the entry-level sibling for small offices.
- COMfortel D-series desk phones; COMfortel M-710/M-730 DECT; WS-500S/M DECT bases.

# Related Philosophy

- [`../business-philosophy/product-selection-philosophy.md`](../business-philosophy/product-selection-philosophy.md)
- [`../business-philosophy/growth-planning-philosophy.md`](../business-philosophy/growth-planning-philosophy.md)
- [`../business-philosophy/financing-philosophy.md`](../business-philosophy/financing-philosophy.md)
- [`../business-philosophy/installation-philosophy.md`](../business-philosophy/installation-philosophy.md)
- [`../business-philosophy/firmware-policy.md`](../business-philosophy/firmware-policy.md)
- [`../business-philosophy/maintenance-philosophy.md`](../business-philosophy/maintenance-philosophy.md)
- [`../business-philosophy/provider-preference-philosophy.md`](../business-philosophy/provider-preference-philosophy.md)

# Related Providers

- [`../providers/telekom.md`](../providers/telekom.md) (preferred for new business installs)
- [`../providers/vodafone.md`](../providers/vodafone.md)
- [`../providers/o2.md`](../providers/o2.md)

# Related Services

- `../services/telephone-system-installation.md`
- `../services/telephone-system-migration.md`
- `../services/maintenance-contract.md`
- `../services/remote-support.md`

# Related Solutions

- `../solutions/growing-business-telephony.md`
- `../solutions/office-relocation.md`

# Related Procedures

- `../procedures/comtrexx-registration-troubleshooting.md`
- `../procedures/voice-escalation-validation.md`

# Related ADRs

- `../decisions/0001-deflect-not-bridge-for-orbit-escalation.md`
- `../decisions/0007-comtrexx-validation-is-manual.md`

# Related AI Rules

- [`../ai-rules/provider-selection.md`](../ai-rules/provider-selection.md)
- Product-selection (Next vs. Flex) — *future* `ai-rules/` entry referencing
  `comtrexx-family.md` and the philosophy files.

# Open Questions (official facts to confirm)

- Flex **IP door-station** capacity and other per-category device limits — **not
  stated** on the official reseller page; confirm from Auerswald technical data.
- Which COMtrexx **capabilities are Flex-only** vs. shared with Next (e.g.
  conferencing, zero-touch, SoftPhone 2) — the "must be Flex" list (also family Q3).
- Exact floating-licence **increments** above the 10-licence base.
- Per-provider certification / cipher-suite support for Flex (CompanyFlex/Vodafone/o2).

# Knowledge History

| Version | Date | Change | Source |
|---|---|---|---|
| 0.1 | 2026-06-25 | Initial Flex entry: Flex-specific positioning, capacity/analog/rack specifics, financing angle; family logic referenced not duplicated; operational gaps framed as questions | family entry + official Auerswald + Teleprofi philosophy |
| 0.2 | 2026-06-25 | Official-doc firm-ups: corrected form factor (desktop + optional rack, not rack-only), 4FXS slot detail, floating-licence scaling, added capabilities (conferencing, zero-touch, SoftPhone 2, GbE-NET); door-station capacity confirmed not officially stated | official Auerswald COMtrexx Flex page |
| 0.2 | 2026-06-25 | Added AI conversation example (5-employees-doubling → Flex) | Teleprofi (Renato) |

# Knowledge Confidence

| Area | Confidence | Reason |
|---|---|---|
| When Flex beats Next (signals) | high | family entry + Teleprofi (Renato) |
| Future-proofing / financing rationale | high | reusable philosophy ([[financing-philosophy]]) |
| Capacity / analog / form factor / licensing specs | high | confirmed on official Auerswald Flex page |
| Flex capabilities (conferencing, zero-touch, SoftPhone 2) | medium | official, but Flex-vs-Next exclusivity unconfirmed |
| Door-station capacity | needs-confirmation | not stated officially (Open Questions) |
| Typical Teleprofi Flex customer band | needs-confirmation | not yet captured — Q1 |
| Typical bundle (analog module frequency) | needs-confirmation | not yet captured — Q3 |
| Flex-specific install/maintenance detail | needs-confirmation | hands-on — Patrick backlog |
| Common mistakes / regret/payoff cases | needs-confirmation | not yet captured — Q4, Q6 |
| Licence scaling behaviour | needs-confirmation | official detail to confirm (Open Questions) |
