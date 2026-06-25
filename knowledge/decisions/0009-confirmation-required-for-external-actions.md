---
id: 0009-confirmation-required-for-external-actions
type: decision
owner: backend-guardian
status: accepted
last_reviewed: 2026-06-24
sources:
  - backend/services/tool_definitions.py
  - backend/services/executive_agent_service.py
  - backend/tests/test_executive_agent_safety.py
---

# 0009 — Confirmation required for external actions

## Status

Accepted.

## Context

The Executive Agent can perform outward actions (calendar create/update/delete,
email send/reply, recurring-event create). These are exposed as `propose_*` tools
and must not execute without explicit user confirmation.

## Decision

Every outward action is gated: a `propose_*` tool records a pending action and
returns a confirmation request; the action is executed against the real API only
on explicit user confirmation. An explicit cancel clears the pending action and
makes no API call.

## Reasoning

`CONFIRMATION_REQUIRED_TOOLS` (`tool_definitions.py:505`) is the authoritative set
of gated tools: `propose_create_calendar_event`, `propose_update_calendar_event`,
`propose_delete_calendar_event`, `propose_send_email`, `propose_reply_email`,
`propose_create_recurring_event`. The agent stores a `pending_action` with status
`awaiting_confirmation` and executes only on confirmation. The safety tests assert
that every `propose_*` tool is in the set, read-only tools are not, and the set is
complete.

## Consequences

- No outward write occurs without an explicit, tracked confirmation step.
- Cancel makes no HTTP call and clears the pending action.
- Pinned by `TestConfirmationRequiredToolsCompleteness` in
  `test_executive_agent_safety.py`.

## Related Sources

- `backend/services/tool_definitions.py` — `CONFIRMATION_REQUIRED_TOOLS`.
- `backend/services/executive_agent_service.py` — `pending_action` /
  `awaiting_confirmation` flow; execute-on-confirm; cancel clears pending.
- `backend/tests/test_executive_agent_safety.py` —
  `TestConfirmationRequiredToolsCompleteness`.
