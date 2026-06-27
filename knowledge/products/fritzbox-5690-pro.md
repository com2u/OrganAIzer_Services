---
id: fritzbox-5690-pro
type: product
owner: unassigned
status: draft
knowledge_version: 0.1   # first router entry; sets the router standard. Teleprofi gaps are interview questions
last_reviewed: 2026-06-25
sources:
  - backend/voice/knowledge/teleprofi_fulda.md             # primary: Teleprofi business knowledge
  - Teleprofi operational knowledge (Renato, 2026-06-25)    # primary
  - knowledge/business-philosophy/provider-preference-philosophy.md  # router-by-access-tech rule (not duplicated)
  - https://fritz.com/en/products/fritz-box-5690-pro-20003043        # supporting: official AVM
category: router
vendor: AVM
model: FRITZ!Box 5690 Pro
lifecycle: current
---

# AVM FRITZ!Box 5690 Pro — Teleprofi product knowledge

> Captures **Teleprofi's** knowledge of when, why and how it sells, installs and
> supports the FRITZ!Box 5690 Pro. This is the **first router entry** and sets the
> router pattern. Router/provider *decision logic* lives in
> [[provider-preference-philosophy]] and `ai-rules/provider-selection.md` and is
> **referenced, not repeated**.
>
> **Knowledge maturity: v0.1 (draft).** Built from Teleprofi philosophy, repository
> knowledge, and official AVM data. Teleprofi-specific gaps are precise questions
> under **[Teleprofi Knowledge Needed](#teleprofi-knowledge-needed)**.

# Executive Summary

**What is it?** AVM's flagship **Wi-Fi 7** business/prosumer router that handles
**both fiber and DSL**: an **integrated fibre ONT** (GPON up to 2.5 Gbit/s, AON, via
SFP — two modules included) **and** a built-in **DSL modem** (VDSL Supervectoring
35b, ADSL2+), plus a 2.5 Gbit/s WAN/LAN port and tri-band Wi-Fi 7 (AVM).

**Who is it for?** Business customers who are on **DSL today but expect fiber**, or
who want one router that won't need replacing across that transition — Teleprofi's
**future-proofing** choice ([[provider-preference-philosophy]], [[growth-planning-philosophy]]).

**Why does Teleprofi sell it?** Because it is the **migration-proof** router: a
customer can start on DSL and move to fiber **without replacing the router**
(Teleprofi router philosophy). It sits upstream of the COMtrexx PBX as internet
access; the SIP trunk is registered **in the PBX**, not the router
([[provider-preference-philosophy]]).

# Teleprofi Recommendation

Recommend the 5690 Pro when the access technology is **DSL-now-fiber-later**, when
fiber timing is **uncertain**, or when the customer wants **one future-proof router**
across the transition. Router choice follows **access technology** — the canonical
rule is in [[provider-preference-philosophy]]; the 5690 Pro is the choice that
**covers both** sides of a migration. It is a premium router, so where the customer
is clearly fiber-only or DSL-only with no migration, a cheaper sibling fits (see
Migration Scenarios).

# Typical Customer

Business customers upstream of a COMtrexx install (`teleprofi_fulda.md`: DSL/fiber +
provider coordination) — especially those **mid-migration** or anticipating fiber.
(Teleprofi's actual 5690 Pro deployment frequency / customer profile — Knowledge
Needed Q1.)

# Typical Deployment

The site **router / internet access** in front of the COMtrexx PBX: terminates DSL
or fiber, provides firewall, network routing, Wi-Fi, and LAN; the PBX owns telephony
and the SIP trunk ([[provider-preference-philosophy]]). Often paired with mesh
(FRITZ!Repeater) for Wi-Fi coverage.

# Typical Bundle

Same "connectivity layer" role as any router in a Teleprofi solution — referenced,
not duplicated:

| Part | Reference |
|---|---|
| **PBX** | COMtrexx (`comtrexx-family.md`) — trunk registered in the PBX |
| **Provider** | per [[provider-preference-philosophy]] (Telekom preferred for new business) + `ai-rules/provider-selection.md` |
| **Wi-Fi mesh** | `fritz-repeater-6000.md` (`products/` entry to come) for coverage |
| **Survey / installation / maintenance** | `services/wifi-site-survey.md`, `services/fiber-installation.md`, `services/telephone-system-installation.md`, `services/maintenance-contract.md` |

Pricing → `pricing/`. Composed deployments → `solutions/` (e.g. `fiber-migration.md`).

# Strengths

- **Dual WAN: fiber + DSL** — integrated GPON/AON ONT (SFP) **and** VDSL/ADSL modem
  (AVM). This is the migration USP.
- **Wi-Fi 7** tri-band + **2.5 Gbit/s** WAN/LAN port; mesh with other FRITZ!Boxes (AVM).
- Familiar FRITZ!OS administration — a Teleprofi-standard router platform
  (`teleprofi_fulda.md`).

# Limitations

- **Premium price** — overkill where the customer is firmly fiber-only or DSL-only
  with no migration (see siblings below).
- Its integrated **DECT/smart-home** features are largely consumer; **Auerswald
  COMfortel system handsets use Auerswald WS-500 DECT bases**, not the FRITZ!Box DECT
  base (do not rely on the FRITZ!Box as the DECT base for COMfortel handsets —
  confirm: Knowledge Needed Q4).
- Direct fiber termination depends on the **provider's fiber type/permission** (see
  Migration Scenarios → ISP ONT transition).

