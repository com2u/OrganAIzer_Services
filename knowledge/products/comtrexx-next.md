---
id: comtrexx-next
type: product
owner: unassigned
status: active
knowledge_version: 1.0   # Renato-answerable knowledge complete; remaining items are Patrick (technician) backlog
last_reviewed: 2026-06-25
sources:
  - backend/voice/knowledge/teleprofi_fulda.md          # primary: Teleprofi business knowledge
  - Teleprofi operational knowledge (Renato, 2026-06-25) # primary: this update
  - knowledge/infrastructure/comtrexx.md
  - https://www.auerswald.de/de/produkt/comtrexx-next/reseller          # supporting: official
  - https://docs.auerswald.de/COMtrexx/Help_V09_de/Help/technische_daten_next_m_concept.html
category: telephony
vendor: Auerswald
model: COMtrexx Next
lifecycle: current
---

# Auerswald COMtrexx Next — Teleprofi product knowledge

> Captures **Teleprofi's** knowledge of when, why and how it sells, installs and
> supports COMtrexx Next. Official Auerswald information is supporting evidence,
> referenced rather than reproduced.
>
> **Knowledge maturity: v1.0.** Self-sufficient for a new Teleprofi technician:
> reading only this entry conveys when to recommend Next (and when not), how
> Teleprofi deploys it, the typical customer, typical mistakes, migration path,
> maintenance expectations, firmware policy, and related products. Reusable
> reasoning (selection / growth / provider-router / financing / firmware /
> maintenance / installation) is **referenced** in `business-philosophy/`, not
> repeated. The only items left are hands-on technician details — see
> **Knowledge Status → Interview Backlog (Patrick)** near the end.

# Executive Summary

**What is this product?**
COMtrexx Next is the smallest current Auerswald COMtrexx IP phone system — a
compact, fanless box that gives a small business a full-featured modern telephone
system. Technically it supports up to ~40 users (Auerswald), but Teleprofi
positions it for **much smaller offices** (see below). It is the **entry-level
COMtrexx** Teleprofi installs for small new customers (`teleprofi_fulda.md`:
"current").

**Why does Teleprofi sell it?**
Primarily because it offers a **significantly lower entry price than COMtrexx Flex**,
giving a small business a professional telephone system without Flex's higher
investment (Teleprofi operational knowledge). It also matches Teleprofi's
reliability-first, preconfigured, low-maintenance delivery approach
([[installation-philosophy]]).

**Who is it for?**
Small offices of roughly **1–5 users** with light-to-moderate telephony needs
(Teleprofi operational knowledge). Teleprofi does **not** position Next as the
long-term platform for every customer — where growth is expected, Flex is discussed
early ([[product-selection-philosophy]]).

# Teleprofi Recommendation

**Ideal customer size.** Approximately **1–5 users**: a small office, a few desk
phones, light-to-moderate telephony requirements (Teleprofi operational knowledge).
Note the gap between Teleprofi's *commercial* sweet spot (1–5) and the *technical*
ceiling (40 users, Auerswald) — Teleprofi recommends moving to Flex long before the
technical limit.

**Why Teleprofi recommends it.** Lower entry price than Flex; a professional system
for small businesses that don't need Flex's investment (Teleprofi operational
knowledge).

**When Teleprofi deliberately recommends COMtrexx Flex instead.** The canonical
Next-vs-Flex decision logic — the full upgrade-trigger list and the "Flex is worth
the higher price" signals — lives in **[`comtrexx-family.md`](./comtrexx-family.md)**
(family-level, shared with Flex). In short, evaluate Flex from **~7–8 users** or when
any growth/complexity signal appears (more departments, call groups, routing,
integrations, product lines, analog devices, advanced door communication). The
decision is based on **future business needs, not just today's headcount**
([[product-selection-philosophy]], [[growth-planning-philosophy]]).

**Growth planning & future-proofing.** Always size to current users **plus planned
growth** (`teleprofi_fulda.md`). When growth is expected, **discuss Flex during the
consultation** even if Next would cover today. On Next, user licences come in blocks
that **do not stack** — growing means buying the next block up (Auerswald licensing).

