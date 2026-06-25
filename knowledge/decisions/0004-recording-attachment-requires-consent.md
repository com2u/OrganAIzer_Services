---
id: 0004-recording-attachment-requires-consent
type: decision
owner: escalation-email-privacy-guardian
status: accepted
last_reviewed: 2026-06-24
sources:
  - backend/voice/escalation.py
  - backend/tests/test_phone_safety.py
  - .claude/skills/escalation-email-privacy-guardian/SKILL.md
  - "commit 939404e — Improve escalation email workflow"
---

# 0004 — Recording attachments require caller consent

## Status

Accepted.

## Context

The escalation email can attach the full-call recording. Consent to recording is
captured from the caller during the call and passed to `handle_escalation` as
`recording_consent`.

## Decision

The call recording is attached only when `recording_consent` is true. When consent
is denied, the email is still sent, but without the recording attachment; the
consent status is reported in the email body.

## Reasoning

Privacy: the recording must not leave the system without consent. The gate is
applied at the `handle_escalation` call site
(`attach_path = recording_path if recording_consent else None`), not inside the
shared `_send_via_gmail` / `_send_smtp_email` transport functions, which are also
used by voicemail and keep their own policy.

## Consequences

- Consent denied → email is sent, no audio attached, body shows
  `Aufzeichnung erlaubt: Nein`.
- Both the Gmail path and the SMTP fallback receive the consent-gated path.
- Pinned by `TestEscalationEmail` in `test_phone_safety.py`
  (`test_recording_attached_when_consent_true`,
  `test_recording_withheld_when_consent_false`,
  `test_smtp_fallback_also_consent_gated`).

## Related Sources

- `backend/voice/escalation.py` — `handle_escalation` consent gate.
- `backend/tests/test_phone_safety.py` — `TestEscalationEmail`.
- `.claude/skills/escalation-email-privacy-guardian/SKILL.md` — consent invariant.
- Commit: `939404e` (escalation email workflow).
