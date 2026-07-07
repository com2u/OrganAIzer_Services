# Scheduler Demo Calendar Seeding Guide

> **Status:** Implementation complete. Seeding script + comprehensive test suite, all 308 scheduler/phone tests passing.

## Overview

The `seed_scheduler_demo_calendar.py` script populates the Scheduler JSONL store with realistic fake appointments for testing and evaluation. This enables realistic appointment-testing scenarios without touching any external APIs (Google Calendar, Outlook, email, etc.).

All seeded appointments are:
- ✅ Marked `status="simulated"`
- ✅ Within business hours (Mon–Thu 8–16, Fri 8–13, no weekends)
- ✅ Using masked phone numbers only (never raw)
- ✅ Distributed across all 6 appointment types
- ✅ Conflict-free (no overlapping appointments per resource)
- ✅ Idempotent (safe to run repeatedly)

---

## Files Added

### Seeding Script
- **`backend/scripts/seed_scheduler_demo_calendar.py`** (260 lines)
  - Generates 18 fake appointments spanning 2 weeks
  - Idempotent: checks for `source="scheduler_demo_seed"` marker, skips if present unless `--force`
  - Supports dry-run, custom output path, deterministic output

### Tests
- **`backend/tests/test_scheduler_seeding.py`** (400 lines)
  - 17 test classes covering:
    - Business hours validation (no weekends, within hours)
    - Status & schema validation (all `status="simulated"`)
    - Phone number masking (no raw numbers, all masked)
    - Appointment type distribution (all 6 types covered, 3+ per type)
    - Conflict detection (no overlapping slots)
    - Idempotency (safe repeated runs)
    - Determinism & repeatability
    - Data quality (realistic names, topics, companies)
  - **All 17 tests passing** ✅

---

## Usage

### Basic: Seed the default store

```bash
cd backend
../.venv-wsl/bin/python scripts/seed_scheduler_demo_calendar.py
```

**Output:**
```
🌱 Seeding Scheduler demo calendar
📍 Store: /mnt/c/Users/rxhec/OrganAIzer_Services/backend/data/scheduler/appointments.jsonl
✅ Seeded 18 appointments to ...
📁 Store size: 10883 bytes
```

### Dry-run: Preview without writing

```bash
../.venv-wsl/bin/python scripts/seed_scheduler_demo_calendar.py --dry-run
```

**Output:**
```
📋 DRY RUN: would seed 18 appointments to ...

  callback                  Max Mustermann       Mon 08:30
  callback                  Erika Musterfrau     Tue 09:00
  callback                  Stefan Bauer         Wed 09:30
  ...
```

### Force re-seed: Ignore idempotency marker

```bash
../.venv-wsl/bin/python scripts/seed_scheduler_demo_calendar.py --force
```

### Custom output path

```bash
../.venv-wsl/bin/python scripts/seed_scheduler_demo_calendar.py --path /tmp/demo.jsonl
```

### Help

```bash
../.venv-wsl/bin/python scripts/seed_scheduler_demo_calendar.py --help
```

---

## Where Seeded Appointments Are Stored

### Default location:
```
backend/data/scheduler/appointments.jsonl
```

This is the SAME store used by live phone calls and testing. The seeding script uses the Scheduler service layer (`create_simulated_appointment`) to append records, just like the phone AI does.

### Example record (one per line):

```json
{
  "status": "simulated",
  "schema_version": "0.1",
  "id": "eb2fb519-e30f-461a-9d70-5cac3b03bb34",
  "created_at": "2026-07-06T22:18:55Z",
  "source": "scheduler_demo_seed",
  "caller_name": "Max Mustermann",
  "company": "Acme GmbH",
  "phone_masked": "+493******6789",
  "topic": "Anruf bezüglich Angebot",
  "appointment_type": "callback",
  "selected_slot_start": "2026-07-06T08:30:00",
  "selected_slot_end": "2026-07-06T09:00:00",
  "assigned_resource": "remote_support_queue",
  "confirmation_summary": null,
  "call_id": "bc0c7471-27e5-4325-b007-e96cd9b5876e"
}
```

---

## Example: Seeded Appointments (Current)

As of 2026-07-06, after running `--force` seed:

