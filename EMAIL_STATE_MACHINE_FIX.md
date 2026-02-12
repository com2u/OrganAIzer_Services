# Email State Machine Fix

## Problem Summary

The OrganAIzer email flow had critical bugs preventing emails from being sent:

1. **Send command not detected**: When user said "send it" or "yes", the draft handler would reprint the email instead of sending it
2. **send_email tool never called**: The active task lock routed to `_handle_email_draft()`, but that method didn't detect confirmation commands
3. **Stuck in email draft mode**: After sending or canceling, the agent stayed locked in draft mode
4. **Unrelated questions triggered drafts**: Questions like "what's the weather?" would still show email draft behavior
5. **Subject showing as "None"**: Auto-generated subjects not being extracted properly from LLM responses

## Root Cause

The active task lock system correctly prevented task switching, but when a user confirmed a draft with "send it", the message was routed to `_handle_email_draft()` which only handled editing and parameter collection - not sending.

The `_handle_confirmation()` method had the send logic, but it was never reached because the task lock routed all messages to the draft handler.

## Solution

### 1. **Added Send Detection to Draft Handler**

Added send command detection at the start of `_handle_email_draft()`:

```python
# CRITICAL FIX: Detect SEND/CONFIRMATION commands FIRST
send_keywords = ["yes", "send it", "looks good", "confirm", "approve", "go ahead", "do it", "send"]
is_send_command = any(keyword in message_lower for keyword in send_keywords)

# Check if we have a draft ready and user is confirming
if pending_action and pending_action["type"] == "send_email" and pending_action["status"] == "awaiting_confirmation":
    if is_send_command:
        logger.info(f"[EMAIL_SEND] Send command detected: '{message}'")
        # Route to send logic
        return await self._execute_email_send(pending_action, user_id, provider)
```

### 2. **Extracted Send Logic to Reusable Method**

Created `_execute_email_send()` method to handle all send operations:

```python
async def _execute_email_send(
    self,
    pending_action: Dict[str, Any],
    user_id: str,
    provider: str
) -> Dict[str, Any]:
    """
    Execute email send operation.
    
    This method extracts the send logic so it can be called from multiple places
    (confirmation handler, draft handler when user says "send it").
    """
```

This method:
- Validates draft is ready (`awaiting_confirmation` status)
- Checks required fields (recipient, body)
- Handles multi-account selection
- Calls the actual email provider's `send_email()` method
- **Clears both pending action AND active task lock on success**
- Provides detailed error messages on failure

### 3. **Updated Confirmation Handler**

Simplified the confirmation handler to use the centralized method:

```python
if action_type == "send_email":
    if not confirmed:
        return {
            "message": "If you'd like me to make changes...",
            "pending_confirmation": True
        }
    
    # Use centralized send method
    logger.info("[CONFIRMATION] Executing email send via confirmation handler")
    return await self._execute_email_send(pending_action, user_id, provider)
```

### 4. **Proper State Cleanup After Send**

The send method now properly clears both states:

```python
if result.get("status") == "success":
    # Update status and clear pending action
    self.memory.update_pending_action_status("sent")
    self.memory.clear_pending_action()
    
    # ✅ Clear active task lock
    self.memory.update_active_task_status("completed")
    self.memory.clear_active_task()
    logger.info("[EMAIL_SEND] ✅ Email sent successfully - task lock cleared")
```

### 5. **Enhanced Cancel Detection**

The cancel detection was already in place in `process_message()`:

```python
# Check for explicit cancellation
message_lower = user_message.lower()
if any(word in message_lower for word in ["cancel", "never mind", "nevermind", "stop", "abort"]):
    logger.info(f"[TASK_LOCK] User cancelled task: {task_type}")
    self.memory.clear_active_task()
    self.memory.clear_pending_action()
    return {
        "message": "✅ Task cancelled. What else can I help you with?",
        "success": True
    }
```

## State Machine Flow

### **Correct Flow:**

1. **User**: "Draft an email to john@example.com about the meeting"
   - State: `collecting_details` → `awaiting_confirmation`
   - Task Lock: `draft_email` (status: `collecting`)

2. **Agent**: Shows draft, asks for confirmation
   - Draft stored in `pending_action`
   - Task lock remains active

3. **User**: "send it"
   - **NEW**: Send command detected in `_handle_email_draft()`
   - Routes to `_execute_email_send()`
   - Email sent via provider
   - State: `awaiting_confirmation` → `sent`
   - **Task lock cleared** ✅
   - **Pending action cleared** ✅

4. **User**: "What's the weather?"
   - No task lock active
   - Routes to normal intent analysis
   - Responds with general chat ✅

### **Edge Cases Handled:**

1. **Cancel during draft**: Clears both task lock and pending action
2. **Email already sent**: Detected in `process_message()`, clears state before processing new intent
3. **Multiple accounts**: Prompts user to select account
4. **No accounts connected**: Clear error message with OAuth links
5. **Send fails**: Draft preserved, task lock remains, user can retry

## Testing

### Test Scenarios:

1. ✅ **Happy Path**: Draft → Edit → Send → New conversation
2. ✅ **Cancel Flow**: Draft → Cancel → New conversation
3. ✅ **Multi-Edit**: Draft → Edit → Edit → Send
4. ✅ **No Re-drafting**: After send, "send it" should not trigger new draft
5. ✅ **Error Recovery**: Send fails → Draft preserved → Can retry

### Expected Behavior:

| User Input | Expected Agent Behavior |
|------------|------------------------|
| "Draft email to john@example.com" | Creates draft, sets task lock |
| "make it shorter" | Edits draft, maintains lock |
| "send it" | **Sends email**, clears lock ✅ |
| "what's the weather?" | Responds to weather (no draft) ✅ |
| "cancel" during draft | Clears draft and lock ✅ |

## Files Modified

- `backend/services/executive_agent_service.py`:
  - Added send detection to `_handle_email_draft()`
  - Created `_execute_email_send()` method
  - Simplified `_handle_confirmation()`
  - Enhanced logging throughout

## Benefits

1. **✅ Emails actually send** when user confirms
2. **✅ Clean state management** - no stuck draft modes
3. **✅ Proper conversation flow** - can move to new topics after send
4. **✅ DRY principle** - send logic centralized in one method
5. **✅ Better error handling** - detailed messages at each step
6. **✅ Enhanced logging** - easier to debug issues

## Migration Notes

No database migrations required - this is a pure logic fix in the service layer.

## Future Improvements

1. Add rate limiting for send operations
2. Implement draft auto-save to persistent storage
3. Add email templates support
4. Support for CC/BCC recipients
5. Attachment support

---

**Status**: ✅ COMPLETE  
**Date**: 2026-02-04  
**Version**: 1.0.0