**Sales guidance — do not undersize.** Never recommend COMtrexx Next **only** because
it satisfies today's requirements or because it is cheaper. Always discuss expected
growth, future locations, additional employees and future telephony requirements.
The objective is to **avoid replacing the PBX after only a few years**
([[product-selection-philosophy]]).

**If budget is the only reason to choose Next**, don't undersize — leasing (Grenke)
can make the better-fitting system (often Flex) affordable. Technical fit is decided
first; financing only supports it ([[financing-philosophy]]).

# Typical Teleprofi Customer

- **Company size:** ~1–5 users; small office (Teleprofi operational knowledge).
- **Telephony profile:** a few desk phones, light-to-moderate requirements. A common
  deployment is **2 desk phones + 3 softphones or headsets**, which is frequently
  sufficient for a small business (Teleprofi operational knowledge).
- **Typical industries:** professional offices, medical practices, retail, service
  companies (`teleprofi_fulda.md`, Target Customers).
- **Typical problems they arrive with:** ageing or failing PBX, ISDN switch-off
  pressure, registration/connectivity faults, forwarding/diversion issues
  (`teleprofi_fulda.md`).
- **Typical reasons for buying:** a dependable, professional phone system at a low
  entry price, installed and supported by one partner.

# Sales Qualification Checklist

Before recommending COMtrexx Next, determine:

- [ ] **Number of employees / active users** (Teleprofi sweet spot ~1–5; evaluate
      Flex from ~7–8).
- [ ] **Planned growth** (more employees, departments, locations?).
- [ ] **Existing PBX** (make/model → migration path).
- [ ] **Existing ISDN** (ISDN switch-off → All-IP migration + porting).
- [ ] **Analog devices** (Next has no analog ports; more analog → Flex).
- [ ] **Fax requirements** (analog fax? → ATA or Flex; or eFax).
- [ ] **DECT requirements** (cordless/mobility → WS-500S/M + COMfortel M-handsets).
- [ ] **Door intercom** (advanced door comm / future expansion → evaluate Flex).
- [ ] **Home office** (remote users/softphones — note the typical 3-softphone mix).
- [ ] **Fiber availability** (current access at the site).
- [ ] **Future fiber migration** (planned move DSL → fiber).
- [ ] **Number portability** (which numbers, from which provider).
- [ ] **Expansion plans** (more departments, call groups, routing, integrations,
      product lines).

> This is a first-principles baseline. Teleprofi's actual qualification flow will be
> captured as the reusable sales-qualification standard in `business-philosophy/`
> (interview backlog) and will then supersede this checklist.

# Typical Teleprofi Solution

Teleprofi rarely sells the PBX alone. A typical small-office COMtrexx Next solution
combines:

| Component | Why it's normally included |
|---|---|
| **COMtrexx Next** | The PBX — entry-level, low cost, right-sized for ~1–5 users. |
| **Endpoints** | Commonly **2 desk phones + 3 softphones/headsets** for a small office (Teleprofi operational knowledge); desk phones are Auerswald COMfortel D-series. |
| **Provider SIP trunk** (often **Telekom CompanyFlex**) | All-IP telephony; Teleprofi's preferred provider for new business installs (`ai-rules/provider-selection.md`, `providers/telekom.md`). |
| **AVM FRITZ!Box** | Internet access / router upstream of the PBX; model follows access technology (DSL → 7590 AX / 5690 Pro; fiber → 5590 Fiber / 5690 Pro). The SIP trunk is registered **in the PBX**, not the router. See [[provider-preference-philosophy]]. |
| **Installation service** | Preconfiguration + on-site install + testing (`services/telephone-system-installation.md`). |
| **Migration service** | Porting numbers; moving off ISDN/analog/old PBX (`services/telephone-system-migration.md`). |
| **Maintenance contract** | Ongoing support, incl. firmware updates as a billed service (`services/maintenance-contract.md`; [[firmware-policy]]). |

