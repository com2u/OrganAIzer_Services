# Semantic Slot Extraction - Implementation Guide

## Overview

This document describes the **Semantic Slot Extraction** system implemented in OrganAIzer's Executive Agent. This intelligent parsing layer makes the agent feel natural and human-like by extracting structured data from conversational input **without re-asking for information already provided**.

## The Problem It Solves

### Before Semantic Parsing ❌
```
User: "Meeting with Chef at 08:00"
Agent: "What should I call this event?"  ← WRONG! Title already provided
```

### After Semantic Parsing ✅
```
User: "Meeting with Chef at 08:00"
Agent: "📅 Got it! Here's what I understood:
       - Event: Meeting with Chef
       - Time: 08:00
       
       When should this be scheduled?"  ← Smart extraction!
```

## Critical Rules

### 1. **MANDATORY SEMANTIC PARSING**
For **EVERY user message**, the agent MUST:
- Parse the message for ALL known entities and slots
- Extract values even if they appear inside full sentences
- Lock any slot that can be confidently extracted
- NEVER re-ask for a slot that was already extracted

### 2. **Slot Locking**
Once a slot is extracted and filled:
- It becomes **locked** and won't be overwritten
- The agent NEVER asks for it again
- Only explicit user edits can change it

### 3. **Natural Language Understanding**
The agent treats natural sentences as structured data:
- "Meeting with Chef at 08:00" → `{title: "Meeting with Chef", time: "08:00"}`
- "Email john@example.com about the project" → `{to_email: "john@example.com", subject: "the project"}`

## Architecture

### Core Components

#### 1. SlotExtractor Class (`backend/utils/slot_extraction.py`)
Central extraction engine with methods for:
- `extract_calendar_slots()` - Extracts calendar event data
- `extract_email_slots()` - Extracts email draft data
- `get_missing_slots()` - Identifies what's still needed
- `format_confirmation()` - Creates smart confirmation messages

#### 2. Integration Points
The SlotExtractor is called at key points in the conversation flow:

**Email Drafting:**
```python
# NEW DRAFT - extract initial info
extracted = SlotExtractor.extract_email_slots(message, existing_slots=email_slots)
email_slots.update(extracted)

# EXISTING DRAFT - extract additional info
extracted = SlotExtractor.extract_email_slots(message, existing_slots=email_slots)
# Only extract what's not already locked
```

**Calendar Creation:**
```python
# Extract calendar slots with locking
extracted = SlotExtractor.extract_calendar_slots(message, existing_slots=calendar_slots)
calendar_slots.update(extracted)
```

## Calendar Slot Extraction

### Extracted Slots

| Slot | Required | Examples | Notes |
|------|----------|----------|-------|
| `title` | ✅ Yes | "Meeting with Chef", "Team Standup" | Event name/description |
| `date` | ✅ Yes | "tomorrow", "next Monday", "2024-12-25" | Relative or absolute dates |
| `time` | ✅ Yes | "08:00", "2pm", "14:30" | 12h or 24h format |
| `duration` | ❌ No | "30 minutes", "2 hours" | Defaults to 30 min |
| `location` | ❌ No | "Conference Room A", "Building 5" | Physical location |
| `provider` | ❌ No | "google", "outlook" | Which calendar to use |

### Extraction Patterns

#### Title Extraction
```python
# Pattern 1: "schedule X at Y"
"schedule meeting with Chef at 08:00" → "Meeting with Chef"

# Pattern 2: "X at Y" (before time marker)
"Team standup at 9am" → "Team Standup"

# Pattern 3: "X tomorrow"
"Dentist appointment tomorrow" → "Dentist Appointment"
```

#### Time Extraction
```python
# 24-hour format
"08:00" → "08:00"
"14:30" → "14:30"

# 12-hour format
"2pm" → "14:00"
"9:30am" → "09:30"

# Time keywords
"morning" → "09:00"
"afternoon" → "14:00"
"evening" → "18:00"
```

#### Date Extraction
```python
# Relative dates
"today" → current date
"tomorrow" → current date + 1 day
"next Monday" → date of next Monday

# Absolute dates
"2024-12-25" → "2024-12-25"
"12/25/2024" → "2024-12-25"
```

