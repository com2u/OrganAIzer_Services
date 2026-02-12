# Follow-Up Action Handling Implementation

## Overview

The Executive Agent now supports **intelligent follow-up action handling**, allowing users to reference and duplicate recently completed actions using natural language.

## Critical Features

### 1. **Follow-Up Detection**
The agent detects when users refer to a previous action using phrases like:
- "as well"
- "also"
- "too"
- "same thing"
- "that one"
- "the same event/email"
- "add it to [provider]"
- "duplicate it"

### 2. **Calendar Event Duplication**
When a user creates a calendar event and then requests to add it to another calendar, the agent:
1. Detects the follow-up request
2. Retrieves event details from action history
3. Prepares a duplicate event for the target calendar
4. Asks for explicit confirmation before creating

### 3. **Multi-Provider Support**
Works seamlessly across:
- Google Calendar ↔ Outlook Calendar
- Automatically detects target provider from user input
- Validates provider availability before proceeding

## Implementation Details

### New Methods in `ExecutiveAgent`

#### `_detect_followup_request(message: str) -> Dict[str, Any]`
Analyzes user message to detect follow-up requests.

**Returns:**
```python
{
    "is_followup": bool,
    "followup_type": "calendar_duplicate" | "email_duplicate" | None,
    "target_provider": str | None,
    "reference_action": dict | None
}
```

#### `_handle_calendar_duplication(reference_action, target_provider, user_id) -> Dict[str, Any]`
Handles the complete duplication workflow:
1. Validates target provider is connected
2. Checks for duplicate provider conflict
3. Recreates event slots from original action
4. Sets up confirmation state
5. Returns confirmation message

### Workflow Example

```
USER: "Schedule Team Meeting tomorrow at 2pm"
AGENT: [creates event on Google Calendar]
      ✅ Calendar event 'Team Meeting' created successfully!

USER: "add it to outlook as well"
AGENT: [detects follow-up, prepares duplication]
      📅 **Duplicate Event to Outlook Calendar?**
      
      I'll add this event:
      - Title: Team Meeting
      - Date: Monday, February 10, 2026
      - Time: 2:00 PM - 2:30 PM
      - From: Google Calendar
      - To: Outlook Calendar
      
      Confirm? (yes / cancel)

USER: "yes"
AGENT: [creates duplicate on Outlook]
      ✅ Calendar event 'Team Meeting' created successfully!
```

## Critical Rules

### FOLLOW-UP DETECTION (CRITICAL)
1. **Check follow-ups FIRST** in `process_message()` before intent analysis
2. **Only trigger on completed actions** - check action history
3. **Preserve all original event details** - title, date, time, duration

### CALENDAR FOLLOW-UP RULE
When user says "add to [calendar]" after creating event:
- **REUSE** last created event details
- **TREAT** as new CALENDAR_CREATE action
- **ASK** for explicit confirmation
- **DO NOT** claim lack of capability if provider exists

### FORBIDDEN BEHAVIOR
- ❌ Ignoring previous action context
- ❌ Claiming lack of capability when provider exists
- ❌ Creating duplicate without confirmation
- ❌ Losing event details during duplication

## Error Handling

### No Previous Action
```python
# User says "add it to outlook" but no recent calendar event
# Response: Asks what event they want to create
```

### Same Provider Conflict
```python
# User created on Google, says "add to google"
# Response: "This event is already on that calendar"
```

### Provider Not Connected
```python
# User requests Outlook but only Google connected
# Response: "Outlook Calendar is not connected. Please connect..."
```

### Multiple Providers Without Specification
```python
# User says "add to my calendar" (no provider specified)
# Has both Google and Outlook connected
# Response: Asks which calendar to use
```

## Testing

Run the test suite:
```bash
python test_followup_handling.py
```

**Test Coverage:**
1. Follow-up phrase detection
2. Complete duplication workflow
3. No previous action handling
4. Multiple provider scenarios
5. Provider validation

## Future Enhancements

### Email Duplication (Planned)
Similar workflow for duplicating emails:
```
USER: "send email to john@example.com about project update"
AGENT: [sends from Gmail]

USER: "send the same email from outlook"
AGENT: [duplicates and sends from Outlook]
```

### Smart Context Awareness
- Detect "that event" referring to events mentioned in conversation
- Support "move it to" (delete from original, create on target)
- Time zone adjustments when duplicating across providers

## Integration Points

### Action History
Uses `SessionMemory.record_action()` to track completed actions.
Each action record includes:
- `action_type`: Type of action (e.g., "create_calendar_event")
- `outcome`: Result (e.g., "EVENT_CREATED")
- `timestamp`: When action completed
- `details`: Action-specific data (title, date, provider, etc.)

### State Machine
Leverages existing calendar state machine:
- Jumps directly to `CAL_CONFIRM` state
- Bypasses `CAL_COLLECTING` since details already known
- Uses same confirmation and execution flow

### Provider Management
Integrates with token storage and provider factories:
- Validates OAuth tokens before preparing duplication
- Auto-selects provider if only one available
- Prompts user if multiple providers connected

## API Changes

No breaking changes. New functionality is transparent to existing code.

**Modified Methods:**
- `process_message()` - Added follow-up detection at the start

**New Methods:**
- `_detect_followup_request()`
- `_handle_calendar_duplication()`

## Security Considerations

1. **Confirmation Required**: Always asks user to confirm before duplicating
2. **Provider Validation**: Verifies OAuth tokens exist before proceeding
3. **Data Integrity**: Preserves exact event details from original
4. **Error Boundaries**: Graceful degradation if providers unavailable

## Performance

- **Near-instant detection** - Simple keyword matching
- **No API calls during detection** - Only on confirmation
- **Minimal memory overhead** - Action history limited to last 10 actions per type

## Logging

All follow-up operations are logged with prefix `[FOLLOWUP]`:
```
[FOLLOWUP] Detected: type=calendar_duplicate, target=outlook
[FOLLOWUP] Calendar duplication detected: target=outlook
[FOLLOWUP] Calendar duplication prepared: Team Meeting → outlook
```

## Configuration

No configuration required. Works out-of-the-box with existing provider setup.

## Troubleshooting

### Follow-up not detected
- Check phrase contains follow-up keywords
- Verify action history has completed action
- Review logs for `[FOLLOWUP]` entries

### Duplication fails
- Confirm OAuth tokens connected for target provider
- Verify event details in action history
- Check provider service availability

### Wrong provider selected
- Be explicit: "add to outlook" not just "add it"
- Provider keywords: "google", "gmail", "outlook", "microsoft"

---

**Status:** ✅ Implemented and Tested
**Version:** 1.0
**Date:** February 9, 2026