Provider/router choice follows `ai-rules/provider-selection.md`. Pricing lives in
`pricing/`. See `solutions/small-office-telephony.md` for the composed solution. (Provider &
router selection is now captured at the reusable level — [[provider-preference-philosophy]].)

# Teleprofi Installation Process

Teleprofi follows its standard delivery workflow — preconfiguration → workshop
testing → customer appointment → installation → configuration → testing → customer
training → documentation → support. The canonical description (and the *why*) lives
in **[[installation-philosophy]]**; it is not duplicated here.

Next-specific notes: provide network and the required external USB SSD (≥64 GB)
before commissioning (Auerswald); configure the SIP trunk per the provider's spec
(`providers/`). The exact per-step checklists (what is preconfigured / bench-tested
/ trained) are hands-on technician detail — see the Interview Backlog (Patrick).

# Teleprofi Operational Experience

> Teleprofi's own observations, separated from official documentation.

- **Firmware (Teleprofi operational experience — not an Auerswald recommendation):**
  Teleprofi deploys only **proven-stable** firmware and evaluates new releases before
  rolling them out. The policy *and* the current COMtrexx stable/avoid version list
  are maintained canonically in **[[firmware-policy]]** (shared across COMtrexx) —
  check it before any Next firmware update; not duplicated here.
- **Typical installation issues (repository):** SIP registration not coming up
  (often provider encryption/trunk config), provisioning failures, firmware
  mismatches (`teleprofi_fulda.md` §8). Triage via
  `procedures/comtrexx-registration-troubleshooting.md`.
- **Typical support requests (repository):** registration loss, forwarding/diversion
  changes, wrong announcements, post-ISDN-migration quirks (`teleprofi_fulda.md`).
- **When upgrades become necessary:** see the Flex upgrade triggers above — ~7–8
  users, growth, more departments/call groups/routing/integration/product lines,
  more analog devices, advanced door communication (Teleprofi operational knowledge).
- **When customers regret choosing too small a system:** when Next is bought to save
  money while the business is already growing past its sweet spot, forcing a PBX
  swap instead of a simple expansion. Avoided by applying
  [[product-selection-philosophy]] and, where budget is the blocker, the leasing
  route in [[financing-philosophy]]. (A concrete anecdote is optional enrichment —
  see Interview Backlog.)

# Migration

Teleprofi delivers Next as a **migration** off an old system as well as a greenfield
install; number porting and cutover are handled as a service
(`services/telephone-system-migration.md`), using the standard delivery workflow in
[[installation-philosophy]]. Next-specific migration notes:

- **From ISDN:** the common case — ISDN switch-off → All-IP on a provider SIP trunk,
  with number porting. Post-migration quirks are a known support area
  (`teleprofi_fulda.md`).
- **From an older Auerswald / legacy PBX:** in-family modernization to current
  COMtrexx.
- **From analog:** **Next has no analog ports** — analog handsets/fax must move to
  IP (COMfortel/SIP) or an ATA; a real analog requirement is itself a signal to
  consider Flex (see [`comtrexx-family.md`](./comtrexx-family.md)).
- **From hosted/cloud PBX:** move to on-prem COMtrexx with trunk + porting.

Migration **away from** Next happens when the customer outgrows it — that is the
family Next→Flex decision (`comtrexx-family.md`), not a Next-specific procedure.

# Maintenance

Teleprofi offers **firmware updates and maintenance as a professional service**,
billed where applicable; keeping systems stable and current is part of the long-term
customer relationship (Teleprofi operational knowledge). Approach:
**[[maintenance-philosophy]]**; proven-stable firmware list: **[[firmware-policy]]**. Delivery:
`services/maintenance-contract.md`, `services/remote-support.md`. The hardware
itself is fanless/low-power and needs little physical upkeep (Auerswald).

# Official Product Information

> Concise, referenced — not a rewrite of the manual. See Auerswald docs (in
> `sources`) for the full specification.

