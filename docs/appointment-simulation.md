# Appointment Scheduling — Simulation (Scheduler v0.1)

> **Status: SIMULATION ONLY.** This subsystem does **not** touch Google Calendar,
> Outlook, any external calendar API, email, a database, COMtrexx, or FreeSWITCH.
> Every record it writes carries `status = "simulated"`. Real calendar integration
> is deliberately deferred until appointment types, durations, confirmation rules,
> and conflict handling are stable.

For the component design, ownership boundary, and migration path, see
[scheduler-architecture.md](./scheduler-architecture.md). This document is the
operational reference (hours, types, records, wording, how to inspect).

## Why simulation first

We want a safe, local, inspectable scheduling model that can be tested end-to-end
before wiring any real calendar. The scheduler produces deterministic availability
and appends "noted" (*vorgemerkte*) appointments to a local JSONL file. Nothing is
guaranteed to a caller and nothing leaves the machine.

## Package layout

```
backend/scheduler/
  __init__.py       public exports
  config.py         business hours, type catalogue, resources, granularity, store path
  models.py         Appointment record, Slot value type, record validation
  availability.py   deterministic slot generation (business hours + conflicts)
  store_jsonl.py    JSONL append / read (replaceable storage backend)
  service.py        internal API (list_available_slots / create_simulated_appointment / list_appointments)
  phone.py          safe German phone-facing wording
```

## Business hours (local Teleprofi time)

| Day       | Hours       |
|-----------|-------------|
| Monday    | 08:00–16:00 |
| Tuesday   | 08:00–16:00 |
| Wednesday | 08:00–16:00 |
| Thursday  | 08:00–16:00 |
| Friday    | 08:00–13:00 |
| Saturday  | closed      |
| Sunday    | closed      |

Slot times in v0.1 are naive local datetimes (no timezone conversion yet).

## Appointment types (v0.1)

| Type                     | Duration | Resource               |
|--------------------------|----------|------------------------|
| `callback`               | 30 min   | `remote_support_queue` |
| `remote_support`         | 30 min   | `remote_support_queue` |
| `technical_consultation` | 30 min   | `technician_sim_1`     |
| `on_site_visit_request`  | 60 min   | `technician_sim_1`     |
| `sales_consultation`     | 30 min   | `sales_queue`          |
| `maintenance_request`    | 60 min   | `technician_sim_1`     |

Simulated resources: `technician_sim_1`, `remote_support_queue`, `sales_queue`.
These are placeholders — not real people or calendars.

## Deterministic availability

Slots sit on a fixed **30-minute grid** starting at opening time and must fit
entirely within business hours. Availability is a pure function of
`(date, appointment_type, store contents, now)` — there is **no randomness** and no
hidden clock.

- A 60-minute type on Friday cannot start after **12:00** (must end by 13:00).
- Weekends yield **no** slots.
- Passing `now=<datetime>` excludes slots already in the past (tests inject `now`
  so "today" is deterministic).

`generate_slots(day, duration, now=…)` builds all candidates; `available_slots(day,
type, existing_records, now=…)` removes any candidate that overlaps an existing
simulated appointment on that type's resource. Both return `Slot` objects
(`slot.start`, `slot.end`, `slot.start_iso`, `slot.end_iso`).

## Conflict & duplicate prevention

- **Conflict:** a resource cannot hold two overlapping appointments. Booking a
  slot that overlaps an existing appointment on the same resource is rejected
  (`reason = "conflict"`).
- **Duplicate:** the same caller cannot be booked twice for the same
  `topic` + `appointment_type` + start time. The identity key uses the *masked*
  phone (or the caller name), the topic, the type, and the start time — never a raw
  number. Rejected with `reason = "duplicate"`.
- Off-grid, out-of-hours, or weekend start times are rejected with
  `reason = "invalid_slot"`; unknown types with `reason = "invalid_type"`; a start
  time before an injected `now` with `reason = "in_past"`.

## Storage (JSONL)

One JSON object per line at:

```
backend/data/scheduler/appointments.jsonl
```

