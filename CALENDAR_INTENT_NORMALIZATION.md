# CALENDAR INTENT NORMALIZATION - IMPLEMENTATION GUIDE

**Status:** ✅ IMPLEMENTED  
**Date:** February 9, 2026  
**Critical:** This implementation enforces strict calendar creation persistence rules

---

## OVERVIEW

The Executive Agent now supports **CALENDAR_CREATE** intent normalization with two distinct types:
1. **EVENT** - Regular calendar events (meetings, appointments)
2. **PERSONAL_NOTE** - Personal reminders/notes (no attendees)

Both types follow the same creation flow with STRICT TASK PERSISTENCE rules.

---

## INTENT NORMALIZATION RULES

### Supported Phrases

All of the following phrases normalize to **CALENDAR_CREATE**:

#### General Calendar Actions
- `"add to my calendar"`
- `"add to calendar"`
- `"add an event"`
- `"add event"`
- `"schedule"`
- `"meeting"`
- `"appointment"`
- `"calendar"`
- `"event"`

#### Personal Note Actions
- `"note it down"`
- `"note this down"`
- `"note down"`
- `"just a note for myself"`
- `"note for myself"`
- `"reminder for myself"`
- `"remind me"`
- `"personal note"`
- `"personal reminder"`

### Type Detection

The system automatically determines if the intent is an EVENT or PERSONAL_NOTE:

**PERSONAL_NOTE indicators:**
- `"note it down"`
- `"note for myself"`
- `"just a note"`
- `"personal note"`
- `"reminder for myself"`
- `"personal reminder"`

**Default:** If no personal note indicators are found, the type defaults to EVENT.

---

## TASK PERSISTENCE RULE (NON-NEGOTIABLE)

Once `CALENDAR_CREATE` is active, the following rules apply:

### FORBIDDEN Behaviors
1. ❌ **FORBIDDEN from listing events** - Cannot switch to "show events" during active creation
2. ❌ **FORBIDDEN from resetting state** - State persists until completion or explicit cancel
3. ❌ **FORBIDDEN from saying "no pending actions"** - Must acknowledge active calendar task

### REQUIRED Behavior
✅ **Every subsequent message** must be interpreted as:
- Filling missing slots (title, date, time)
- Clarifying the same calendar item
- Editing existing slots
- Confirming or cancelling

### Explicit Cancel Only

The agent may ONLY cancel if the user says:
- `"cancel"`
- `"stop"`
- `"never mind"`
- `"forget it"`
- `"abort"`

---

## SEMANTIC SLOT EXTRACTION (MANDATORY)

From every user message during `CALENDAR_CREATE`, the system extracts:

### Required Slots
1. **title** - Event/note name
2. **date** - When it occurs (YYYY-MM-DD format)
3. **time** - Start time (HH:MM in 24-hour format)

### Optional Slots
4. **duration** - Length in minutes (default: 30)
5. **location** - Physical/virtual location
6. **provider** - Google Calendar or Outlook Calendar
7. **type** - EVENT or PERSONAL_NOTE

### Example Extraction

```
User: "Meeting with Chef tomorrow at 08:00"
```

**Extracted:**
- title = "Meeting with Chef"
- date = "2026-02-10" (tomorrow)
- time = "08:00"
- type = "EVENT" (default)

---

## CONFIRMATION FLOW

When all **required slots** are filled, the system presents a summary:

### Format

```
📅 Here's what I'll add:

- Type: Personal note (or Event)
- Title: Meeting with Chef
- Date: Monday, February 9, 2026
- Time: 08:00 AM - 08:30 AM (30 minutes)
- Location: Conference Room A (if provided)
- Calendar: Google (or Outlook)

Create it? (yes / cancel)
```

### User Responses

**Confirmation:**
- `"yes"`
- `"confirm"`
- `"looks good"`
- `"create it"`
- `"add it"`
- `"go ahead"`

**Cancellation:**
- `"cancel"`
- `"no"`
- `"never mind"`

**Edits:**
- Any message with slot updates (e.g., "change time to 2pm", "tomorrow instead")

---

## STATE MACHINE

### Calendar States