### Complete Example

```python
User: "Meeting with Chef at 08:00 tomorrow for 2 hours"

Extracted:
{
  "title": "Meeting with Chef",
  "time": "08:00",
  "date": "2024-02-09",  # tomorrow's date
  "duration": 120,        # 2 hours = 120 minutes
}

Agent Response:
"📅 Got it! Here's what I understood:
- Event: Meeting with Chef
- Date: Tomorrow (Saturday, February 9)
- Time: 08:00
- Duration: 120 minutes

Which calendar should I add this to? (Google / Outlook)"
```

## Email Slot Extraction

### Extracted Slots

| Slot | Required | Examples | Notes |
|------|----------|----------|-------|
| `to_email` | ✅ Yes | "john@example.com" | Validated email address |
| `to_name` | ❌ No | "John Smith" | Display name |
| `subject` | ❌ No | "Project Update" | Auto-generated if missing |
| `body` | ✅ Yes | Email content | The actual message |

### Extraction Patterns

#### Email Address Extraction
```python
# Direct extraction with regex
"john@example.com" → "john@example.com"
"Email jane.doe@company.org" → "jane.doe@company.org"
```

#### Subject Extraction
```python
# Pattern 1: "subject: X"
"subject: Project Update" → "Project Update"

# Pattern 2: "about X"
"about the meeting tomorrow" → "the meeting tomorrow"
```

### Complete Example

```python
User: "Email john@example.com about the quarterly review"

Extracted:
{
  "to_email": "john@example.com",
  "subject": "the quarterly review"
}

Agent Response:
"📧 Got it! Here's what I understood:
- To: john@example.com
- Subject: the quarterly review

What should the email say?"
```

## Forbidden Behaviors

### ❌ DO NOT:
1. **Repeat questions for extracted information**
   ```
   User: "Meeting at 08:00"
   Agent: "What time should it be?" ← FORBIDDEN!
   ```

2. **Ignore structured info in sentences**
   ```
   User: "Schedule team standup tomorrow at 9am"
   Agent: "What should I call it?" ← FORBIDDEN! Title is "Team Standup"
   ```

3. **Treat natural language as invalid**
   ```
   User: "tomorrow afternoon"
   Agent: "Please provide a valid date" ← FORBIDDEN! Parse it!
   ```

4. **Ask the same question twice**
   ```
   User: "Meeting with Chef"
   Agent: "What's the title?"
   User: "Team meeting"
   Agent: "What should I call it?" ← FORBIDDEN! Already answered
   ```

### ✅ DO:
1. **Confirm what was understood**
   ```
   Agent: "Got it! Event is 'Meeting with Chef' at 08:00 tomorrow. Is that correct?"
   ```

2. **Ask for different missing slots**
   ```
   Agent: "Which calendar should I add this to? (Google / Outlook)"
   ```

3. **Handle ambiguity gracefully**
   ```
   User: "Schedule it for 2"
   Agent: "Do you mean 2:00 AM or 2:00 PM?"
   ```

## Intelligent Default Behavior

### Multi-Slot Messages
When a message contains BOTH title and time:
```python
User: "Meeting with Chef at 08:00"

# Agent should:
1. Extract BOTH pieces of information
2. Store them in respective slots
3. Ask for the NEXT missing piece (e.g., date)

# NOT ask for the title again ❌
```

### Incremental Building
The agent builds understanding incrementally:
```
Turn 1
User: "Schedule a meeting"
Agent: "What should I call this event?"

Turn 2  
User: "Team standup"
Slots: {title: "Team standup"}
Agent: "When should this be scheduled?"

Turn 3
User: "Tomorrow at 9am"
Slots: {title: "Team standup", date: "2024-02-09", time: "09:00"}
Agent: "Got it! Event 'Team standup' on Saturday, February 9 at 9:00 AM..."
```

## Implementation Details

### Slot Locking Mechanism