- **Capabilities:** full COMtrexx soft-PBX feature set in a compact appliance.
- **Capacity:** up to **40 users**, up to **40 simultaneous calls**; up to **16** IP
  relay/box systems and **8** IP door stations (Auerswald technical data). *(Teleprofi
  positions it far below this — see Teleprofi Recommendation.)*
- **Technical specs (headline):** fanless; ~103 × 103 × 23 mm, ~165 g, ~2.3–4.3 W;
  **no analog ports**; 10/100 Mbit/s RJ-45; requires external USB SSD (≥64 GB);
  codecs G.711/G.722 (Auerswald technical data).
- **Compatibility:** standards-based SIP PBX; native Auerswald COMfortel phones and
  Auerswald DECT; works behind a FRITZ!Box. Provider encryption specifics →
  `providers/telekom.md` / `vodafone.md` / `o2.md`.
- **Licensing:** floating user licences in blocks of 5/10/20/30/40; **blocks do not
  stack on Next** (Auerswald licensing; IT-Administrator test).
- **Expansion / limitations:** 40-user / 40-call ceiling; **no analog ports**; single
  10/100 NIC; external SSD required.

# AI Recommendation Notes

> Business reasoning only — not a product description, not an AI prompt. Canonical
> principle: [[product-selection-philosophy]]. The full **Next-vs-Flex decision
> logic is family-level** and lives in [`comtrexx-family.md`](./comtrexx-family.md);
> this note only states the **Next side**.

The AI should **never choose COMtrexx Next purely because it is less expensive.**
Lean Next when the customer is a small office (~1–5 users), with light-to-moderate
telephony, no must-keep analog/fax, no advanced door communication, and no near-term
growth signals — a professional system at the lowest entry cost, right-sized. The
moment any growth-or-complexity signal appears, switch to the family decision logic
in `comtrexx-family.md` (which leans Flex). Cross-product selection logic belongs in
a future `ai-rules/` entry that references the family entry and the philosophy files.

**Conversation example.** Customer: *"I only need two desk phones."* → A two-phone
small office sits squarely in Next's 1–5 sweet spot with light telephony and no
stated growth / analog / door signals → **Next is sufficient** and right-sized at the
lowest entry cost. Confirm there are no growth/analog/door signals before finalizing
([[product-selection-philosophy]]). Contrasting pair in
[`comtrexx-family.md`](./comtrexx-family.md).

# Knowledge Status

**Renato-answerable knowledge is complete (v1.0).** Everything Renato provides —
positioning, ideal size, Next-vs-Flex signals, provider/router choice, financing,
firmware policy, maintenance — is captured, and reusable parts live in
`business-philosophy/` / `comtrexx-family.md` / `ai-rules/` (referenced above, not
repeated). The remaining gaps are hands-on technician details only **Patrick** can
provide, plus optional enrichment and a few official-fact confirmations.

## Interview Backlog (Patrick / technician)

Hands-on detail that needs the installing technician (does **not** block v1.0;
deepens the deployment sections when answered):

- **Preconfiguration:** exactly what is configured at the workshop before a Next install.
- **Bench-test checklist:** what is verified before going on site.
- **Customer training:** what is covered, and how long it takes.
- **Firmware scope:** are the [[firmware-policy]] versions COMtrexx **system** firmware
  or COMfortel **device** firmware (or both, tracked separately)?
- **Per-provider trunk config:** any Next-specific COMtrexx trunk settings per provider
  beyond "register in the PBX" (general rule already in [[provider-preference-philosophy]]).

## Reusable backlog (Renato, but at the higher level — not in this file)

- **Sales-qualification standard** → future `business-philosophy/sales-qualification-philosophy.md`
  (will supersede the checklist above).
- **Objection handling** → reusable sales standard (model-specific objections can then
  be noted at family level).

## Optional enrichment (either)

- A concrete **"regret" anecdote** (a customer who outgrew Next, and at what user
  count) to make the growth-planning lesson vivid.

# Related Products

- [`comtrexx-family.md`](./comtrexx-family.md) — **family-level** logic: when to
  choose COMtrexx at all, and Next vs. Flex (the canonical decision lives here).
