# Email Slot-Filling + Email-Mode Parsing + Draft Persistence Fix

## Problem Summary

The OrganAIzer email drafting system had three critical issues in the reproduction scenario:

**REPRO TRACE:**
```
User: draft me an email
User: renato.xheci@web.de
Agent asks AGAIN who to put in To:  ❌
User: Fronti
User: Can I meet you at some point for dinner?
Agent treats as invitation to the AI, not email content  ❌
User: no thats the email i want to send
Agent: no pending actions  ❌
```

## Root Causes

1. **Slot Confusion**: Agent re-asks for "To" after it was already provided and overwrites recipient
2. **Email-Mode Parsing**: In EMAIL_* states, user free-form messages interpreted as conversation to agent instead of email SUBJECT/BODY content
3. **Draft Persistence**: Showing a draft didn't persist `pending_email_draft`; confirmations/clarifications failed with "no pending actions"

## Solution Implemented

### A) STRICT EMAIL SLOTS (Authoritative Backend State)

Implemented structured fields as authoritative backend state:
- `to_email` (string, validated email) - NEVER re-ask once set
- `to_name` (optional display name)
- `subject` (string, optional → auto-generate if missing)
- `body` (string)

**Rules Enforced:**
1. If user supplies a valid email address at any point, set `to_email` and NEVER ask for "To:" again
2. If user provides a non-email token when `to_email` is already known (e.g., "Fronti"), treat it as `to_name` (display name), NOT recipient
3. If `to_email` is missing and user provides a non-email token, ask again specifically for an email address

### B) EMAIL MODE MESSAGE INTERPRETATION

When state is `EMAIL_COLLECTING` or `EMAIL_DRAFT_READY`:

**Default interpretation of any free-form sentence is EMAIL BODY content**, unless it clearly matches:
- Edit request (e.g., "make it friendlier", "shorter", "change subject")
- Confirmation (send it/yes/looks good)
- Cancel
- Explicit subject marker ("subject: ...")

**Example:**
```
User: "Can I meet you at some point for dinner?"
=> Treated as body text, NOT conversation with AI
```

### C) ATOMIC DRAFT PERSISTENCE + PENDING ACTION

If the agent displays "Email Draft Ready" (or any draft):
- Persist `pending_email_draft` in backend state immediately
- Set state = `EMAIL_DRAFT_READY`
- Confirmation must map to this persisted draft

**On "send"/"send it"/"yes":**
- Call `send_email` exactly once using `pending_email_draft`
- On success: record `EMAIL_SENT` in action log, clear draft, state=IDLE, respond with ✅ confirmation
- On failure: keep draft, state=`EMAIL_DRAFT_READY`, explain error

### D) FIX "NO PENDING ACTIONS" FALLBACK

The agent must NOT say "no pending actions" if:
- The last assistant message contained an email draft OR
- `pending_email_draft` exists OR
- State is `EMAIL_DRAFT_READY`

Instead: proceed with send/edit/cancel handling.

## Implementation Details

### New Helper Methods

1. **`_extract_email_slots(message)`**
   - Uses regex to extract email address (authoritative)
   - Extracts subject markers ("subject:", "about")
   - Returns dict with `to_email`, `to_name`, `subject`, `body`

2. **`_finalize_email_draft(email_slots, user_id, provider)`**
   - Checks if all required slots are filled
   - Auto-generates subject if missing
   - Persists draft with state `EMAIL_DRAFT_READY`
   - Records `DRAFT_CREATED` in action history

3. **`_edit_email_draft(edit_request, email_slots, user_id, provider)`**
   - Modifies existing draft based on user request
   - Uses LLM to apply changes while preserving intent
   - Re-finalizes to show updated draft

### Modified `_handle_email_draft()` Flow

```python
1. Detect state-specific intents (cancel, send, edit)
2. If new draft: initialize strict slots
3. If existing draft:
   a. EMAIL_DRAFT_READY state:
      - Send command → execute send
      - Edit request → modify draft
      - DEFAULT → treat as additional body content (EMAIL MODE)
   b. EMAIL_COLLECTING state:
      - Extract new information
      - Apply STRICT SLOT RULES
      - Never overwrite to_email once set
4. Finalize draft (check required slots, show draft if ready)
```

## State Machine

```
IDLE
  ↓ "draft email"
EMAIL_COLLECTING (gathering to_email, to_name, subject, body)
  ↓ All required slots filled
EMAIL_DRAFT_READY (draft shown, awaiting confirmation)
  ↓ "send it"
  ├─ Single account → Proceed to send
  └─ Multiple accounts → EMAIL_SELECT_SENDER
EMAIL_SELECT_SENDER (waiting for "gmail" or "outlook")
  ↓ Valid selection
EMAIL_SENDING (sending email)
  ↓ Success
IDLE (email sent confirmation)
  ↓ Failure
EMAIL_DRAFT_READY (draft preserved for retry)
```

### EMAIL_SELECT_SENDER State

**Purpose:** Prevent sender selection ("gmail"/"outlook") from being appended to email body.

**Hard Rules:**
- ONLY accepts "gmail" or "outlook" as input
- Does NOT treat user input as email body content
- Invalid input prompts user again without modifying draft
- Once provider selected, immediately proceeds to send

**Anti-Loop Guard:**
- If `provider` already set in draft data, skip this state entirely
- Prevents asking for sender more than once

## Success Criteria

✅ **Test 1: Provide email then name**
```
User: draft email
User: renato.xheci@web.de
User: Fronti
User: Can I meet you for dinner sometime?
=> Draft shows To: Fronti <renato.xheci@web.de> with body including that sentence
```

✅ **Test 2: After "send it"**
```
=> ✅ Email sent confirmation (tool-backed), then normal chat works
```

✅ **Test 3: No "pending actions" error**
```
Draft shown → "send it" → Send executed (not "no pending actions")
```

## Testing

Run the test suite:
```bash
cd backend
python ../test_email_slot_filling.py
```

Tests verify:
- Strict slot filling (never re-ask for to_email)
- Email-mode parsing (treat messages as content)
- Atomic draft persistence
- No "pending actions" fallback when draft exists

## Files Modified

1. `backend/services/executive_agent_service.py`
   - Rewrote `_handle_email_draft()` with strict slot-filling logic
   - Added helper methods for slot extraction and draft finalization
   - Implemented email-mode parsing rules
   - Added atomic draft persistence

## Backward Compatibility

The fix maintains backward compatibility with existing email workflows:
- Legacy `recipient` field is set alongside `to_email` for compatibility
- Existing `pending_action` structure is enhanced, not replaced
- All existing confirmation handlers continue to work

## Related Fixes

This fix builds on and complements:
- `EMAIL_STATE_MACHINE_FIX.md` - State management
- `EMAIL_DRAFT_PERSISTENCE_FIX.md` - Draft persistence
- `ACTION_HISTORY_IMPLEMENTATION.md` - Action logging
- `DRAFT_EMAIL_ROUTING_FIX.md` - Intent routing