`backend/data/` is gitignored, so simulated appointment data never enters git. The
path can be overridden with the `SCHEDULER_STORE_PATH` env var or the `path=`
argument (tests write to a temp file). The store is append-only; reads skip
blank/whitespace-only lines but **fail loudly** on a malformed JSON line
(`MalformedAppointmentLine`, reporting the file and line number) rather than
silently dropping data.

### How to inspect appointments

```bash
# from repo root
cat backend/data/scheduler/appointments.jsonl              # raw, one record per line
python -c "import json,sys; [print(json.loads(l)['appointment_type'], json.loads(l)['selected_slot_start']) for l in open('backend/data/scheduler/appointments.jsonl')]"
# or programmatically, with filters:
python -c "from scheduler import list_appointments; print(list_appointments(call_id='call-abc123'))"
```

### Record shape

Every record contains exactly these fields:

`status`, `schema_version`, `id`, `created_at`, `source`, `caller_name`,
`company`, `phone_masked`, `topic`, `appointment_type`, `selected_slot_start`,
`selected_slot_end`, `assigned_resource`, `notes`, `confirmation_summary`,
`call_id`.

- `status` is always `"simulated"`.
- `phone_masked` is the masked number (contains `*`) or `null`. **Raw phone
  numbers are never stored** — masking uses `voice.call_trigger.mask_number`.
- `created_at` is UTC (`...Z`); slot times are local naive ISO datetimes.

### Example record (fake)

```json
{"status": "simulated", "schema_version": "0.1", "id": "0450ec1d-74d3-42ef-af88-7cbaa74ed172", "created_at": "2026-07-01T21:20:37Z", "source": "phone_ai_simulation", "caller_name": "Max Mustermann", "company": "Muster GmbH", "phone_masked": "+491******4567", "topic": "Drucker offline", "appointment_type": "callback", "selected_slot_start": "2026-07-06T09:00:00", "selected_slot_end": "2026-07-06T09:30:00", "assigned_resource": "remote_support_queue", "notes": null, "confirmation_summary": "Perfekt, ich habe den Termin unverbindlich vorgemerkt: Rückruf am Montag, den 6. Juli um 9 Uhr (30 Minuten). Unser Team bestätigt ihn anschließend.", "call_id": "call-abc123"}
```

## Phone-facing wording (German)

`scheduler.phone` builds only simulation-honest wording and guards it with
`assert_phrase_safe()`. Offers are ONE natural spoken sentence (never a bullet
list — the text is read aloud by TTS), e.g. „Am Montag, den 6. Juli könnte ich
Ihnen 9 Uhr, 9:30 Uhr oder 10 Uhr anbieten.“

**Allowed:**
- „Ich kann Ihnen einen Termin vormerken.“
- „Am Montag könnte ich Ihnen 9 Uhr oder 10 Uhr anbieten.“
- „Perfekt, ich habe den Termin unverbindlich vorgemerkt.“

**Forbidden (raise `UnsafePhoneWording`):**
- „Der Termin ist garantiert.“
- „Renato kommt sicher morgen.“
- „Ich habe es im echten Kalender eingetragen.“
- „Der Termin ist fest gebucht.“

The confirmation summary always frames the result as a non-binding note —
„Perfekt, ich habe den Termin unverbindlich vorgemerkt: … Unser Team bestätigt
ihn anschließend.“ It never says „gebucht“ or claims a guarantee.

## Public API

```python
from datetime import datetime, date
from scheduler import (
    list_available_slots, create_simulated_appointment, list_appointments,
)
from scheduler import phone

# Offer up to 3 free slots for a Monday callback (deterministic)
slots = list_available_slots(date(2026, 7, 6), "callback", limit=3)
offer_text = phone.format_slot_offer(slots)   # safe German offer sentence

# Confirm one returned slot (simulation)
result = create_simulated_appointment(
    appointment_type="callback",
    slot_start=slots[0].start,
    caller_name="Max Mustermann",
    company="Muster GmbH",
    phone="+491701234567",          # masked before storage
    topic="Drucker offline",
    call_id="call-abc123",
)
if result.ok:
    summary = phone.build_confirmation_summary(result.appointment)

# Inspect stored records (optional filters: appointment_type, resource, call_id)
rows = list_appointments(call_id="call-abc123")
```