```
CAL_COLLECTING
  ↓
  ├─ Gathering: title, date, time
  ├─ User provides partial info
  └─ Agent asks for missing slots
  
CAL_CONFIRM
  ↓
  ├─ All required slots filled
  ├─ Preview shown to user
  └─ Awaiting confirmation
  
CAL_PROVIDER_SELECT (if needed)
  ↓
  ├─ Multiple calendars connected
  ├─ User selects Google or Outlook
  └─ Must choose before creation
  
CAL_CREATING
  ↓
  ├─ Calling calendar API
  └─ Creating event in calendar
  
CAL_DONE
  ↓
  ├─ Event created successfully
  ├─ Recorded in action history
  └─ Task cleared
  
CAL_CANCELED
  ↓
  ├─ User explicitly cancelled
  └─ Task cleared
```

### State Transitions

1. **New Request** → `CAL_COLLECTING`
2. **All Slots Filled** → `CAL_CONFIRM`
3. **User Confirms + Multiple Accounts** → `CAL_PROVIDER_SELECT`
4. **Provider Selected OR User Confirms + Single Account** → `CAL_CREATING`
5. **API Success** → `CAL_DONE`
6. **User Says "Cancel"** → `CAL_CANCELED`

---

## ACTION TRUTH RULE

The agent may **ONLY** claim an event was created if:

✅ `calendar_provider.create_event()` returns `status="success"`

### Implementation

```python
result = await calendar_provider.create_event(event_request)

if result.get("status") == "success":
    # CRITICAL: Record in action history
    self.memory.record_action(
        action_type="create_calendar_event",
        outcome="EVENT_CREATED",
        details={
            "title": title,
            "event_id": result.get("event_id"),
            ...
        }
    )
    # SUCCESS response
else:
    # CRITICAL: Record failure
    self.memory.record_action(
        action_type="create_calendar_event",
        outcome="EVENT_FAILED",
        details={"error": result.get("message")}
    )
    # ERROR response - event NOT created
```

### On Failure

If API fails or returns non-success status:
- ❌ **DO NOT** say "event created"
- ✅ **DO** preserve event details
- ✅ **DO** explain the error
- ✅ **DO** allow user to retry

---

## EXAMPLES

### Example 1: Simple Event

```
User: "Meeting tomorrow at 2pm"

Agent: 📅 Got it! Here's what I understood:
- Event: Meeting
- Date: Tomorrow
- Time: 14:00

⏰ What time should the event start?

User: "2pm"

Agent: 📅 Here's what I'll add:
- Type: Event
- Title: Meeting
- Date: Monday, February 10, 2026
- Time: 02:00 PM - 02:30 PM (30 minutes)
- Calendar: Google

Create it? (yes / cancel)

User: "yes"

Agent: ✅ Calendar event 'Meeting' created successfully! Can I help with anything else?
```

### Example 2: Personal Note

```
User: "Note down: Call mom about birthday party"

Agent: 📅 Got it! Here's what I understood:
- Event: Call Mom About Birthday Party
- Type: Personal note

📅 When should this event be scheduled?

User: "Tomorrow at 10am"

Agent: 📅 Here's what I'll add:
- Type: Personal note
- Title: Call Mom About Birthday Party
- Date: Monday, February 10, 2026
- Time: 10:00 AM - 10:30 AM (30 minutes)
- Calendar: Google

Create it? (yes / cancel)

User: "yes"

Agent: ✅ Calendar event 'Call Mom About Birthday Party' created successfully! Can I help with anything else?
```

### Example 3: Task Persistence

```
User: "Schedule a meeting with chef"

Agent: 📅 Got it! Here's what I understood:
- Event: Meeting With Chef

📅 When should this event be scheduled?

User: "Show me my calendar"  ← User tries to switch tasks

Agent: 📅 When should this event be scheduled?
(I'm currently helping you create "Meeting With Chef". 
Please provide a date, or say "cancel" to stop.)
```

**CRITICAL:** The agent does NOT switch to listing events. Task persistence rules prevent this.

### Example 4: Slot Filling

```
User: "Add to my calendar"

Agent: 📅 What should I call this event?

User: "Team standup"

Agent: 📅 Got it! Here's what I understood:
- Event: Team Standup

📅 When should this event be scheduled?

User: "Every day at 9am"

Agent: 📅 Here's what I'll add:
- Type: Event
- Title: Team Standup
- Date: Today
- Time: 09:00 AM - 09:30 AM (30 minutes)
- Calendar: Google

Create it? (yes / cancel)
```

---

## IMPLEMENTATION DETAILS

### Code Location

**File:** `backend/services/executive_agent_service.py`

**Key Methods:**
1. `_analyze_intent()` - Detects CALENDAR_CREATE intent
2. `_handle_calendar_intent()` - Routes to creation handler
3. `_handle_calendar_create()` - Main creation flow with state machine
4. `_finalize_calendar_event()` - Validates slots and shows confirmation
5. `_execute_calendar_create()` - Actually creates event via API

