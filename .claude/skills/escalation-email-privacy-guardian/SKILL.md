---
name: escalation-email-privacy-guardian
description: Owns the content, privacy, and safety of the phone-escalation email (and the shared email transport it shares with voicemail). Activate when editing escalation.py email construction, the call-summary prompt, recording-attachment logic, ESCALATION_EMAIL_* config, or anything that changes what the escalation/voicemail email contains or who receives it. Enforces consent-gated recordings, no raw number in the subject, transcript-secret hygiene, and the operator-handoff fields a technician needs while the caller waits in orbit.
---

# Escalation Email Privacy Guardian

Owns the **escalation email** sent when the AI hands a live call to a human:
what it contains, what must never leak, and what the technician needs to act on
while the caller is parked in the COMtrexx waiting room. The email is the *only*
handoff trigger under the manual-pickup model (see
`comtrexx-integration-guardian`), so it is both operationally critical and a PII
surface.

## Purpose

- Keep the escalation email **actionable**: the technician must know the caller
  is waiting, in which orbit, since when, and how to pick them up.
- Keep it **privacy-safe**: no secrets in the subject, no recording without
  consent, no unredacted secrets dragged in from the transcript.
- Keep the shared email transport (`_send_via_gmail` / `_send_smtp_email`)
  consistent across escalation and voicemail without coupling their policies.

## When to activate

- Editing `backend/voice/escalation.py`: `handle_escalation` (subject/body),
  `_build_summary_system` / `_SUMMARY_SYSTEM`, `_format_transcript`,
  `_format_local`, `_send_via_gmail`, `_send_smtp_email`,
  `send_voicemail_notification`.
- Editing the escalation trigger in `backend/voice/esl_call_handler.py`
  (`_conversation_loop`: consent capture, `recording_path`, `call_uuid`, `caller`).
- Changing `CALL_SUMMARY_FIELDS` in `backend/voice/llm_bridge.py`.
- Changing `ESCALATION_EMAIL_TO/FROM/SMTP_*` or `AI_WAITING_ROOM_*` config.
- Any change to what the escalation or voicemail email includes, or its recipient.

## Files/directories to inspect

- `backend/voice/escalation.py` — single source of the email subject + body, the
  summary prompt, transcript formatting, local-time formatting, and transport.
- `backend/voice/esl_call_handler.py` — `_conversation_loop` builds `reason`,
  captures `recording_consent`, finalises the recording, and calls
  `handle_escalation(... recording_consent=..., recording_path=..., call_uuid=...)`.
- `backend/voice/llm_bridge.py` — `CALL_SUMMARY_FIELDS` (ticket-ready schema).
- `backend/voice/config.py` — `ESCALATION_EMAIL_*`, `AI_WAITING_ROOM_PRIMARY/SECONDARY`.
- `backend/tests/test_phone_safety.py` — `TestEscalationEmail` is the executable spec.

## Email content invariants (MUST hold)

1. **Consent-gated recording.** The call recording is attached **only when
   `recording_consent` is true**. Gate it at the `handle_escalation` call site
   (`attach_path = recording_path if recording_consent else None`) — NOT inside
   `_send_via_gmail`/`_send_smtp_email`, which are shared with voicemail and must
   keep their own policy. When consent is "Nein", still report
   `Aufzeichnung erlaubt: Nein` in the body and still send the email; just withhold
   the audio (and log that it was withheld).
2. **No raw number in the subject.** The subject is `KI-Eskalation: {display} – …`
   where `display = caller_name or caller`; when the name is unknown this puts the
   **raw caller number in the subject line**, which mail servers log and index
   unencrypted. Prefer a non-PII fallback (e.g. "Unbekannt" + Call-ID) over the
   raw number in the subject.
