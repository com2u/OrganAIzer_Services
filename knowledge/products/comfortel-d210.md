---
id: comfortel-d210
type: product
owner: unassigned
status: draft
knowledge_version: 0.1   # first desk-phone entry; teaches when the entry-tier D-210 fits. Teleprofi gaps are interview questions
last_reviewed: 2026-06-25
sources:
  - backend/voice/knowledge/teleprofi_fulda.md            # primary: Teleprofi business knowledge (D-210 listed current)
  - Teleprofi operational knowledge (Renato, 2026-06-25)   # primary
  - knowledge/products/comtrexx-family.md                  # the PBX (not duplicated)
  - https://www.auerswald.de/en/product/comfortel-d-210    # supporting: official
  - https://www.auerswald.de/en/product/comfortel-d-400    # supporting: official (sibling)
  - https://www.auerswald.de/en/product/comfortel-d-600    # supporting: official (sibling)
category: phone
vendor: Auerswald
model: COMfortel D-210
lifecycle: current
---

# Auerswald COMfortel D-210 — Teleprofi product knowledge

> The **entry-tier wired desk phone** in Teleprofi's Auerswald COMfortel D-series
> (D-210 → D-400 → D-600). This entry teaches **when the D-210 is the right desk
> phone**. Shared desk-phone knowledge (how COMtrexx desk phones are provisioned,
> PoE/network, the tier ladder) will become a reusable **`deskphone-family.md`**
> later — kept light and **referenced**, not duplicated here. Reusable principles live
> in `business-philosophy/`.
>
> **Knowledge maturity: v0.1 (draft).** Teleprofi-specific gaps are precise questions
> under **[Teleprofi Knowledge Needed](#teleprofi-knowledge-needed)**.

# Executive Summary

**What is it?** The **entry-level** COMfortel IP desk phone — a wired SIP system phone
with a **graphical (non-touch) display**, that is nonetheless **highly expandable**:
up to **three COMfortel D-XT20i modules → up to 66 programmable keys** (Auerswald). It
registers to the COMtrexx PBX.

**Who is it for?** **Standard office desks** and **cost-sensitive fleets** — users who
need a reliable, full-featured system phone without a colour touchscreen. Also the
**budget many-key** option (reception/operator) thanks to expansion modules.

**Why does Teleprofi sell it?** It's the **current entry desk phone** (`teleprofi_fulda.md`)
and the right-sized, cost-effective choice for ordinary workstations
([[product-selection-philosophy]]: fit, not over-spec).

# Teleprofi Recommendation

Recommend the **D-210 for standard desks** where a colour touch display and advanced
headset features aren't needed — especially across **larger, cost-sensitive fleets**.
Step up to the **D-400** (colour touch + EHS headset) or **D-600** (7″ touch +
Bluetooth) for users whose role justifies it (see below). The desk-phone choice is
**role/feature-tier driven**; the per-role split is the key open question (Q1).

# Typical Customer

Businesses fitting out **fixed workstations** on a COMtrexx system — offices,
practices, retail back-office (`teleprofi_fulda.md`). The D-210 is the **volume desk
phone** for ordinary users; D-400/D-600 are layered in for specific roles. (Teleprofi's
real desk-phone mix per site — Knowledge Needed Q1.)

# Typical Deployment

Wired desk phone: connect via Ethernet (**PoE** where the switch supports it; Teleprofi
does switches/PoE/cabling — `teleprofi_fulda.md`), register/provision to the **COMtrexx
PBX** (`comtrexx-family.md`). Provisioning/registration is shared desk-phone behaviour
(→ future `deskphone-family.md`); not detailed per-model here. (Teleprofi desk-phone
provisioning checklist — Patrick backlog.)

# Typical Bundle

A desk phone is part of a complete workstation/telephony solution — referenced, not
duplicated:

| Part | Reference |
|---|---|
| **PBX** | COMtrexx (`comtrexx-family.md`) |
| **Network** | switch / PoE / structured cabling (`teleprofi_fulda.md`: switching, cabling) |
| **Provider + router** | [[provider-preference-philosophy]] / `fritzbox-family.md` |
| **Expansion modules** | COMfortel **D-XT20i** for key-heavy desks (reception/operator) |
| **Installation + maintenance** | `../services/telephone-system-installation.md`, `../services/maintenance-contract.md` |

Pricing → `pricing/`.

# Strengths

- **Entry price** for a full COMfortel system phone — ideal for **volume desks**.
- **Highly expandable:** up to 3 D-XT20i modules → **up to 66 programmable keys**
  (Auerswald) — a cheap path to a **many-BLF reception/operator** phone.
- Native COMtrexx/COMfortel integration (one Auerswald ecosystem).

# Limitations

- **Graphical (non-touch) display** — no colour touchscreen (that's the D-400/D-600).
- Fewer onboard comfort features than the higher tiers (advanced headset/Bluetooth,
  large touch UI).
- Wired desk phone — for **mobility**, that's DECT (`ws-500s.md` + M-710/M-730), not
  this product.

# Typical Office Environment

Fixed **indoor office workstations** — ordinary desks where users make/receive normal
call volumes. Not for mobile/cordless needs (DECT) and not where a role needs a premium
touch device (D-600).

# Expansion Possibilities

Up to **three COMfortel D-XT20i** expansion modules, reaching **up to 66 freely
programmable keys** (Auerswald). This makes the inexpensive D-210 a viable
**reception/operator** phone where the value is **many BLF/function keys** rather than
a rich display — a useful Teleprofi option to weigh against a D-600 for that role (Q2).

# When Teleprofi recommends the D210

Standard desks; cost-sensitive fleets; users who need a reliable system phone (and
optionally many programmable keys via modules) **without** a colour touch display.

# When D400 is the better choice

Users who want a **4.3″ colour touch display** and **EHS/DHSG headset** support — e.g.
knowledge workers / frequent callers — at a still-modest price (Auerswald: "premium
functions at almost entry-level price"). *(Dedicated `comfortel-d400.md` to come.)*

# When D600 is the better choice

**Executives, reception, power users** wanting the **7″ colour touch** display,
**Bluetooth** + EHS headset, and the most on-screen keys — the premium D-series device
(Auerswald). *(Dedicated `comfortel-d600.md` to come.)*

# Common customer questions

- "What's the cheapest proper desk phone?" → the D-210 (entry tier).
- "Our receptionist needs to see lots of extensions — do we need the expensive phone?"
  → not necessarily; a D-210 + expansion modules gives many keys cheaply (or a D-600).
- "Does it have a touchscreen?" → no; that's the D-400 (4.3″) / D-600 (7″).
- "Can we mix D-210s with a few D-600s?" → yes, all COMfortel D-series on COMtrexx.

# Typical support issues

Desk-phone support: **provisioning/registration** to COMtrexx, **PoE/network** (no
power / wrong VLAN), firmware, key/module config (`teleprofi_fulda.md`: registration,
PoE, provisioning issues). Shared across the D-series (→ future family). (Most common
D-210 support call — Knowledge Needed Q3.)

# Installation expectations

Provision/register to COMtrexx, connect via PoE switch, configure keys/modules;
validate per [[installation-philosophy]] (`services/telephone-system-installation.md`).
Largely shared desk-phone process (→ future `deskphone-family.md`). (Checklist — Patrick
backlog.)

# Maintenance expectations

Firmware per [[firmware-policy]] (proven-stable; updates as a billed service per
[[maintenance-philosophy]]) — kept consistent across the Auerswald estate. Low-touch
wired device.

# Firmware / update policy

Shared [[firmware-policy]] — only proven-stable firmware, evaluated first; updates as a
billed service. Not restated here. *(COMfortel **device** firmware scope in the policy
is the open question already tracked in [[firmware-policy]].)*

# AI Recommendation Signals

**Lean D-210** on a **standard-desk / cost-sensitive / volume** signal, or a
**many-keys-on-a-budget** (reception via modules) signal. **Lean D-400** on a
**colour-touch + headset** signal; **lean D-600** on an **executive/reception/power-user
premium** signal. Decisive axis = **role / feature tier**, not user count. Don't over-
spec ordinary desks ([[product-selection-philosophy]]).

# AI Conversation Example

Customer: *"We're equipping about 20 standard office desks — nothing fancy, just
reliable phones, and we'd like to keep the cost down."*
→ A **standard-desk, cost-sensitive, volume** signal → recommend the **COMfortel
D-210**: the entry-tier system phone, right-sized for ordinary desks
([[product-selection-philosophy]]), all on the COMtrexx PBX. *(If the receptionist
needs to monitor many extensions, add D-XT20i key modules to a D-210 — or a D-600 — and
if specific users want a colour touchscreen/headset, fit a D-400 for them.)*

# Cross-Selling Opportunities

- **PBX:** COMtrexx (`comtrexx-family.md`).
- **Network:** switches / PoE / structured cabling (`teleprofi_fulda.md`).
- **Provider + router:** [[provider-preference-philosophy]] / `fritzbox-family.md`.
- **Expansion modules:** COMfortel **D-XT20i** (key-heavy desks).
- **Higher tiers** for specific roles: `comfortel-d400.md` / `comfortel-d600.md` (to come).
- **Installation + maintenance:** `../services/telephone-system-installation.md`,
  `../services/maintenance-contract.md`.

# Related products

- `comfortel-d400.md` — mid-tier (colour touch + EHS headset) (to come).
- `comfortel-d600.md` — premium (7″ touch + Bluetooth) (to come).
- `comtrexx-family.md` — the PBX the desk phones register to.
- `comfortel-m710.md` / `comfortel-m730.md` — the **cordless** alternative (DECT) for
  mobility instead of a wired desk phone.

# Related (reusable knowledge)

- Philosophy: [[product-selection-philosophy]], [[installation-philosophy]],
  [[firmware-policy]], [[maintenance-philosophy]].
- AI rules: `../ai-rules/provider-selection.md` (wider solution).
- Services: `../services/telephone-system-installation.md`, `../services/maintenance-contract.md`.

# Teleprofi Knowledge Needed

**Renato (commercial / selection) — the core boundary:**
1. Teleprofi's typical **desk-phone mix per site** — which roles get D-210 vs D-400 vs
   D-600, and the rough ratio?
2. For a **reception/operator** desk, does Teleprofi prefer **D-210 + key modules** or a
   **D-600**, and why?
4. Any customers/situations where Teleprofi **avoids** the D-210 (e.g. always steps up)?

**Patrick (technician / hands-on):**
3. Most common **D-210 support call** (provisioning, PoE, key/module config)?
5. Teleprofi's **desk-phone provisioning/registration** checklist (shared across the
   D-series — will seed the future `deskphone-family.md`).

# Knowledge History

| Version | Date | Change | Source |
|---|---|---|---|
| 0.1 | 2026-06-25 | First desk-phone entry: entry-tier positioning, expansion-module angle, D-210 vs D-400 vs D-600 boundary (kept brief for a future family), AI signals + conversation example + cross-selling; shared desk-phone process referenced not duplicated | repo Teleprofi knowledge + official Auerswald |

# Knowledge Confidence

| Area | Confidence | Reason |
|---|---|---|
| Tier positioning (D-210 entry vs D-400/D-600) | high | official Auerswald product pages |
| Expansion (3× D-XT20i → up to 66 keys) | high | official Auerswald |
| Display/headset tier differences | high | official Auerswald |
| Teleprofi desk-phone mix / per-role assignment | needs-confirmation | not captured — Q1/Q2 |
| Reception: D-210+modules vs D-600 preference | needs-confirmation | Q2 |
| Support issues / provisioning checklist | needs-confirmation | Q3 + Patrick backlog |
| COMfortel device firmware scope in firmware-policy | needs-confirmation | open in [[firmware-policy]] |
