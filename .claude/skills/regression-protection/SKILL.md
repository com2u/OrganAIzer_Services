---
name: regression-protection
description: Guarantees that fixed bugs stay fixed and safety behavior never silently regresses. Activate after fixing a bug or changing safety-critical behavior (phone, OpenClaw, confirmation gating, logging redaction, voice, idempotency). Every fix must land with a hermetic test that fails before and passes after.
---

# Regression Protection

This repo keeps a strong, hermetic safety net (`backend/tests/`) precisely because
its highest-value behaviors are easy to break silently — a dialed non-German
number, a leaked phone number, an unconfirmed email send, a loosened OpenClaw
container. This skill enforces test-first regression discipline.

## Purpose

- Ensure every bug fix ships with a test that reproduces the bug (fails before fix).
- Ensure safety behaviors are pinned so they cannot regress unnoticed.
- Keep the test suite hermetic (no real network/FS/Docker/OAuth) so it always runs.

## When to activate

- After fixing any bug (functional or safety).
- After changing any safety-critical behavior.
- When a guardian skill's "after editing" checklist calls for a new/updated test.
- When reviewing a change that lacks test coverage for new behavior.

## Files/directories to inspect

- `backend/tests/` — find the test file matching the area:
  - `test_phone_safety.py` — German gate, masking, confirmation, active-call block.
  - `test_openclaw_safety.py` — container bounds + client + router surface.
  - `test_executive_agent_safety.py` — confirmation gating, pending actions.
  - `test_calendar_event_creation.py` — idempotency + truthfulness rules.
  - `test_calendar_intent.py`, `test_email_foundation.py` — intent/slots.
  - `test_microsoft_integration.py` — provider/OAuth mocked.
  - `test_logging_redaction.py` — no secret/PII in logs.
  - `test_voice_bugs_regression.py`, `test_qa_audit_bugs.py` — named-bug regressions.
- Existing tests show the established mocking patterns (aiohttp, originate_call,
  MSAL) — reuse them.

## How regression tests must be written

1. **Hermetic.** No real network, FreeSWITCH, Docker, or OAuth. Mock at the
   boundary (patch `originate_call`, mock aiohttp/MSAL, read config files as text).
2. **Fails before, passes after.** Write the test against the bug first; confirm it
   fails on the unfixed code, then apply the fix.
3. **Lives in the matching file**, or a new `test_<area>_regression.py` for a
   named bug. Name the test after the behavior, not the ticket.
4. **Asserts the invariant, not the implementation** — e.g. assert "non-German
   number is rejected", not the exact internal call sequence.

## Mandatory checklist BEFORE editing

- [ ] Locate the existing test that covers (or should cover) this behavior.
- [ ] Write/extend a test that reproduces the bug or pins the new safety behavior.
- [ ] Run it and confirm it FAILS on current code (for a bug fix).

## Mandatory checklist AFTER editing

- [ ] The new/updated test PASSES after the fix.
- [ ] The full safety subset still passes.
- [ ] The test is hermetic (no skipped network/FS/Docker dependency).
- [ ] No existing test was weakened or deleted to make the change pass; if a test
      genuinely had to change, the reason is explicit and the invariant preserved.

## Validation commands

```bash
# WSL debian12 + .venv-wsl, from backend/:
cd backend
# The specific new test:
../.venv-wsl/bin/python -m pytest tests/test_<area>.py::TestClass::test_name -q
# Full safety subset gate:
../.venv-wsl/bin/python -m pytest tests/test_phone_safety.py tests/test_openclaw_safety.py \
  tests/test_executive_agent_safety.py tests/test_logging_redaction.py \
  tests/test_calendar_event_creation.py tests/test_voice_bugs_regression.py \
  tests/test_qa_audit_bugs.py -q
# Whole suite:
../.venv-wsl/bin/python -m pytest tests/ -q
```

## Documentation updates required

- If the bug revealed a documented behavior was wrong, fix the doc (via
  `documentation-sync`).
- For a notable bug class, add a one-line note to `VOICE_MODE.md` or the relevant
  module doc describing the failure mode and the guard now in place (mirrors the
  existing "Fix applied" note in `VOICE_MODE.md`).

## Known repository risks

- **No CI** runs these tests automatically — regressions only surface if the suite
  is run manually. Always run the safety subset before declaring done.
- Tests rely on `sys.path.insert` and must be run from `backend/`; running from the
  repo root changes collection.
- Some tests read config files as raw text (e.g. `openclaw.json` is JSON5) — follow
  the existing pattern rather than `json.load`.
- It is easy to make a test pass by weakening an assertion; that defeats the net.

## Forbidden behavior

- Do NOT fix a safety bug without adding a test that fails on the unfixed code.
- Do NOT delete or weaken a safety assertion to make a change pass.
- Do NOT add tests that depend on real network/FreeSWITCH/Docker/OAuth.
- Do NOT skip the safety subset before marking work complete.
- Do NOT run the suite with Windows Python.
