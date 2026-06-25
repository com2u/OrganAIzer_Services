---
id: example-infrastructure
type: infrastructure
owner: unassigned
status: draft
last_reviewed: 2026-06-24
sources:
  - docker-compose.yml
  - backend/voice/config.py
  - backend/voice/freeswitch/README.md
---

# <Infrastructure Component>

> One-line description of the component.

> One source of truth: **reference** the authoritative source for every value.
> Do NOT copy ports, IPs, env vars, or COMtrexx parameters into this file — link
> to where they actually live so this entry can never drift.

## Overview

<What the component is and its role in the system.>

## Authoritative sources

<List each fact and where it is defined, e.g.:
- Published ports → `docker-compose.yml`
- Env vars → `backend/voice/config.py` + `backend/.env.example`
- COMtrexx / orbits (003010, 778, 779) → `backend/voice/freeswitch/README.md`>

## Related procedures

<Link to `procedures/` runbooks for operating or validating this component.>

## Notes

<Known limitations, drift risks, manual-validation needs.>