| Date | Time | Type | Caller | Company | Topic | Resource |
|------|------|------|--------|---------|-------|----------|
| 2026-07-06 | 09:00 | on_site_visit_request | Max Mustermann | Digital Solutions | Neue Installation | technician_sim_1 |
| 2026-07-06 | 08:30 | callback | Max Mustermann | Acme GmbH | Anruf bezüglich Angebot | remote_support_queue |
| 2026-07-07 | 09:00 | callback | Erika Musterfrau | TechStart AG | Rückruf für Beratung | remote_support_queue |
| 2026-07-07 | 09:30 | on_site_visit_request | Erika Musterfrau | Cloud Services Ltd. | Verkabelungs-Projekt | technician_sim_1 |
| 2026-07-08 | 09:30 | callback | Stefan Bauer | Innovation Labs | Terminbestätigung | remote_support_queue |
| 2026-07-08 | 10:00 | sales_consultation | Stefan Bauer | Smart Networks | Anfrage zu neuen Produkten | sales_queue |
| 2026-07-09 | 10:00 | remote_support | Anna Schmidt | Digital Solutions | VPN Setup Unterstützung | remote_support_queue |
| 2026-07-09 | 10:30 | sales_consultation | Anna Schmidt | (none) | Lizenz-Upgrade Gespräch | sales_queue |
| 2026-07-10 | 10:30 | remote_support | Thomas Weber | Cloud Services Ltd. | Fernwartung für Netzwerk | remote_support_queue |
| 2026-07-10 | 11:00 | sales_consultation | Thomas Weber | Acme GmbH | Vertriebsgespräch | sales_queue |
| 2026-07-13 | 11:00 | remote_support | Julia Müller | Smart Networks | Fernzugriff zur Fehlersuche | remote_support_queue |
| 2026-07-13 | 11:30 | maintenance_request | Julia Müller | TechStart AG | Support-Vertrag anpassen | technician_sim_1 |
| 2026-07-14 | 11:30 | technical_consultation | Robert Fischer | (none) | Optimierungsgespräch | technician_sim_1 |
| 2026-07-14 | 12:00 | maintenance_request | Robert Fischer | Innovation Labs | Wartungsvertrag verlängern | technician_sim_1 |
| 2026-07-15 | 12:00 | technical_consultation | Sandra Wagner | Acme GmbH | Sicherheits-Review | technician_sim_1 |
| 2026-07-15 | 12:30 | maintenance_request | Sandra Wagner | Digital Solutions | Präventive Wartung | technician_sim_1 |
| 2026-07-16 | 12:30 | technical_consultation | Klaus Hoffmann | TechStart AG | Technische Beratung zu Netzwerk | technician_sim_1 |
| 2026-07-17 | 08:30 | on_site_visit_request | Petra Schönberg | Innovation Labs | Hardware-Austausch erforderlich | technician_sim_1 |

**Summary:**
- **18 appointments seeded** across 2 weeks (Mon 2026-07-06 through Wed 2026-07-17)
- **All 6 types** represented (callback ×3, remote_support ×3, technical_consultation ×3, on_site_visit_request ×3, sales_consultation ×3, maintenance_request ×3)
- **Business hours respected** (no weekend, all times within Mon–Thu 8–16 or Fri 8–13)
- **No conflicts** (no overlapping times per resource)
- **Realistic data** (fake German names, companies, topics)
- **All masked** (no raw phone numbers visible)

---

## Safety & Testing

### Seeding Tests: All Passing ✅

```bash
cd backend
../.venv-wsl/bin/python -m pytest tests/test_scheduler_seeding.py -v
```

**Result: 17 passed in 0.47s**

