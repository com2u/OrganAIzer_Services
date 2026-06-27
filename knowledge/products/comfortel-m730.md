---
id: comfortel-m730
type: product
owner: unassigned
status: draft
knowledge_version: 0.1   # first endpoint entry; sets the phone standard. Teleprofi-specific gaps are interview questions
last_reviewed: 2026-06-25
sources:
  - backend/voice/knowledge/teleprofi_fulda.md           # primary: Teleprofi business knowledge
  - Teleprofi operational knowledge (Renato, 2026-06-25)  # primary
  - https://www.auerswald.de/de/support/produkt/comfortel-m-730/support   # supporting: official
  - https://www.auerswald.de/de/produkt/comfortel-m-710                    # supporting: official (sibling)
category: dect
vendor: Auerswald
model: COMfortel M-730
lifecycle: current
---

# Auerswald COMfortel M-730 — Teleprofi product knowledge

> Captures **Teleprofi's** knowledge of when, why and how it sells, installs and
> supports the COMfortel M-730 DECT handset. This is the **first endpoint entry**
> and sets the pattern for future phones: Teleprofi-first, reuse reusable knowledge,
> document only what's unique. Reusable reasoning (selection / growth / financing /
> firmware / installation / maintenance / provider) lives in `business-philosophy/`
> and is **referenced, not repeated**.
>
> **Knowledge maturity: v0.1 (draft).** Built from repository Teleprofi knowledge,
> official Auerswald data, and existing philosophy. Teleprofi-specific operational
> detail is captured as precise questions under
> **[Teleprofi Knowledge Needed](#teleprofi-knowledge-needed)**.

# Executive Summary

**What is this product?**
The COMfortel M-730 is Auerswald's **rugged DECT cordless handset** — IP65-rated
(dust-tight, protected against water jets), disinfectant-resistant, with a 2.4″
colour display (Auerswald). It registers to Auerswald DECT bases (e.g. WS-500S/M)
behind a COMtrexx PBX.

**Why does Teleprofi sell it?**
Because it's the **current** Auerswald DECT handset for **demanding environments**
(`teleprofi_fulda.md` lists M-730 as current) — where a normal office handset would
not survive: workshops, warehouses, outdoors, wet/dusty areas, and hygiene-sensitive
settings. It fits Teleprofi's reliability-first approach ([[installation-philosophy]]).

**Who is it for?**
Customers who need cordless mobility **in tough conditions** — not the cheapest
office handset, but the one that lasts where ruggedness, water/dust resistance, or
disinfectant-wipe hygiene matter.

# Teleprofi Recommendation

The M-730 is the **rugged** option in Teleprofi's current Auerswald DECT line-up;
the M-710 is the office/entry option (see "When Teleprofi recommends the M-710
instead"). The choice is driven by **environment**, not headcount.

- Recommend **M-730** when the working environment is harsh (dust, moisture,
  outdoors, drops) or hygiene-critical (disinfectant wiping).
- It is a premium handset — price-per-handset is higher than the M-710, so it is
  recommended where the environment justifies it, not by default
  ([[product-selection-philosophy]]: fit first, not cheapest-by-default).

> Teleprofi's actual M-730-vs-M-710 split and the environments where it insists on
> M-730 are not yet captured — see Knowledge Needed Q1.

# Typical Customer

- Businesses with **field/floor mobility in rough conditions**: workshops,
  warehouses, logistics, production, outdoor/yard work; and **hygiene-sensitive**
  settings (medical/care/food) where handsets are wiped with disinfectant.
- Often the same customers Teleprofi already serves for telephony/DECT
  (`teleprofi_fulda.md`) — the M-730 is the handset for the subset working in tough
  areas. (Specific industries to confirm — Knowledge Needed Q2.)

# Typical Deployment

DECT mobility on top of an existing or new Auerswald telephony install: one or more
Auerswald DECT bases (WS-500S/M) for coverage, with M-730 handsets registered to
them and routed through the COMtrexx PBX. Teleprofi's DECT work routinely includes
**coverage planning, coverage testing, device registration and user onboarding**
(`teleprofi_fulda.md`, DECT Infrastructure) — the M-730 slots into that process.
(Typical handset counts / multi-base roaming patterns to confirm — Knowledge Needed Q3.)

# Typical Bundle

The M-730 is an endpoint within a complete Teleprofi solution; it is **referenced**
alongside the other parts, never sold as an island:

| Part of the bundle | Reference (not duplicated) |
|---|---|
| **PBX** | COMtrexx (`comtrexx-family.md`; `comtrexx-next.md` / `comtrexx-flex.md`) |
| **DECT base(s)** | Auerswald WS-500S/M (DECT coverage; `products/` entry to come) |
| **Provider SIP trunk + router** | per [[provider-preference-philosophy]] (`providers/`) |
| **Licensing** | each handset registers as a device/user on COMtrexx — consumes floating user licences (`comtrexx-family.md`); no separate per-handset licence logic restated here |
| **Headset (optional)** | Bluetooth or 3.5 mm headset for hands-free (Teleprofi headset line: Jabra, `teleprofi_fulda.md`) |
| **Installation / DECT survey / maintenance** | `services/dect-site-survey.md`, `services/telephone-system-installation.md`, `services/maintenance-contract.md` |

See `solutions/` for composed deployments. Pricing lives in `pricing/`.

# Strengths

- **Rugged: IP65** (dust-tight, water-jet resistant) and robust housing (Auerswald).
- **Disinfectant-resistant** — suited to hygiene-critical settings (Auerswald).
- **2.4″ colour display**; Bluetooth, Micro-USB, 3.5 mm jack (Auerswald).
- Battery up to ~**12 h talk / 320 h standby** (Auerswald).
- Native Auerswald DECT integration with COMtrexx and COMfortel ecosystem.

# Limitations

- **Premium price per handset** vs. the M-710 — not the choice for plain office use
  or large cost-sensitive fleets (see M-710 below).
- Like any DECT handset, depends on adequate **base coverage** (a survey concern,
  not a handset flaw).
- Battery is a **consumable** — capacity degrades over the handset's life.

# When Teleprofi recommends the M-730

Harsh or hygiene-critical environments: workshop/warehouse/production floors,
outdoor/yard use, wet or dusty areas, drop-risk, or disinfectant-wipe hygiene
(medical/care/food). The **environment** is the trigger.

# When Teleprofi recommends the M-710 instead

Normal **office/indoor** use, and especially **cost-sensitive fleets with many
handsets** — the M-710 is the entry-level office DECT handset, attractive on price
for installations with many devices (Auerswald). If ruggedness/IP65/disinfectant
resistance is not needed, the M-710 is the right-sized, cheaper choice
([[product-selection-philosophy]]). *(A dedicated `comfortel-m710.md` follows in
Phase 1.)*

# Common customer questions

- "What's the difference between the M-730 and the M-710?" → ruggedness/IP65 +
  disinfectant resistance + colour display vs. cost-effective office handset.
- "Can it handle our workshop/warehouse/outdoors?" → yes, that's its purpose (IP65).
- "Can we wipe it with disinfectant?" → yes (disinfectant-resistant).
- "How long does the battery last?" → up to ~12 h talk / 320 h standby (Auerswald).
- "Does it work with our Auerswald system?" → yes, via Auerswald DECT bases + COMtrexx.

# Typical support issues

DECT-handset support tends to be: **registration/pairing** to the base,
**coverage/roaming** gaps (handover between bases), **battery wear** over time, and
firmware. These map to Teleprofi's known wireless issues — coverage, roaming,
registration (`teleprofi_fulda.md`). Triage via the DECT survey/coverage process.
(Teleprofi's most common M-730 support call is not yet captured — Knowledge Needed Q4.)

# Installation expectations

Part of Teleprofi's DECT deployment: **site survey → coverage testing → base
placement → handset registration → user onboarding** (`teleprofi_fulda.md`;
`services/dect-site-survey.md`), preconfigured and validated per
[[installation-philosophy]]. Rugged handsets are typically deployed where coverage
must reach difficult areas — so coverage testing matters more, not less. (Exact
Teleprofi DECT preconfig/bench/onboarding checklist — Patrick backlog.)

# Maintenance expectations

- **Firmware:** handled per [[firmware-policy]] (only proven-stable; updates as a
  billed service via [[maintenance-philosophy]]). *(Whether the firmware-policy
  version table covers COMfortel **device** firmware as well as COMtrexx system
  firmware is an open question already tracked in [[firmware-policy]].)*
- **Battery:** a consumable — plan for eventual battery replacement across a fleet.

# Firmware / update policy

Governed by the shared [[firmware-policy]] — Teleprofi deploys only proven-stable
firmware and evaluates releases first; updates are a billed service. Not restated
here.

# AI Recommendation Signals

> Business reasoning only — not a product description, not an AI prompt.

**Lean M-730** when the customer signals a **demanding environment**: dust, moisture,
outdoors, drop-risk, workshop/warehouse/production, or hygiene/disinfectant needs.
**Lean M-710** for ordinary office use, especially **many handsets on a budget**.
Decisive signal = **environment/ruggedness**, not user count. If cost is the only
objection to ruggedness the customer genuinely needs, don't downgrade on price alone
([[product-selection-philosophy]]); financing options apply to the wider solution
([[financing-philosophy]]).

# AI Conversation Example

Customer: *"Our warehouse and yard staff use cordless phones, but they keep getting
dropped, dusty, and one died after getting rained on."*
→ This is a **rugged-environment** signal. Recommend the **COMfortel M-730** over the
office-grade M-710: its **IP65** housing handles dust and water jets and tolerates
drops, so it survives warehouse/yard conditions that kill an office handset. Frame it
as fit-for-environment, not an upsell — the M-710 would simply fail there
([[product-selection-philosophy]]). Confirm DECT coverage reaches the yard (a survey
item, `services/dect-site-survey.md`).

# Cross-Selling Opportunities

Natural follow-ons an experienced Teleprofi consultant would attach (referenced, not
described here):

- **DECT base(s):** Auerswald **WS-500S/M** — required for coverage (`products/` to come).
- **PBX:** COMtrexx (`comtrexx-family.md`) if not already in place.
- **Provider + router:** per [[provider-preference-philosophy]] (`providers/`).
- **Headset:** Bluetooth / 3.5 mm headset (Jabra line, `teleprofi_fulda.md`).
- **DECT site survey:** `../services/dect-site-survey.md` — coverage into difficult/rugged areas.
- **Installation:** `../services/telephone-system-installation.md`.
- **Maintenance contract:** `../services/maintenance-contract.md` (firmware/batteries).
- **Training / onboarding:** user onboarding (`teleprofi_fulda.md`, DECT onboarding).

# Related products

- `comfortel-m710.md` — the office/entry DECT handset (cost-effective at scale).
- Auerswald **WS-500S/M** DECT bases (required for coverage; `products/` entry to come).
- `comtrexx-family.md` / `comtrexx-next.md` / `comtrexx-flex.md` — the PBX the
  handset routes through.

# Related (reusable knowledge)

- Philosophy: [[product-selection-philosophy]], [[installation-philosophy]],
  [[firmware-policy]], [[maintenance-philosophy]], [[financing-philosophy]],
  [[provider-preference-philosophy]].
- Services: `../services/dect-site-survey.md`,
  `../services/telephone-system-installation.md`, `../services/maintenance-contract.md`.
- Solutions: `../solutions/` (DECT/mobility deployments).

# Teleprofi Knowledge Needed

> Interview questions. Answers update this entry (and, where reusable, philosophy or
> a future DECT entry).

**Renato (commercial / selection):**
1. What is Teleprofi's actual **M-730 vs. M-710 split** — which environments make you
   insist on the M-730?
2. Which **industries/customers** typically take the M-730 (medical/care/food,
   logistics, trades)?
3. Typical **handset counts** and whether multi-base **roaming** is common.
7. How often is a DECT/handset order **bundled with a DECT site survey** as standard?

**Patrick (technician / hands-on):**
4. Most common **M-730 support call** in practice (registration, coverage, battery)?
5. Teleprofi's **DECT preconfig / registration / onboarding checklist** for handsets.
6. Any **base/handset firmware** pairing gotchas (ties to [[firmware-policy]] scope Q).

# Knowledge History

| Version | Date | Change | Source |
|---|---|---|---|
| 0.1 | 2026-06-25 | First endpoint entry (sets the phone standard): rugged-vs-office positioning, typical bundle by reference, AI signals + conversation example; Teleprofi gaps as questions | repo Teleprofi knowledge + official Auerswald + philosophy |
| 0.1 | 2026-06-25 | Added Cross-Selling Opportunities section (new phone-standard section) | repo + philosophy |

# Knowledge Confidence

| Area | Confidence | Reason |
|---|---|---|
| M-730 vs. M-710 positioning (rugged vs. office) | high | official Auerswald product pages |
| Ruggedness / IP65 / display / battery specs | high | official Auerswald |
| Typical bundle (by reference) | medium | structurally sound; per-deployment specifics to confirm |
| When Teleprofi insists on M-730 (real split) | needs-confirmation | not captured — Q1/Q2 |
| Typical support issues / install checklist | needs-confirmation | Q4 + Patrick backlog |
| Firmware version scope for device firmware | needs-confirmation | open in [[firmware-policy]] |
| DECT base compatibility detail (WS-500 vs. others) | needs-confirmation | base entries not yet written |
