---
id: comfortel-d600
type: product
owner: unassigned
status: draft
knowledge_version: 0.1   # premium desk-phone tier; completes the D-series. Teleprofi gaps are interview questions
last_reviewed: 2026-06-25
sources:
  - backend/voice/knowledge/teleprofi_fulda.md            # primary: Teleprofi business knowledge (D-600 listed current)
  - Teleprofi operational knowledge (Renato, 2026-06-25)   # primary
  - knowledge/products/comfortel-d210.md                   # entry-tier sibling (shared desk-phone knowledge)
  - knowledge/products/comfortel-d400.md                   # mid-tier sibling
  - https://www.auerswald.de/en/product/comfortel-d-600    # supporting: official
category: phone
vendor: Auerswald
model: COMfortel D-600
lifecycle: current
---

# Auerswald COMfortel D-600 — Teleprofi product knowledge

> The **premium tier** of Teleprofi's Auerswald COMfortel desk-phone portfolio
> (D-210 → D-400 → **D-600**). This entry teaches **why Teleprofi picks the D-600 as the
> premium desk phone**. Shared desk-phone mechanics (COMtrexx provisioning, PoE/network)
> live in [`comfortel-d210.md`](./comfortel-d210.md) and will consolidate into a future
> **`deskphone-family.md`** — kept light and **referenced**, not duplicated. Reusable
> principles live in `business-philosophy/`.
>
> **Knowledge maturity: v0.1 (draft).** Teleprofi-specific gaps are precise questions
> under **[Teleprofi Knowledge Needed](#teleprofi-knowledge-needed)**.

# Executive Summary

**What is it?** The **top-of-line** COMfortel IP desk phone — a **7″ colour capacitive
touch display**, **40+ on-screen self-labelling keys** with status signalling, and
**Bluetooth as well as EHS headset** support (Auerswald). It registers to the COMtrexx
PBX.

**Who is it for?** **Executives, reception/operators, and power users** — roles that
justify the largest screen, the most at-a-glance keys, and a **wireless (Bluetooth)
headset**.

**Why does Teleprofi sell it?** It's the **current premium desk phone**
(`teleprofi_fulda.md`) — the right choice where the **role**, not the headcount, calls
for the best device ([[product-selection-philosophy]]: fit the role).

# Teleprofi Recommendation

Recommend the **D-600 for the few roles that need it** — executives, reception, heavy
multitaskers — not as a blanket fleet phone. The desk-phone choice is **role/feature-tier
driven**; the canonical tier ladder and per-role split will live in the future
`deskphone-family.md` (and the real Teleprofi mix is the open question — Q1). For most
desks the **D-210** or **D-400** is the right fit (below).

# Typical Customer

Businesses with **defined premium roles** on a COMtrexx system — a managing director, a
busy reception/switchboard, a customer-service lead (`teleprofi_fulda.md`). Usually the
**top layer** of a mixed fleet. (Real Teleprofi mix / how many D-600s per site —
Knowledge Needed Q1.)

# Typical Deployment

Wired desk phone: PoE Ethernet, provisioned/registered to the **COMtrexx PBX**
(`comtrexx-family.md`); a Bluetooth headset pairs to the phone. Provisioning/registration
is shared desk-phone behaviour — see [`comfortel-d210.md`](./comfortel-d210.md), Typical
Deployment (→ future family); not re-detailed here.

# Typical Bundle

Part of a complete workstation/telephony solution — referenced, not duplicated (same
structure as the D-210/D-400):

| Part | Reference |
|---|---|
| **PBX** | COMtrexx (`comtrexx-family.md`) |
| **Network** | switch / PoE / cabling (`teleprofi_fulda.md`) |
| **Provider + router** | [[provider-preference-philosophy]] / `fritzbox-family.md` |
| **Headset** | **Bluetooth** (or EHS) headset — the premium attach (Jabra line, `teleprofi_fulda.md`) |
| **Expansion modules** | COMfortel **D-XT20i** for additional BLF (reception) — confirm need vs the 40+ on-screen keys (Q2) |
| **Installation + maintenance** | `../services/telephone-system-installation.md`, `../services/maintenance-contract.md` |

Pricing → `pricing/`.

# Strengths

- **7″ colour capacitive touch** — the largest, richest D-series UI (Auerswald).
- **40+ on-screen self-labelling keys** with status signalling — strong BLF/operator
  capability **without** add-on modules (Auerswald).
- **Bluetooth + EHS headset** — wireless freedom of movement at the desk (Auerswald).
- Premium fit-and-finish; native COMtrexx/COMfortel integration.

# Limitations

- **Premium price** — over-spec for ordinary desks (use D-210/D-400).
- Wired desk phone — true mobility is DECT (`ws-500s.md` + M-710/M-730), not this product;
  the D-600's "mobility" is **Bluetooth-headset freedom at the desk**, not roaming.
- More device surface (touch, Bluetooth) to support than the lower tiers.

# Executive / Reception / Power-user scenarios

- **Executive:** large touch screen, Bluetooth headset, status at a glance — a phone that
  matches the role and is effortless to use.
- **Reception / operator:** the **40+ on-screen BLF keys** let a receptionist monitor and
  transfer across many extensions on one screen; the touch UI speeds call handling.
  *(For a budget operator desk, a D-210 + key modules is the alternative — the
  D-210-modules-vs-D-600 reception choice is an open Teleprofi question, Q2.)*
- **Power user:** heavy multitasking caller who benefits from the best UI + wireless
  headset.

# Productivity Features

The D-600's reasons to exist over the D-400:
- **7″** screen vs 4.3″ — more content/keys visible at once.
- **40+ on-screen keys** vs 20 physical — richer BLF/operator view without modules.
- **Bluetooth** headset (in addition to EHS) — wireless, not just wired.

# Bluetooth and mobility workflow

The D-600 supports a **Bluetooth headset** for hands-free handling and **freedom of
movement around the desk/immediate area** while on a call (Auerswald). This is
**desk-area** convenience, **not** site-wide roaming — for staff who must move through a
building on calls, the answer is **DECT** (`ws-500s.md` + M-710/M-730), not a desk phone.
*(Any Bluetooth mobile-device pairing beyond the headset use case — confirm; not asserted.)*

# Expansion Possibilities

The 40+ on-screen keys cover most BLF needs without add-ons; COMfortel **D-XT20i** modules
can extend further for the largest operator desks (confirm module support/limits for the
D-600 — official detail, Q-official).

# When Teleprofi recommends the D600

Specific premium roles — **executive, reception/operator, power user** — needing the 7″
touch UI, many on-screen BLF keys, and/or a **Bluetooth** headset.

# When D400 is sufficient

Phone-centric users who want **touch + a (wired EHS) headset** but not the 7″ screen,
Bluetooth, or 40+ keys — see [`comfortel-d400.md`](./comfortel-d400.md). *(Full tier
ladder → future `deskphone-family.md`.)*

# When D210 is sufficient

Standard/occasional-call desks and **cost-sensitive fleets** — see
[`comfortel-d210.md`](./comfortel-d210.md). *(Full tier ladder → future `deskphone-family.md`.)*

# Common customer questions

- "What makes it worth the premium?" → 7″ touch, 40+ on-screen keys, Bluetooth headset.
- "Can the receptionist see/transfer all our lines on it?" → yes — 40+ BLF keys on screen.
- "Can I use a wireless headset?" → yes, Bluetooth (the D-400 is wired EHS only).
- "Can our exec walk around the building on it?" → only desk-area (Bluetooth headset); for
  building-wide mobility you need DECT cordless.

# Typical support issues

Desk-phone support: provisioning/registration to COMtrexx, PoE/network, **Bluetooth/EHS
headset** pairing/config, touch-UI/key setup, firmware — shared across the D-series (→
future family; `comfortel-d210.md`, Typical support issues), with **Bluetooth pairing** as
a D-600-specific add. (Most common D-600 support call — Knowledge Needed Q3.)

# Installation expectations

Provision/register to COMtrexx, PoE connect, pair Bluetooth headset, configure keys/UI;
validate per [[installation-philosophy]] (`services/telephone-system-installation.md`).
Shared desk-phone process (→ future family). (Checklist — Patrick backlog.)

# Maintenance expectations

Firmware per [[firmware-policy]] (proven-stable; updates as a billed service per
[[maintenance-philosophy]]). Slightly more surface (touch, Bluetooth) than lower tiers;
otherwise low-touch wired device.

# Firmware / update policy

Shared [[firmware-policy]] — only proven-stable firmware, evaluated first; updates as a
billed service. Not restated here. *(COMfortel device firmware scope is the open question
already tracked in [[firmware-policy]].)*

# AI Recommendation Signals

**Lean D-600** on a **premium-role** signal — executive, reception/operator (many BLF),
power user, or an explicit **wireless/Bluetooth headset** or **large touchscreen** need.
**Lean D-400** on a **touch + wired-headset** signal without the premium need; **lean
D-210** on a **standard/cost-sensitive** signal. Decisive axis = **role / feature tier**,
not user count. Reserve the D-600 for roles that justify it
([[product-selection-philosophy]]).

# AI Conversation Example

Customer: *"Our managing director wants the best phone with a wireless headset, and our
receptionist handles every incoming call and needs to see who's free across the whole
company."*
→ Two **premium-role** signals → recommend the **COMfortel D-600** for both: the MD gets
the 7″ touch UI and a **Bluetooth** headset; reception gets **40+ on-screen BLF keys** to
monitor and transfer across all extensions ([[product-selection-philosophy]]). *(The rest
of the staff don't need this — standard desks on D-210, phone-heavy roles on D-400.)*

# Cross-Selling Opportunities

- **Headset:** **Bluetooth** (or EHS) headset (Jabra line, `teleprofi_fulda.md`) — the
  premium attach.
- **PBX / network / provider:** COMtrexx (`comtrexx-family.md`), switches/PoE
  (`teleprofi_fulda.md`), [[provider-preference-philosophy]] / `fritzbox-family.md`.
- **Expansion modules:** COMfortel **D-XT20i** for the largest operator desks.
- **Other tiers** for the rest of the fleet: `comfortel-d210.md` / `comfortel-d400.md`.
- **Installation + maintenance:** `../services/telephone-system-installation.md`,
  `../services/maintenance-contract.md`.

# Related products

- [`comfortel-d210.md`](./comfortel-d210.md) — entry tier (no touch).
- [`comfortel-d400.md`](./comfortel-d400.md) — mid tier (4.3″ touch + EHS headset).
- `comtrexx-family.md` — the PBX the desk phones register to.
- `comfortel-m710.md` / `comfortel-m730.md` — the **cordless** (DECT) alternative for true mobility.

# Related (reusable knowledge)

- Philosophy: [[product-selection-philosophy]], [[installation-philosophy]],
  [[firmware-policy]], [[maintenance-philosophy]].
- AI rules: `../ai-rules/provider-selection.md` (wider solution).
- Services: `../services/telephone-system-installation.md`, `../services/maintenance-contract.md`.

# Teleprofi Knowledge Needed

**Renato (commercial / selection):**
1. Real **desk-phone mix per site** — which roles get the D-600, and **how many** per
   typical site? *(shared with the D-210/D-400 family question)*
2. For **reception/operator**, does Teleprofi prefer a **D-600** (40+ on-screen keys) or a
   **D-210 + key modules**, and why?
4. Is the D-600 ever recommended **beyond execs/reception** (e.g. a customer who just
   wants "the best for everyone")?

**Patrick (technician / hands-on):**
3. Most common **D-600 support call** (provisioning, PoE, **Bluetooth** pairing, touch UI)?
5. Any **Bluetooth/EHS headset** pairing gotchas with the D-600.

# Knowledge History

| Version | Date | Change | Source |
|---|---|---|---|
| 0.1 | 2026-06-25 | Premium desk-phone tier completing the D-series: executive/reception/power-user scenarios, Bluetooth/desk-mobility workflow, concise D-210/D-400 boundaries deferring to a future family, AI signals + conversation example + cross-selling; shared desk-phone mechanics referenced not duplicated | repo Teleprofi knowledge + official Auerswald + D-210/D-400 entries |

# Knowledge Confidence

| Area | Confidence | Reason |
|---|---|---|
| Premium positioning + 7″ touch / 40+ keys / Bluetooth | high | official Auerswald product page |
| Productivity/headset tier differences vs D-400/D-210 | high | official Auerswald |
| Bluetooth = desk-area headset freedom (not roaming) | high | official + DECT contrast |
| Teleprofi per-role assignment / D-600 count per site | needs-confirmation | not captured — Q1 |
| Reception: D-600 vs D-210+modules preference | needs-confirmation | Q2 |
| D-XT20i module support/limits on the D-600 | needs-confirmation | official detail to confirm |
| Support issues / Bluetooth pairing gotchas / checklist | needs-confirmation | Q3/Q5 + Patrick backlog |
| COMfortel device firmware scope in firmware-policy | needs-confirmation | open in [[firmware-policy]] |
