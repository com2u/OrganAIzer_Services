---
id: 0008-german-only-outbound-dialing
type: decision
owner: voice-freeswitch-guardian
status: accepted
last_reviewed: 2026-06-24
sources:
  - backend/voice/call_trigger.py
  - backend/tests/test_phone_safety.py
---

# 0008 — German-only outbound dialing

## Status

Accepted.

## Context

The voice system can place outbound calls. Outbound dialing is restricted to German
numbers by the `is_german_number` gate in `backend/voice/call_trigger.py`.

## Decision

Outbound dialing is allowed only for German numbers. `is_german_number` gates the
dialing paths; non-German numbers are not dialed.

## Reasoning

`is_german_number` (`call_trigger.py:62`) is applied at the resolve/dial points
(`call_trigger.py:175`, `:192`, `:197`). German formats (`+49`, `0049`, national
`0…`, mobile `0175…`) pass; non-German numbers (`+1`, `+44`, `+33`, `0033`, `0044`,
`001…`) are rejected. This is asserted by the safety tests.

## Consequences

- A dial request for a non-German number is blocked before any call is placed.
- The restriction is pinned by `TestGermanNumberAllowed` and
  `TestNonGermanNumberBlocked` in `test_phone_safety.py`.

## Related Sources

- `backend/voice/call_trigger.py` — `is_german_number` definition and its use in
  the dial/resolve paths.
- `backend/tests/test_phone_safety.py` — `TestGermanNumberAllowed`,
  `TestNonGermanNumberBlocked`.