- [`comtrexx-flex.md`](./comtrexx-flex.md) — the scalable long-term COMtrexx for
  growth, analog, advanced door comm, and >~7–8 users.
- COMfortel D-series desk phones; COMfortel M-710/M-730 DECT; WS-500S/M DECT bases.

# Related Philosophy

- [`../business-philosophy/product-selection-philosophy.md`](../business-philosophy/product-selection-philosophy.md)
- [`../business-philosophy/growth-planning-philosophy.md`](../business-philosophy/growth-planning-philosophy.md)
- [`../business-philosophy/installation-philosophy.md`](../business-philosophy/installation-philosophy.md)
- [`../business-philosophy/firmware-policy.md`](../business-philosophy/firmware-policy.md)
- [`../business-philosophy/maintenance-philosophy.md`](../business-philosophy/maintenance-philosophy.md)
- [`../business-philosophy/provider-preference-philosophy.md`](../business-philosophy/provider-preference-philosophy.md)
- [`../business-philosophy/financing-philosophy.md`](../business-philosophy/financing-philosophy.md)

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

- `../solutions/small-office-telephony.md`
- `../solutions/growing-business-telephony.md`

# Related Procedures

- `../procedures/comtrexx-registration-troubleshooting.md`
- `../procedures/voice-escalation-validation.md`

# Related ADRs

- `../decisions/0001-deflect-not-bridge-for-orbit-escalation.md`
- `../decisions/0007-comtrexx-validation-is-manual.md`

# Related AI Rules

- [`../ai-rules/provider-selection.md`](../ai-rules/provider-selection.md)
- Product-selection (Next vs. Flex) — *future* `ai-rules/` entry referencing the
  philosophy files.

# Open Questions (official facts to confirm)

- "Up to ~200 manageable devices" (IT-Administrator test) vs. Auerswald's official
  per-category limits (16 IP relay, 8 IP door).
- Exact COMfortel/SIP phone + DECT compatibility/capacity matrix for current firmware.
- Per-provider certification and cipher-suite support (CompanyFlex/Vodafone/o2).

# Knowledge History

| Version | Date | Change | Source |
|---|---|---|---|
| 0.1 | 2026-06-25 | Initial Teleprofi-first draft (repo + official Auerswald); gaps framed as interview questions | repo + Auerswald docs |
| 0.2 | 2026-06-25 | Integrated Teleprofi operational knowledge: ideal ~1–5 users, lower-entry-price positioning, Next→Flex upgrade triggers, typical 2 desk + 3 soft/headset, firmware stability, maintenance-as-service | Teleprofi (Renato) |
| 1.0 | 2026-06-25 | Provider/router + financing routed to `business-philosophy/`; Next-vs-Flex logic centralized in `comtrexx-family.md`; added Migration section; closed Renato-answerable items; remaining hands-on items moved to Patrick interview backlog; status → active | Teleprofi (Renato) + reusable knowledge |
| 1.0 | 2026-06-25 | Added AI conversation example (two-desk-phones → Next) | Teleprofi (Renato) |

# Knowledge Confidence

| Area | Confidence | Reason |
|---|---|---|
| When to recommend / not (Next vs. Flex signals) | high | captured from Teleprofi (Renato) + family entry |
| Typical customer & deployment (1–5 users; 2 desk + 3 soft) | high | captured from Teleprofi (Renato) |
| Provider / router choice | high | reusable [[provider-preference-philosophy]] |
| Financing (purchase/rental/leasing) | high | reusable [[financing-philosophy]] |
| Firmware policy | high | reusable [[firmware-policy]] (version scope pending Patrick) |
| Maintenance expectations | high | reusable [[maintenance-philosophy]] |
| Migration path | medium | pattern clear; per-source feature-parity not yet detailed |
| Installation step detail (preconfig/bench/training) | needs-confirmation | hands-on — Patrick backlog |
| Official capacity/specs | medium | Auerswald docs; device-count figure to confirm (Open Questions) |
| Phone/DECT compatibility matrix | needs-confirmation | exact per-firmware matrix not confirmed (Open Questions) |