`create_simulated_appointment` returns a `BookingResult(ok, reason, appointment,
conflicting_id)` where `reason ∈ {booked, conflict, duplicate, invalid_type,
invalid_slot, in_past}`.

## Testing

```bash
# WSL debian12 + .venv-wsl, from backend/:
../.venv-wsl/bin/python -m pytest \
  tests/test_scheduler_models.py tests/test_scheduler_availability.py \
  tests/test_scheduler_store.py tests/test_scheduler_service.py \
  tests/test_scheduler_safety.py -q
```

The suite covers model/record validation, business hours, no-weekend slots,
Friday's 13:00 close, deterministic slots (with `now` injection), conflict
exclusion, duplicate prevention (incl. `topic`), JSONL append/read + blank-line
skip + malformed-line failure, raw-phone-never-stored, the `status = "simulated"`
invariant, safe phone wording, and a check that no calendar/external-API/network
dependency is imported or used.

## Phone integration (implemented — v0.1)

The Scheduler is wired into the live call loop through a single, narrow seam.

- **Module:** `backend/voice/scheduler_dialogue.py` — a deterministic per-call
  state machine (`idle → collecting → offered → booked`). Given the caller's
  transcribed utterance it returns either `None` (not an appointment turn — the
  call falls through to the normal LLM) or a `TurnResult` whose `reply` is spoken.
- **Hook:** `backend/voice/esl_call_handler.py::_conversation_loop` accepts an
  optional `dialogue_state` and, in the per-turn worker, calls
  `scheduler_dialogue.handle_turn(...)` **before** the LLM. When it returns `None`
  every existing call behaves exactly as before. Per-call state is created in
  `handle_esl_call` (in-memory, never persisted).

Flow and guarantees:

1. Appointment intent (or a clearly named service type) starts the flow; the
   engine collects **one detail at a time**: appointment type, then a preferred
   day.
2. It offers **1–3 real slots** from `list_available_slots(...)` via
   `phone.format_slot_offer(...)` — it never invents times.
3. **Nothing is booked until the caller confirms a specific offered slot**
   (ordinal "die erste/zweite/dritte" or a time like "10 Uhr"). Only then does it
   call `create_simulated_appointment(...)` with the masked-at-source phone and
   the `call_id`, and speak `phone.build_confirmation_summary(...)` (a
   *Vormerkung*, never a guarantee).
4. **Emergencies / high-risk** utterances are never booked — the engine emits the
   existing `ESCALATE:` directive so the loop's escalation path handles them.
5. If it cannot classify the type or parse a selection after a couple of tries,
   it resets and hands control back to the LLM.

Intent → appointment-type mapping (keyword-based, German-first): Rückruf →
`callback`; Fernwartung → `remote_support`; Vor-Ort / Techniker / Installation →
`on_site_visit_request`; Wartung → `maintenance_request`; Vertrieb / Angebot →
`sales_consultation`; Beratung → `technical_consultation`.

A defense-in-depth line in the inbound system prompt
(`backend/voice/llm_bridge.py`) also tells the model that scheduling is
system-handled, that it must not invent times, and must not claim a real/guaranteed
booking.

Tests: `backend/tests/test_scheduler_phone_integration.py` (engine state machine +
an end-to-end `_conversation_loop` wiring test proving a booking is written via the
Scheduler and the LLM is never asked to invent slots).

## Not implemented (deferred)

- Real Google Calendar / Outlook / any calendar API write.
- Real email confirmations.
- Persistent database (JSONL only).
- Timezone/DST handling (slot times are naive local).
- Cancellation / rescheduling / lookup-by-caller flows.
- Multi-day availability search or working-around holidays.
- Collecting the caller's company on the call (left `null`; not asked, to keep the
  flow short).
- English-language appointment dialogue (the engine's keywords and wording are
  German; English callers fall through to the LLM).
- COMtrexx / FreeSWITCH changes (none).
