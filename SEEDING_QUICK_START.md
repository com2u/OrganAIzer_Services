# Scheduler Seeding — Quick Start

## One-Liner: Seed the calendar

```bash
cd backend && ../.venv-wsl/bin/python scripts/seed_scheduler_demo_calendar.py
```

**Output:**
```
✅ Seeded 18 appointments to /mnt/.../backend/data/scheduler/appointments.jsonl
📁 Store size: 10883 bytes
```

---

## Common Tasks

### Preview before seeding

```bash
../.venv-wsl/bin/python scripts/seed_scheduler_demo_calendar.py --dry-run
```

### Force re-seed (clear old seed)

```bash
../.venv-wsl/bin/python scripts/seed_scheduler_demo_calendar.py --force
```

### Run tests

```bash
# Seeding tests
../.venv-wsl/bin/python -m pytest tests/test_scheduler_seeding.py -v

# All scheduler tests
../.venv-wsl/bin/python -m pytest tests/test_scheduler*.py -q
```

### View seeded appointments

```bash
cat backend/data/scheduler/appointments.jsonl | python -m json.tool | less
```

---

## What You Get

✅ **18 appointments** across 2 weeks  
✅ **All 6 types** (callback, remote_support, technical_consultation, on_site_visit_request, sales_consultation, maintenance_request)  
✅ **Business hours only** (Mon–Thu 8–16, Fri 8–13, no weekends)  
✅ **Realistic data** (German names, companies, topics)  
✅ **Masked phone numbers** (no raw numbers exposed)  
✅ **No conflicts** (no overlapping appointments)  
✅ **Idempotent** (safe to run repeatedly)  
✅ **No external APIs** (local JSONL only, simulation-only)  

---

## Files

| File | Purpose |
|------|---------|
| `backend/scripts/seed_scheduler_demo_calendar.py` | Seeding script |
| `backend/tests/test_scheduler_seeding.py` | 17 validation tests |
| `SCHEDULER_SEEDING_GUIDE.md` | Detailed usage guide |
| `SEEDING_IMPLEMENTATION_REPORT.md` | Technical details |
| `backend/data/scheduler/appointments.jsonl` | Seeded appointments (JSONL) |

---

## Test Results

```
✅ 17/17 seeding tests PASSING
✅ 308/308 total tests PASSING (scheduler + phone + voice)
✅ 0 failures
```

---

## Design: No Commits, No Push

- ✅ All code created
- ✅ All tests passing
- ❌ No git commits
- ❌ No git push
- ✅ Ready to commit when you're ready

---

## For More Details

- **How to use:** `SCHEDULER_SEEDING_GUIDE.md`
- **Technical details:** `SEEDING_IMPLEMENTATION_REPORT.md`
- **Test coverage:** `backend/tests/test_scheduler_seeding.py`

---

## Status

**Implementation: COMPLETE ✅**

Ready for immediate use in appointment testing and AI phone evaluation.
