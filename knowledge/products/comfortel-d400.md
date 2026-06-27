---
id: comfortel-d400
type: product
owner: unassigned
status: draft
knowledge_version: 0.1   # middle desk-phone tier; teaches D-400-vs-D210/D600. Teleprofi gaps are interview questions
last_reviewed: 2026-06-25
sources:
  - backend/voice/knowledge/teleprofi_fulda.md            # primary: Teleprofi business knowledge (D-400 listed current)
  - Teleprofi operational knowledge (Renato, 2026-06-25)   # primary
  - knowledge/products/comfortel-d210.md                   # entry-tier sibling (shared desk-phone knowledge)
  - https://www.auerswald.de/en/product/comfortel-d-400    # supporting: official
  - https://www.auerswald.de/en/product/comfortel-d-600    # supporting: official (premium sibling)
category: phone
vendor: Auerswald
model: COMfortel D-400
lifecycle: current
---

# Auerswald COMfortel D-400 — Teleprofi product knowledge

> The **middle tier** of Teleprofi's Auerswald COMfortel desk-phone portfolio
> (D-210 → **D-400** → D-600). This entry teaches **why Teleprofi picks the D-400 over
> the D-210 or D-600**. Shared desk-phone mechanics (COMtrexx provisioning, PoE/network)
> live in [`comfortel-d210.md`](./comfortel-d210.md) and will consolidate into a future
> **`deskphone-family.md`** — kept light and **referenced**, not duplicated. Reusable
> principles live in `business-philosophy/`.
>
> **Knowledge maturity: v0.1 (draft).** Teleprofi-specific gaps are precise questions
> under **[Teleprofi Knowledge Needed](#teleprofi-knowledge-needed)**.

# Executive Summary

**What is it?** The **professional mid-tier** COMfortel IP desk phone — a **4.3″ colour
capacitive touch display**, **20 self-labelling, programmable keys with LED signalling**
(expandable to **80** keys with modules), and **EHS/DHSG headset** support (Auerswald).
Auerswald positions it as "premium functions at almost entry-level price." It registers
to the COMtrexx PBX.

**Who is it for?** Users who **work the phone** — frequent/customer-facing callers — who
benefit from a **colour touch UI** and a **wired headset**, without needing the premium
D-600.

**Why does Teleprofi sell it?** It's the **current mid desk phone** (`teleprofi_fulda.md`)
and the productivity sweet spot: real comfort features at a modest step up from the
D-210 ([[product-selection-philosophy]]).

# Teleprofi Recommendation

Recommend the **D-400 for productivity-oriented users** — touch UI + headset for people
on the phone a lot — where the **D-210 feels too basic** but the **D-600 is more than
the role needs**. The desk-phone choice is **role/feature-tier driven**; the canonical
tier ladder and per-role split will live in the future `deskphone-family.md` (and the
real Teleprofi mix is the open question — Q1).

# Typical Customer

Businesses with **customer-facing / heavy-phone roles** — sales, support, service desks,
front office — on a COMtrexx system (`teleprofi_fulda.md`). Often the **mid layer** of a
mixed fleet (D-210 for standard desks, D-400 for phone-heavy roles, D-600 for
execs/reception). (Real Teleprofi mix — Knowledge Needed Q1.)

# Typical Deployment

Wired desk phone: PoE Ethernet, provisioned/registered to the **COMtrexx PBX**
(`comtrexx-family.md`). Provisioning/registration is shared desk-phone behaviour — see
[`comfortel-d210.md`](./comfortel-d210.md), Typical Deployment (→ future family); not
re-detailed here.

# Typical Bundle

Part of a complete workstation/telephony solution — referenced, not duplicated (same
structure as the D-210):

| Part | Reference |
|---|---|
| **PBX** | COMtrexx (`comtrexx-family.md`) |
| **Network** | switch / PoE / cabling (`teleprofi_fulda.md`) |
| **Provider + router** | [[provider-preference-philosophy]] / `fritzbox-family.md` |
| **Headset** | EHS/DHSG wired headset (Jabra line, `teleprofi_fulda.md`) — a natural D-400 attach |
| **Expansion modules** | COMfortel **D-XT20i** (to 80 keys) for key-heavy desks |
| **Installation + maintenance** | `../services/telephone-system-installation.md`, `../services/maintenance-contract.md` |

Pricing → `pricing/`.

# Strengths

- **4.3″ colour capacitive touch** display — easier, faster handling than the D-210
  (Auerswald).
- **20 self-labelling programmable keys with LED** (BLF), expandable to **80** (Auerswald).
- **EHS/DHSG headset** support — hands-free for heavy callers (Auerswald).
- Native COMtrexx/COMfortel integration; strong **value** ("premium at near-entry price").

# Limitations

- **No Bluetooth** — wireless/Bluetooth headset is a **D-600** feature.
- Smaller **4.3″** screen and fewer on-screen keys than the **7″ D-600**.
- Wired desk phone — mobility is DECT (`ws-500s.md` + M-710/M-730), not this product.

# Typical Office Environment

Fixed indoor workstations for **phone-centric roles** — sales floors, support/service
desks, front office — where the touch UI and a headset speed up everyday call handling.

# Productivity Features

The D-400's reason to exist over the D-210:
- **Colour touch UI** — quicker navigation of calls, contacts, functions.
- **Self-labelling LED keys** (BLF/speed-dial) — see colleague/line status at a glance;
  valuable for teams and small operator roles.
- **EHS/DHSG headset** — answer/end on the headset, hands free for multitasking callers.

These suit users whose **time on the phone** justifies the step up; for occasional
callers the D-210 is enough (below).

# Expansion Possibilities

Programmable keys **expandable to 80** via COMfortel **D-XT20i** modules (Auerswald) —
covering BLF-heavy desks and small operator roles without moving to the D-600.

# When Teleprofi recommends the D400

Phone-centric/customer-facing users who benefit from **touch + headset + BLF keys**, at
a modest step up from the D-210.

# When D210 is sufficient

Standard/occasional-call desks and **cost-sensitive fleets** that don't need a touch
screen or headset features — see [`comfortel-d210.md`](./comfortel-d210.md). *(Full tier
ladder → future `deskphone-family.md`.)*

# When D600 is justified

**Executives, reception, power users** needing the **7″ touch**, **Bluetooth** headset,
and the most on-screen keys — the premium tier (`comfortel-d600.md`, to come).
*(Full tier ladder → future `deskphone-family.md`.)*

# Common customer questions

- "What's the difference vs the cheap one (D-210)?" → colour touch + headset + LED keys.
- "Can I use a wireless/Bluetooth headset?" → not on the D-400 (EHS/DHSG wired); Bluetooth
  is the D-600.
- "Is it good for our sales team on the phone all day?" → yes — touch UI + headset.
- "Can we mix D-400s with D-210s/D-600s?" → yes, all COMfortel D-series on COMtrexx.

# Typical support issues

Desk-phone support: provisioning/registration to COMtrexx, PoE/network, headset (EHS)
pairing/config, key/module setup, firmware — shared across the D-series (→ future
family; `comfortel-d210.md`, Typical support issues). (Most common D-400 support call —
Knowledge Needed Q3.)

# Installation expectations

Provision/register to COMtrexx, PoE connect, configure keys/headset; validate per
[[installation-philosophy]] (`services/telephone-system-installation.md`). Shared
desk-phone process (→ future family). (Checklist — Patrick backlog.)

# Maintenance expectations

Firmware per [[firmware-policy]] (proven-stable; updates as a billed service per
[[maintenance-philosophy]]). Low-touch wired device; the **headset** is an added
support/maintenance surface vs the D-210.

# Firmware / update policy

Shared [[firmware-policy]] — only proven-stable firmware, evaluated first; updates as a
billed service. Not restated here. *(COMfortel device firmware scope is the open
question already tracked in [[firmware-policy]].)*

# AI Recommendation Signals

**Lean D-400** on a **phone-centric / customer-facing / wants-touch-and-headset** signal
where the D-210 is too basic and the D-600 is over-spec. **Lean D-210** on a
**standard/occasional/cost-sensitive** signal; **lean D-600** on an
**executive/reception/Bluetooth/large-screen** signal. Decisive axis = **role / feature
tier**, not user count.

# AI Conversation Example

Customer: *"Our sales and support staff are on calls most of the day — they want
headsets and an easier-to-use phone, but we don't need anything fancy for them."*
→ A **phone-centric, touch+headset** signal → recommend the **COMfortel D-400**: colour
touch UI, LED BLF keys, and EHS headset support — a clear step up from the basic D-210
for heavy callers, without the premium cost of the D-600
([[product-selection-philosophy]]). *(Standard back-office desks can stay on D-210s;
execs/reception may warrant a D-600.)*

# Cross-Selling Opportunities

- **Headset:** EHS/DHSG wired headset (Jabra line, `teleprofi_fulda.md`) — the natural
  D-400 attach.
- **PBX / network / provider:** COMtrexx (`comtrexx-family.md`), switches/PoE
  (`teleprofi_fulda.md`), [[provider-preference-philosophy]] / `fritzbox-family.md`.
- **Expansion modules:** COMfortel **D-XT20i** (BLF-heavy desks).
- **Other tiers** for specific roles: `comfortel-d210.md` / `comfortel-d600.md` (to come).
- **Installation + maintenance:** `../services/telephone-system-installation.md`,
  `../services/maintenance-contract.md`.

# Related products

- [`comfortel-d210.md`](./comfortel-d210.md) — entry tier (no touch).
- `comfortel-d600.md` — premium tier (7″ touch + Bluetooth) (to come).
- `comtrexx-family.md` — the PBX the desk phones register to.
- `comfortel-m710.md` / `comfortel-m730.md` — the **cordless** (DECT) alternative for mobility.

# Related (reusable knowledge)

- Philosophy: [[product-selection-philosophy]], [[installation-philosophy]],
  [[firmware-policy]], [[maintenance-philosophy]].
- AI rules: `../ai-rules/provider-selection.md` (wider solution).
- Services: `../services/telephone-system-installation.md`, `../services/maintenance-contract.md`.

# Teleprofi Knowledge Needed

**Renato (commercial / selection):**
1. Real **desk-phone mix per site** — which roles get D-400 specifically, and the rough
   D-210/D-400/D-600 ratio? *(shared with the D-210 family question)*
2. Is the **D-400 the default "good phone"** for most staff, or reserved for
   phone-heavy roles only?
4. How often is a **headset** sold with the D-400 (attach rate), and which model?

**Patrick (technician / hands-on):**
3. Most common **D-400 support call** (provisioning, PoE, **EHS headset** config, keys)?
5. Any **EHS/DHSG headset** compatibility gotchas with the D-400.

# Knowledge History

| Version | Date | Change | Source |
|---|---|---|---|
| 0.1 | 2026-06-25 | Middle desk-phone tier: productivity (touch + LED keys + EHS headset) positioning, concise D-210/D-600 boundaries deferring to a future family, AI signals + conversation example + cross-selling; shared desk-phone mechanics referenced not duplicated | repo Teleprofi knowledge + official Auerswald + D-210 entry |

# Knowledge Confidence

| Area | Confidence | Reason |
|---|---|---|
| Mid-tier positioning + productivity features | high | official Auerswald product pages |
| Display / keys / EHS headset / no-Bluetooth | high | official Auerswald |
| Expansion to 80 keys | high | official Auerswald |
| Teleprofi per-role assignment / D-400 default-or-not | needs-confirmation | not captured — Q1/Q2 |
| Headset attach rate / model | needs-confirmation | Q4 |
| Support issues / EHS gotchas / checklist | needs-confirmation | Q3/Q5 + Patrick backlog |
| COMfortel device firmware scope in firmware-policy | needs-confirmation | open in [[firmware-policy]] |
