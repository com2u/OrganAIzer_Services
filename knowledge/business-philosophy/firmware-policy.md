---
id: firmware-policy
type: philosophy
owner: unassigned
status: active
last_reviewed: 2026-06-25
sources:
  - Teleprofi operational knowledge (Renato, 2026-06-25)
  - backend/voice/knowledge/teleprofi_fulda.md
---

# Teleprofi Firmware Policy

> Reusable policy. Products reference this for firmware handling instead of
> restating it. See also [[installation-philosophy]].

## Policy

**Stability is more important than always having the newest version.**

- New firmware is **not** installed immediately after release.
- New releases are **evaluated first**.
- Only firmware that has **proven stable** is deployed to customer systems.

Firmware updates and ongoing maintenance are offered as a **professional service**,
billed where applicable — keeping customer systems stable and current is part of the
long-term relationship, not an afterthought. (See `services/maintenance-contract.md`,
`services/remote-support.md`; pricing lives in `pricing/`.)

> **CANDIDATE ADDITION — Teleprofi interview draft, unconfirmed.**
> **Requires Patrick/Renato confirmation before merge.**
>
> ### What "stable" means (candidate refinement)
>
> Candidate framing: a firmware is not approved simply because it is the
> newest. "Stable" should mean: Herstellerhinweise wurden geprüft; bekannte
> Fehler sind akzeptabel; relevante Funktionen wurden intern oder bei
> geeigneten Referenzsystemen getestet; Backup und Rückfall sind möglich;
> die Version ist für die jeweilige Kundenumgebung freigegeben. Candidate
> update-timing guidance: install when there's a security fix, a known bug
> affecting the customer, a needed function only available in the update, or
> vendor support/compatibility requires it — within a planned maintenance
> window after checking release notes, backup and rollback. Hold off right
> after a major release, on critical systems without a confirmed need, when
> known bugs have been reported, when in-use endpoints/interfaces aren't yet
> confirmed compatible, or without a suitable maintenance/rollback window.
>
> **This candidate content does NOT resolve the open question below** — the
> source draft explicitly declines to state which firmware versions are
> stable, and never addresses whether the table below is COMtrexx system
> firmware or COMfortel device firmware. That confirmation is still needed
> from Patrick.
>
> Source: Teleprofi candidate interview-answer document (unconfirmed,
> 2026-07-22), Interview 4 "FIRMWARE".

## COMtrexx firmware status

> **Teleprofi operational experience — NOT an official Auerswald recommendation.**
> Reflects what Teleprofi has observed in customer deployments and must be
> re-validated over time.

| Version | Status (Teleprofi experience) |
|---|---|
| **2.4.6** | Considered **stable**; safe for customer deployments. |
| **2.6.1** | Has produced issues in practice; **not recommended** until validated. |
| **2.6.2** | Has produced issues in practice; **not recommended** until validated. |

> Applies to the COMtrexx family (e.g. `products/comtrexx-next.md`, and
> `comtrexx-flex.md` when created). Update this table as Teleprofi validates newer
> versions. **Needs Human Confirmation:** whether these version numbers are COMtrexx
> system firmware or COMfortel device firmware — confirm with Renato.

## Why

A small technician team supporting many customer sites cannot afford avoidable
firmware regressions. Deploying only proven-stable firmware minimises callbacks and
downtime, consistent with [[installation-philosophy]].