Tests validate:
- ✅ Business hours (no weekends, within hours)
- ✅ Status (all `"simulated"`)
- ✅ Schema version (all `"0.1"`)
- ✅ Phone masking (no raw numbers in store)
- ✅ Appointment type distribution (all 6 types, 3+ per type)
- ✅ No conflicts (no overlapping per resource)
- ✅ Idempotency (second run skips, `--force` re-seeds)
- ✅ Determinism (same date → same slots)
- ✅ Seeding marker (all records have `source="scheduler_demo_seed"`)
- ✅ Dry-run (prints but doesn't write)
- ✅ Data quality (realistic names, topics, companies)

### Integration Tests: All Passing ✅

```bash
cd backend
../.venv-wsl/bin/python -m pytest tests/test_scheduler*.py tests/test_phone_safety.py tests/test_voice_bugs_regression.py -v
```

**Result: 308 passed in 15.99s**

Includes:
- All existing scheduler service tests
- All phone safety tests
- All voice regression tests
- All new seeding tests

---

## Design Notes

### Idempotency

The seeding script is **safe to run repeatedly**:

1. **First run:** Seeds 18 appointments, each with `source="scheduler_demo_seed"`
2. **Second run:** Detects the marker, skips (returns count=0)
3. **With `--force`:** Clears marker detection, re-seeds from scratch

This prevents accidental duplication when running tests or demos multiple times.

### Phone Number Masking

- **Raw numbers** (e.g., `+4930123456789`) are NEVER stored
- **Masking** happens in `create_simulated_appointment()` (service layer)
- **Stored form** is masked (e.g., `+493******6789`)
- **Test validation** confirms no raw numbers in the JSONL file

### Business Hours Enforcement

The seeding script respects the Scheduler's business hours:

```python
BUSINESS_HOURS = {
    0: (time(8, 0), time(16, 0)),   # Monday
    1: (time(8, 0), time(16, 0)),   # Tuesday
    2: (time(8, 0), time(16, 0)),   # Wednesday
    3: (time(8, 0), time(16, 0)),   # Thursday
    4: (time(8, 0), time(13, 0)),   # Friday
    # 5, 6: closed (weekends)
}
```

All seeded appointments fall within these hours on working days only.

### No External APIs

The seeding script:
- ❌ Does NOT call Google Calendar
- ❌ Does NOT call Outlook
- ❌ Does NOT send emails
- ❌ Does NOT contact FreeSWITCH/COMtrexx
- ✅ ONLY writes to local JSONL file
- ✅ Uses Scheduler service layer (same as phone AI)

---

## Use Cases

### 1. Testing Appointment Conflicts

```python
from scheduler import list_available_slots
from datetime import date

# Seeded calendar makes conflicts realistic
day = date(2026, 7, 6)
slots = list_available_slots(day, "callback")  # Fewer slots available!
```

### 2. Realistic QA Testing

When testing the phone AI:
1. Run `python scripts/seed_scheduler_demo_calendar.py`
2. Call extension 003010
3. Try to book an appointment — some slots are already taken!
4. AI can only offer the free slots (realistic, not "everything is free")

### 3. Evaluation Framework Testing

When running the AI phone evaluation:
1. Seed the calendar
2. Call with appointment intent
3. AI offers realistic (constrained) availability
4. Caller can only pick from truly available slots

### 4. Load Testing

With 18 pre-filled appointments:
- Test conflict prevention
- Test duplicate prevention (same caller, same time)
- Test availability calculation efficiency

---

## What's NOT Implemented (Still Simulation-Only)

✅ **Seeding:** ✅ DONE
✅ **JSONL Storage:** ✅ DONE
✅ **Business Hours Validation:** ✅ DONE
✅ **Phone Masking:** ✅ DONE
✅ **Idempotency:** ✅ DONE
✅ **Test Coverage:** ✅ DONE (17 tests, all passing)

❌ **Google Calendar Write** — Not yet connected (next phase)
❌ **Outlook Integration** — Not yet connected (next phase)
❌ **Email Notifications** — Appointments don't trigger emails yet
❌ **Real Booking** — All appointments remain `status="simulated"`
❌ **CRM Sync** — No integration to CRM systems

---

## Running Tests

### Seeding tests only:
```bash
cd backend
../.venv-wsl/bin/python -m pytest tests/test_scheduler_seeding.py -v
```

### Scheduler test suite (all seeding + existing scheduler tests):
```bash
cd backend
../.venv-wsl/bin/python -m pytest tests/test_scheduler*.py -v
```

### Safety-critical subset (including phone, voice, seeding):
```bash
cd backend
../.venv-wsl/bin/python -m pytest tests/test_scheduler_seeding.py tests/test_phone_safety.py tests/test_voice_bugs_regression.py -q
```

### Full integration (all 308 tests):
```bash
cd backend
../.venv-wsl/bin/python -m pytest tests/test_scheduler*.py tests/test_phone_safety.py tests/test_voice_bugs_regression.py -v
```

---

## Summary

| Metric | Value |
|--------|-------|
| Script location | `backend/scripts/seed_scheduler_demo_calendar.py` |
| Store location | `backend/data/scheduler/appointments.jsonl` |
| Appointments seeded | 18 (2 weeks, all 6 types) |
| Test file | `backend/tests/test_scheduler_seeding.py` |
| Tests added | 17 classes, all passing ✅ |
| Total tests passing | 308 ✅ |
| External APIs called | 0 (SIMULATION ONLY) |
| Phone numbers exposed | 0 (all masked) |
| Idempotent | Yes ✅ |
| Safe to run repeatedly | Yes ✅ |
| Deterministic output | Yes ✅ |

---

## Next Steps (Future Phases)

1. **Google Calendar Write** — Wire `create_simulated_appointment()` → `google_calendar_create_event()`
2. **Outlook Integration** — Parallel to Google Calendar
3. **Email Notifications** — Send confirmation emails after booking (requires confirmation gating)
4. **Rescheduling/Cancellation** — Extend scheduler to modify/delete appointments
5. **Calendar Sync** — Bi-directional sync with external calendars

---

**No commits. No push. Simulation-only seeding complete.**