3. **Raw caller number policy.** The body's `Nummer:` is currently the unmasked
   caller-ID — this diverges from the project masking invariant
   (`voice-freeswitch-guardian` #2: "never in escalation emails as raw"). A
   technician needs a callback number, so treat this as an **explicit, documented
   policy decision**, not an accident: the callback number is permitted in the
   body of the *internal* escalation email only. Do not widen that exposure (no
   raw number in the subject, logs, or any external surface). If you change this,
   update the invariant in `voice-freeswitch-guardian` to match.
4. **Transcript secret hygiene.** `Gesprächsverlauf` is emitted verbatim. The
   structured summary prompt (`_build_summary_system`) already forbids credentials,
   PINs, payment data, and full phone numbers — keep those rules. The raw
   transcript block does NOT redact; if you broaden transcript inclusion, add
   secret-pattern redaction or rely on the structured summary instead.
5. **Operator-handoff fields are required.** Because pickup is manual, the email
   MUST carry: a "caller is waiting" status, the waiting room (`AI_WAITING_ROOM_PRIMARY`
   with secondary as fallback, e.g. `778 (Fallback 779)`), a pickup instruction
   banner, the `Call-ID` (`call_uuid`), and a **local Europe/Berlin timestamp**
   alongside UTC. Do not remove these.
6. **Local time never crashes.** `_format_local` formats Europe/Berlin via
   `zoneinfo`, falls back to UTC if tzdata is missing, and never raises. Keep both
   the local and UTC lines.
7. **Internal mailbox assumption.** `ESCALATION_EMAIL_TO` is assumed to be an
   **internal, access-controlled** mailbox — it receives name + callback number +
   summary + transcript + (consented) recording. Never point it at an external or
   shared address, and do not add more PII without confirming the recipient.

## Mandatory checklist BEFORE editing

- [ ] Re-read `TestEscalationEmail` to know what is pinned.
- [ ] Identify whether your change touches the shared transport (also affects
      voicemail) or only `handle_escalation` (escalation-only policy).
- [ ] If adding a field, classify it: operational (safe) vs PII (gate/justify).

## Mandatory checklist AFTER editing

- [ ] Recording attaches ONLY with consent; consent line still present when "Nein".
- [ ] No raw number in the subject line.
- [ ] Waiting room, waiting flag, pickup instruction, Call-ID, and local+UTC
      timestamps all present in the body.
- [ ] No new unredacted secret path via the transcript.
- [ ] `TestEscalationEmail` (and the rest of `test_phone_safety.py`) pass in WSL.
- [ ] Voicemail email behavior unchanged unless intentionally edited.

## Tests required before email changes

Email changes are safety/privacy-relevant — they land with a hermetic test that
fails before and passes after (see `regression-protection`). Extend
`TestEscalationEmail` in `backend/tests/test_phone_safety.py`. Run in WSL:

```bash
cd backend
../.venv-wsl/bin/python -m pytest tests/test_phone_safety.py -q
# Privacy gate (recording/consent + logging):
../.venv-wsl/bin/python -m pytest tests/test_phone_safety.py tests/test_logging_redaction.py -q
```

## Documentation updates required

- `SECURITY.md` if the PII content of the email or its recipient policy changes.
- `VOICE_MODE.md` / `backend/voice/freeswitch/README.md` if the operator-handoff
  fields or escalation behavior change.
- `backend/voice/config.py` docstrings (+ `.env.example`) for any new
  `ESCALATION_EMAIL_*` setting.

## Forbidden behavior

- Do NOT attach the call recording without `recording_consent` true.
- Do NOT put the raw caller number (or any secret) in the email subject.
- Do NOT move the consent gate into the shared transport functions (it would also
  gate voicemail, whose policy is owned separately).
- Do NOT include unredacted secrets/credentials; do NOT relax the summary prompt's
  no-secrets rules.
- Do NOT remove the waiting-room / waiting-flag / pickup / Call-ID / local-time
  fields — they are the manual-pickup handoff.
- Do NOT point `ESCALATION_EMAIL_TO` at an external/shared mailbox.
- Do NOT change escalation timing, the deflect/orbit flow, or voicemail from here
  (see `comtrexx-integration-guardian` and `voice-freeswitch-guardian`).