**Slot Extraction:**
**File:** `backend/utils/slot_extraction.py`

**Method:** `SlotExtractor.extract_calendar_slots()`

### Integration Points

1. **Intent Analysis** - Early detection prevents task switching
2. **Active Task Lock** - Prevents state leaks and context switching
3. **Action History** - Records EVENT_CREATED or EVENT_FAILED
4. **Session Memory** - Persists slots across messages

---

## TESTING GUIDE

### Test Cases

#### TC1: Basic Event Creation
```
Input: "Schedule team meeting tomorrow at 3pm"
Expected: Event created with all details
```

#### TC2: Personal Note
```
Input: "Note for myself: buy groceries"
Expected: Personal note type detected
```

#### TC3: Task Persistence
```
Input: "Meeting tomorrow"
       "Show my calendar" ← Should NOT list events
Expected: Agent continues collecting meeting details
```

#### TC4: Explicit Cancel
```
Input: "Add event"
       "cancel"
Expected: Task cancelled, state cleared
```

#### TC5: Slot Filling
```
Input: "Schedule meeting"
       "with chef"
       "tomorrow"
       "at 2pm"
Expected: All slots filled incrementally
```

#### TC6: Multiple Calendars
```
Input: "Add event tomorrow at 2pm"
       "yes" (to confirm)
Expected: Provider selection prompt if both Google and Outlook connected
```

---

## MIGRATION NOTES

### Breaking Changes

**None** - This is an enhancement to existing calendar functionality.

### Backward Compatibility

✅ Old calendar creation flows still work
✅ Existing slot extraction enhanced
✅ New intent normalization is additive

### Configuration

No configuration changes required.

---

## MONITORING

### Log Messages

Key log entries to monitor:

```
[INTENT] CALENDAR_CREATE detected: 'note down meeting' (type: EVENT)
[CALENDAR_PERSIST] Active calendar task detected - continuing creation flow
[CAL_CONFIRM] Event preview shown: Meeting With Chef on 2026-02-10 at 14:00
[CAL_CREATE] Creating event 'Meeting With Chef' via google
[ACTION_HISTORY] Recorded: create_calendar_event → EVENT_CREATED
```

### Error Scenarios

```
[CAL_CREATE] ⚠️ Event not created - status: error
[ACTION_HISTORY] Recorded: create_calendar_event → EVENT_FAILED
```

---

## TROUBLESHOOTING

### Issue: Agent lists events during creation

**Cause:** Task persistence not enforced  
**Fix:** Check active task lock in `_handle_calendar_intent()`

### Issue: Slots not extracted

**Cause:** Regex patterns in SlotExtractor not matching  
**Fix:** Review `SlotExtractor.extract_calendar_slots()` patterns

### Issue: Event not created but agent says it was

**Cause:** Action Truth Rule violation  
**Fix:** Check `_execute_calendar_create()` status checking logic

### Issue: User can't cancel event creation

**Cause:** Cancel keywords not detected  
**Fix:** Verify cancel_keywords list in `_handle_calendar_create()`

---

## FUTURE ENHANCEMENTS

### Planned
- [ ] Recurring events support
- [ ] Attendee management for EVENTs
- [ ] Event editing/updating
- [ ] Event deletion with confirmation
- [ ] Time zone handling
- [ ] Calendar sync status

### Under Consideration
- [ ] Natural language date parsing improvements
- [ ] Voice-to-calendar integration
- [ ] Smart event suggestions
- [ ] Conflict detection

---

## RELATED DOCUMENTATION

- `SEMANTIC_SLOT_EXTRACTION.md` - Slot extraction rules
- `ACTIVE_TASK_LOCK.md` - Task persistence mechanism
- `ACTION_HISTORY_IMPLEMENTATION.md` - Action recording
- `EXECUTIVE_AGENT_GUIDE.md` - Overall agent architecture

---

## CHANGELOG

### v1.0 - February 9, 2026
- ✅ Intent normalization for CALENDAR_CREATE
- ✅ Support for EVENT and PERSONAL_NOTE types
- ✅ Task persistence rules implementation
- ✅ Semantic slot extraction for calendar
- ✅ Confirmation flow with type display
- ✅ Action truth rule enforcement
- ✅ Multi-calendar provider support

---

**Document Version:** 1.0  
**Last Updated:** February 9, 2026  
**Author:** AI Implementation Team  
**Status:** Production Ready ✅