# When Teleprofi recommends the 5690 Pro

DSL-now-fiber-later, uncertain fiber timing, or "one router for the whole journey."

# When Teleprofi does NOT recommend it

- **Fiber-only, no DSL fallback needed → FRITZ!Box 5590 Fiber** (cheaper, fiber-native).
- **DSL-only, no fiber migration expected → FRITZ!Box 7590 AX** (sufficient, cheaper).

> Canonical router selection across all three models:
> [`fritzbox-family.md`](./fritzbox-family.md) → Router Selection Decision Table.
> Principle: access-technology rule in [[provider-preference-philosophy]].

## Migration Scenarios

> Router/provider decision logic is referenced from [[provider-preference-philosophy]]
> and `ai-rules/provider-selection.md` — not duplicated.

- **DSL today → fiber later.** The 5690 Pro's built-in DSL modem **and** fibre ONT
  mean the customer runs DSL now and **switches to fiber by re-cabling to the SFP
  fibre module — no router replacement**. This is the core reason to choose it.
- **Why Teleprofi often recommends it.** Future-proofing: it avoids buying a second
  router at migration and avoids a re-install of the whole edge. Fits
  [[product-selection-philosophy]] (size for the investment's life) and
  [[growth-planning-philosophy]].
- **Fiber ID.** Activating a fibre line typically needs the **provider's fibre-line
  activation data** (e.g. a Fiber-/Glasfaser-ID) to bring up the connection. The
  exact item and process are **provider-specific** — confirm per provider (Patrick
  backlog Q6); do not assume.
- **ISP ONT transition.** With its **integrated ONT** (AON/GPON SFP modules), the
  5690 Pro can often **replace a separate ISP-provided ONT/media converter** — but
  whether the provider supports direct termination depends on **fiber type and
  provider policy** (AON vs GPON). Confirm per provider before promising it
  (Knowledge Needed Q5).
- **Telekom recommendation.** Where Teleprofi's preferred provider applies (new
  business installs → Telekom; [[provider-preference-philosophy]],
  `ai-rules/provider-selection.md`), the 5690 Pro pairs with Telekom DSL today and
  Telekom fibre later. Exact Telekom-fibre + 5690 Pro provisioning steps — confirm
  (Patrick backlog).
- **When a sibling is the better choice** (fiber-native → 5590 Fiber; DSL-only,
  no-migration → 7590 AX): see the full table in
  [`fritzbox-family.md`](./fritzbox-family.md).

# Common customer questions

- "We're on DSL but fiber is coming — what should we buy?" → 5690 Pro (one router for both).
- "Will I need a new router when fiber arrives?" → no, the 5690 Pro already handles fiber.
- "Can it replace the ONT box from my provider?" → often yes, provider-dependent (see above).
- "Do we still need a separate DECT base for our handsets?" → yes for Auerswald
  COMfortel handsets (WS-500S/M) — confirm (Q4).

# Typical support issues

Router-class support: line sync/activation at provisioning (DSL or fiber), Wi-Fi
coverage, port-forwarding/firewall, firmware (`teleprofi_fulda.md`: internet-access
issues — outages, router access, IP changes, port forwarding). (Most common 5690 Pro
support call — Knowledge Needed Q2.)

# Installation expectations

Edge install: terminate DSL/fiber, configure WAN, Wi-Fi, firewall/NAT; ensure the
**SIP trunk is provisioned in the COMtrexx PBX**, not the router
([[provider-preference-philosophy]]); validate per [[installation-philosophy]].
Fiber installs may involve the provider's ONT/fiber activation (see Migration
Scenarios). (Teleprofi router preconfig/bench checklist — Patrick backlog.)

# Maintenance expectations

Firmware (FRITZ!OS) handled per [[firmware-policy]] (proven-stable; updates as a
billed service per [[maintenance-philosophy]]). Routers are long-lived; the 5690 Pro
is chosen partly to **avoid** a mid-life hardware swap at fiber migration.

# Firmware / update policy

Shared [[firmware-policy]] — only proven-stable FRITZ!OS, evaluated first; updates
as a billed service. Not restated here. *(Whether the policy's version table tracks
FRITZ!OS as well as Auerswald firmware is the open scope question in [[firmware-policy]].)*

# AI Recommendation Signals

