# Scheduler — Architecture (v0.1)

> **Status: SIMULATION ONLY.** The Scheduler is a core internal OrganAIzer
> service, built with the same discipline as the Executive Agent, but v0.1 makes
> **no** real bookings. It does not touch Google Calendar, Outlook, any external
> calendar API, email, a database, COMtrexx, or FreeSWITCH. Every record it writes
> carries `status = "simulated"`.

## Why the Scheduler exists as its own component

Appointment logic is a long-lived concern that will eventually front real
calendars, multiple resources, and confirmation rules. Rather than scatter
availability math and booking records through the phone/AI code, the Scheduler
owns them behind a small, deterministic, testable interface. The phone AI (and
any future caller) asks the Scheduler; it never re-implements scheduling itself.

## Ownership boundary

**The Scheduler owns:**
- business hours
- the appointment-type catalogue (durations + which resource serves each type)
- the resource list
- deterministic slot generation (the *only* source of availability)
- conflict checks (a resource cannot double-book)
- duplicate prevention (same caller + topic + type + start time)
- the simulated booking record shape + validation
- JSONL persistence (append / read)

**The AI is allowed to decide:**
- which appointment type best matches the caller's need
- which offered slot to propose / confirm (chosen from what the Scheduler returns)
- the free-text `topic`, `notes`, and caller details to attach

**The AI is NOT allowed to:**
- invent availability, business hours, or durations — it must call
  `list_available_slots()` and only confirm a slot the Scheduler returned
- write a record with any status other than `simulated`
- store a raw phone number
- imply a guarantee or a real calendar write to the caller (see `scheduler.phone`)

This mirrors the Executive Agent's discipline: the model proposes, a typed service
validates and records, and outward-sounding claims are gated.

## Module layout

```
backend/scheduler/
  __init__.py       public exports
  config.py         business hours, type catalogue, resources, granularity, store path
  models.py         Appointment record, Slot value type, validation
  availability.py   deterministic slot generation (business hours + conflicts)
  store_jsonl.py    JSONL append / read (the replaceable storage backend)
  service.py        internal API: list_available_slots / create_simulated_appointment / list_appointments
  phone.py          safe German phone-facing wording (offer + Vormerkung), guarded
```

Dependency direction (no cycles):

```
config  ←  models  ←  availability  ┐
   ↑         ↑                        ├→  service  →  (callers: phone AI, tools, tests)
   └─────────┴──  store_jsonl  ───────┘
models  ←  phone
```

`config` is pure data. `service` is the only layer callers should use.

## Internal API

```python
from datetime import date, datetime
from scheduler import (
    list_available_slots, create_simulated_appointment, list_appointments,
)

# 1) Ask the Scheduler what's free (deterministic; inject `now` to hide past slots)
slots = list_available_slots(
    date(2026, 7, 6), "callback", limit=3, now=datetime(2026, 7, 6, 9, 0),
)
# -> list[Slot]  (Slot.start, Slot.end, Slot.start_iso, Slot.end_iso)

# 2) Confirm ONE returned slot (simulation). Raw phone is masked before storage.
result = create_simulated_appointment(
    appointment_type="callback",
    slot_start=slots[0].start,
    caller_name="Max Mustermann",
    company="Muster GmbH",
    phone="+491701234567",          # stored only as phone_masked
    topic="Drucker offline",
    call_id="call-abc123",
)
# -> BookingResult(ok, reason, appointment, conflicting_id)
#    reason ∈ {booked, conflict, duplicate, invalid_type, invalid_slot, in_past}

# 3) Inspect what's stored
rows = list_appointments(call_id="call-abc123")   # optional filters: appointment_type, resource, call_id
```

### Determinism

Availability is a pure function of `(date, appointment_type, store contents, now)`.
There is **no randomness** and no hidden clock: tests inject `now` to control
"today". Slots sit on a fixed 30-minute grid (`config.SLOT_GRANULARITY_MINUTES`)
from opening time and must fit entirely inside business hours.

## Business hours & catalogue

See `config.py` (the source of truth) and `docs/appointment-simulation.md` for the
tables. Summary: Mon–Thu 08:00–16:00, Fri 08:00–13:00, weekend closed; six
appointment types across three simulated resources.

## Storage: why JSONL

- **Inspectable:** one JSON object per line — `cat`, `grep`, `jq`, or a diff all
  work; a human can read exactly what the AI "booked" during a call.
- **Append-only & simple:** no schema migration, no server, no locking ceremony
  for a single-user, single-writer runtime (matches the repo's in-memory session
  model).
- **Safe to throw away:** it is a simulation log, not a system of record.

The store lives at `backend/data/scheduler/appointments.jsonl` (gitignored via
`backend/data/`), overridable with `SCHEDULER_STORE_PATH` or the `path=` argument.

## Migration path (later, out of scope for v0.1)

Storage is deliberately isolated behind `store_jsonl.py`'s two functions
(`append_appointment` / `read_appointments`) and the `Appointment` record shape.
A future backend swaps that module without touching `service.py`:

1. **SQLite** — add `store_sqlite.py` with the same append/read contract; select
   via config. `schema_version` on every record enables a migration.
2. **Google Calendar / Outlook** — introduce a real `book()` path *behind
   confirmation gating* (like the Executive Agent's calendar create): a
   deterministic idempotency key (e.g. SHA-256 over caller+type+slot), a status
   beyond `simulated` (`pending`/`confirmed`), and treating a 2xx without an
   event id as failure. Availability then reconciles Scheduler records with the
   real calendar's busy times.
3. **Confirmation rules & richer resources** stabilize *before* any real write —
   that is the explicit reason v0.1 stays a simulation.

## Testing

```bash
# WSL debian12 + .venv-wsl, from backend/:
../.venv-wsl/bin/python -m pytest \
  tests/test_scheduler_models.py tests/test_scheduler_availability.py \
  tests/test_scheduler_store.py tests/test_scheduler_service.py \
  tests/test_scheduler_safety.py -q
```

The safety file also asserts the package imports no calendar/DB/network dependency
and that booking works with `socket.socket` patched to raise.

## Phone integration

The Scheduler is wired into the live call loop via
`backend/voice/scheduler_dialogue.py` (a deterministic per-call state machine) and
a single optional `dialogue_state` hook in
`esl_call_handler.py::_conversation_loop`. The engine offers only
Scheduler-provided slots and books (simulated) only after explicit caller
confirmation; emergencies escalate instead. Full details in
`docs/appointment-simulation.md` ("Phone integration").

## Explicitly not implemented in v0.1

Real calendar/email/DB writes; timezone/DST handling (slot times are naive local);
cancellation/reschedule; multi-day search / holidays; collecting company on the
call; and English-language appointment dialogue (German-only engine).