```python
def extract_calendar_slots(message: str, existing_slots: Optional[Dict] = None):
    existing = existing_slots or {}
    extracted = {}
    
    # CRITICAL: Check if title already exists
    if not existing.get("title"):
        title = _extract_title(message, message_lower)
        if title:
            extracted["title"] = title
            # Title is now LOCKED
    
    # Similar for other slots...
    return extracted
```

### State Management

```python
# Initial extraction
email_slots = {
    "to_email": None,
    "subject": None,
    "body": None,
}

# First message: "Email john@example.com"
extracted = SlotExtractor.extract_email_slots(message, existing_slots=email_slots)
# extracted = {"to_email": "john@example.com"}
email_slots.update(extracted)
# email_slots = {"to_email": "john@example.com", "subject": None, "body": None}

# Second message: "about the project"
extracted = SlotExtractor.extract_email_slots(message, existing_slots=email_slots)
# extracted = {"subject": "the project"}  ← to_email NOT re-extracted
email_slots.update(extracted)
# email_slots = {"to_email": "john@example.com", "subject": "the project", "body": None}
```

## Testing the Implementation

### Unit Tests
```python
def test_calendar_slot_extraction():
    # Test 1: Full extraction
    message = "Meeting with Chef at 08:00 tomorrow"
    slots = SlotExtractor.extract_calendar_slots(message)
    
    assert slots["title"] == "Meeting with Chef"
    assert slots["time"] == "08:00"
    assert "date" in slots  # tomorrow's date
    
    # Test 2: Slot locking
    existing = {"title": "Team Standup"}
    message = "Project Review"
    slots = SlotExtractor.extract_calendar_slots(message, existing)
    
    assert "title" not in slots  # Already locked!
```

### Integration Tests
```python
async def test_calendar_creation_flow():
    agent = ExecutiveAgent()
    
    # Turn 1: Provide all info at once
    response = await agent.process_message(
        "Schedule Meeting with Chef tomorrow at 08:00"
    )
    
    # Agent should extract all slots and only ask for calendar provider
    assert "Meeting with Chef" in response["message"]
    assert "tomorrow" in response["message"].lower()
    assert "08:00" in response["message"]
    assert "which calendar" in response["message"].lower()
```

## Why This Matters

### User Experience Impact

**Before Semantic Parsing:**
- Feels robotic
- Requires structured input
- Frustrating multi-turn conversations
- Users have to repeat themselves

**After Semantic Parsing:**
- Feels natural and smart
- Understands conversational input
- Efficient single-turn interactions
- Never asks twice for same information

### The Difference
```
Before:
User: "Meeting with Chef at 08:00"
Agent: "What should I call this event?"
User: "I just told you - Meeting with Chef!"
Agent: "What time?"
User: "08:00! I JUST SAID THAT!"

After:
User: "Meeting with Chef at 08:00"
Agent: "📅 Got it! Meeting with Chef at 08:00. When should this be?"
User: "Tomorrow"
Agent: "Perfect! Creating 'Meeting with Chef' tomorrow at 08:00..."
```

## Future Enhancements

1. **Contextual Understanding**
   - "Schedule another meeting with Chef" → Inherit previous context
   - "Same time tomorrow" → Use last meeting's time

2. **Ambiguity Resolution**
   - "Schedule a meeting at 2" → Ask "2 AM or 2 PM?"
   - "Next Friday" when there are two Fridays → Clarify

3. **Multi-Entity Extraction**
   - "Schedule team standup at 9am and client call at 2pm" → Extract both events

4. **Learning from Corrections**
   - If user corrects extraction, learn patterns for future

## Conclusion

Semantic Slot Extraction transforms the Executive Agent from a rigid form-filler into an intelligent conversational partner. By extracting and locking information from natural language, it creates an experience that feels **smart, calm, and human**.

The key principle: **Treat LLM output as data, not conversation** - run slot extraction before deciding what to ask next.

---

**Implementation Files:**
- `backend/utils/slot_extraction.py` - Core extraction logic
- `backend/services/executive_agent_service.py` - Integration points
- This document - Comprehensive guide

**Status:** ✅ Fully Implemented and Integrated