**Lean 5690 Pro** on any **migration/uncertainty** signal: "fiber is coming",
"on DSL now but…", unknown fiber timeline, or a desire to buy once. **Lean 5590
Fiber** on a clean **fiber-only** signal; **lean 7590 AX** on a **DSL-only, no
migration** signal. Decisive signal = **access technology + migration outlook**
(not price); don't downgrade away from a needed migration path on price alone
([[product-selection-philosophy]]) — financing applies to the wider solution
([[financing-philosophy]]).

# AI Conversation Example

Customer: *"We're on DSL now, but fibre is being rolled out on our street and we'll
switch within a year or two."*
→ A **DSL-now-fiber-later** signal → recommend the **FRITZ!Box 5690 Pro**: it runs
the DSL line today and already has the fibre ONT, so when fibre is activated the
customer **moves over without replacing the router or re-doing the edge install**.
Frame it as avoiding a second purchase + reinstall, not an upsell
([[product-selection-philosophy]]). Provider follows [[provider-preference-philosophy]]
(Telekom for a new business install). If fibre will **never** come, the DSL-only
7590 AX would be enough.

# Cross-Selling Opportunities

- **PBX:** COMtrexx (`comtrexx-family.md`) if telephony is in scope.
- **Provider:** SIP trunk + line per [[provider-preference-philosophy]] / `ai-rules/provider-selection.md`.
- **Wi-Fi mesh:** **FRITZ!Repeater 6000** (`fritz-repeater-6000.md` to come) for coverage.
- **Wi-Fi site survey:** `../services/wifi-site-survey.md`.
- **Fiber installation / migration:** `../services/fiber-installation.md`,
  `../solutions/fiber-migration.md`.
- **Installation + maintenance contract:** `../services/telephone-system-installation.md`,
  `../services/maintenance-contract.md`.
- **DECT base** (if cordless needed): Auerswald **WS-500S/M** (`products/` to come).

# Related products

- [`fritzbox-family.md`](./fritzbox-family.md) — **canonical router selection model**
  (decision table, access-tech matrix, migration strategy across all three routers).
- [`fritzbox-5590-fiber.md`](./fritzbox-5590-fiber.md) — fiber-only sibling.
- [`fritzbox-7590-ax.md`](./fritzbox-7590-ax.md) — DSL-only sibling.
- `fritz-repeater-6000.md` — Wi-Fi mesh extension (to come).
- `comtrexx-family.md` — the PBX the router sits in front of.

# Related (reusable knowledge)

- Philosophy: [[provider-preference-philosophy]], [[product-selection-philosophy]],
  [[growth-planning-philosophy]], [[installation-philosophy]], [[firmware-policy]],
  [[maintenance-philosophy]], [[financing-philosophy]].
- AI rules: `../ai-rules/provider-selection.md` (router-by-access-tech, trunk-in-PBX).
- Providers: `../providers/telekom.md` (+ vodafone/o2).
- Services/solutions: `../services/fiber-installation.md`, `../services/wifi-site-survey.md`,
  `../solutions/fiber-migration.md`.

# Teleprofi Knowledge Needed

**Renato (commercial / selection):**
1. How often do you deploy the 5690 Pro vs. the 5590 / 7590 AX, and what tips it?
2. Typical customer profile for the 5690 Pro (sectors, sizes, migration timing).
3. Do you proactively recommend the 5690 Pro to DSL customers as future-proofing,
   or only when fiber is already planned?

**Patrick (technician / hands-on):**
4. Do Auerswald **COMfortel handsets ever use the FRITZ!Box DECT base**, or always
   WS-500S/M? (Confirms the Limitations note.)
5. Which **providers/fiber types** let the 5690 Pro terminate fiber directly
   (replace the ISP ONT), and which require keeping the ISP ONT?
6. The **fiber activation** procedure (Fiber-/Glasfaser-ID handling) per provider,
   esp. Telekom.

# Knowledge History

| Version | Date | Change | Source |
|---|---|---|---|
| 0.1 | 2026-06-25 | First router entry (sets the router standard): migration-proof positioning, Migration Scenarios section, AI signals + conversation example + cross-selling; router/provider logic referenced not duplicated | Teleprofi philosophy + repo + official AVM |

# Knowledge Confidence

| Area | Confidence | Reason |
|---|---|---|
| Dual fiber+DSL / Wi-Fi 7 / ports specs | high | official AVM |
| Migration positioning (DSL→fiber, no router swap) | high | reuses [[provider-preference-philosophy]] + official capability |
| Sibling choice (5690 vs 5590 vs 7590 AX) | high | provider philosophy + official product lines |
| Teleprofi deployment frequency / customer profile | needs-confirmation | not captured — Q1/Q2 |
| Direct fiber termination per provider / Fiber ID process | needs-confirmation | provider-specific — Q5/Q6 |
| COMfortel-vs-FRITZ DECT base | needs-confirmation | Q4 |
| FRITZ!OS firmware scope in firmware-policy | needs-confirmation | open in [[firmware-policy]] |
