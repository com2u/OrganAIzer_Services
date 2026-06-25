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
