# Multi-Account Email Sending Fix - Implementation Guide

## Problem Summary

OrganAIzer had a critical issue with multi-account email sending:
- Users could have multiple authenticated email accounts (Gmail + Outlook)
- The agent didn't know which sender mailbox to use
- Backend fell back to 'default_user' or failed, causing loops and false "sent" confirmations
- No way to select or set a default sender account

## Solution Overview

Implemented a comprehensive multi-account email management system with:
1. Account discovery and listing
2. Default sender account settings
3. Sender account selection during email send
4. Multi-account aware email sending logic
5. Intelligent account auto-selection

## Backend Changes Implemented

### 1. User Settings Storage (`backend/utils/user_settings.py`)

**New File Created** - Manages user preferences including default email sender account.

**Key Features:**
- Stores user settings in JSON files (`data/user_settings/{user_id}_settings.json`)
- `get_default_sender_account(user_id)` - Retrieves default sender preference
- `set_default_sender_account(user_id, provider, account_id)` - Sets default sender
- Thread-safe singleton pattern

**Usage Example:**
```python
from utils.user_settings import get_user_settings

user_settings = get_user_settings()
default = user_settings.get_default_sender_account("default_user")
# Returns: {"provider": "gmail", "account_id": "default_user"} or None
```

### 2. Email Providers - Get User Email (`backend/services/providers/`)

**Added Methods:**
- `GoogleEmailProvider.get_user_email()` - Returns Gmail address
- `MicrosoftEmailProvider.get_user_email()` - Returns Outlook address

**Implementation:**
- Gmail: Uses `users().getProfile()` API
- Outlook: Uses Microsoft Graph `/me` endpoint with `mail` or `userPrincipalName`

### 3. Email API Enhancements (`backend/api/email.py`)

#### New Endpoint: `GET /email/accounts`

Lists all connected email accounts for a user.

**Request:**
```
GET /api/email/accounts?user_id=default_user
```

**Response:**
```json
{
  "accounts": [
    {
      "provider": "gmail",
      "account_id": "default_user",
      "email_address": "user@gmail.com",
      "display_name": "user",
      "is_default": true
    },
    {
      "provider": "outlook",  
      "account_id": "default_user",
      "email_address": "user@outlook.com",
      "display_name": "user",
      "is_default": false
    }
  ],
  "count": 2
}
```

**Auto-Default Behavior:**
- If exactly 1 account exists and no default is set → Auto-sets it as default
- Returns `is_default: true` for the default account

#### New Endpoint: `POST /email/accounts/set-default`

Sets the default sender account for a user.

**Request:**
```
POST /api/email/accounts/set-default?provider=gmail&account_id=default_user&user_id=default_user
```

**Response:**
```json
{
  "message": "Default sender account set to gmail",
  "provider": "gmail",
  "account_id": "default_user"
}
```

#### Updated Endpoint: `POST /email/send`

Enhanced with multi-account logic.

**Key Changes:**
- `provider` parameter now optional (auto-detected)
- Multi-account detection and validation
- Default sender account support
- Structured error responses for account selection

**Multi-Account Flow:**

1. **No Accounts:** Returns error with OAuth links
2. **Single Account:** Auto-selects the account
3. **Multiple Accounts + Default Set:** Uses default
4. **Multiple Accounts + No Default:** Returns `MISSING_SENDER_ACCOUNT` error

**MISSING_SENDER_ACCOUNT Error Response:**
```json
{
  "detail": {
    "error": "MISSING_SENDER_ACCOUNT",
    "message": "Multiple email accounts detected. Please specify which account to send from.",
    "accounts": [
      {"provider": "gmail", "email": "user@gmail.com"},
      {"provider": "outlook", "email": "user@outlook.com"}
    ]
  }
}
```

### 4. Executive Agent Multi-Account Support (`backend/services/executive_agent_service.py`)

**Enhanced Email Sending Logic:**

The `_handle_confirmation` method now implements a sophisticated multi-account workflow:

```python
# 1. Check connected accounts
google_tokens = token_storage.load_tokens(user_id, "google")
microsoft_tokens = token_storage.load_tokens(user_id, "microsoft")
account_count = (1 if google_tokens else 0) + (1 if microsoft_tokens else 0)

# 2. Auto-select if single account
if account_count == 1:
    selected_provider = "gmail" if google_tokens else "outlook"

# 3. Use default if set
else:
    default_sender = user_settings.get_default_sender_account(user_id)
    if default_sender:
        selected_provider = default_sender["provider"]
    
# 4. Ask user to select account
    else:
        # Show account picker with email addresses
        return {
            "message": "📬 **Which email account should I send from?**...",
            "needs_account_selection": True
        }
```

**Account Selection Handler:**

Users can reply with "gmail" or "outlook" to select the sender account. The agent:
- Detects account selection intent in `_analyze_intent()`
- Stores selected provider in pending action data
- Proceeds with email sending using selected account

**Success Confirmation:**

Now only confirms email was sent if `result.get("status") == "success"`:
```python
if result.get("status") == "success":
    return {
        "message": "✅ **Email sent successfully via Gmail!**",
        "email_sent": True,
        "provider_used": "gmail"
    }
else:
    return {
        "message": "⚠️ **Email not sent**",
        "error": "email_not_sent"
    }
```

## Frontend Considerations

### Recommended UI Enhancements

#### 1. Account Picker Modal

When `needs_account_selection: true` is received:

```typescript
if (response.needs_account_selection) {
  // Show modal with account selection buttons
  // - Gmail button
  // - Outlook button
  // - "Set as default" checkbox
}
```

#### 2. Account Management UI

Add settings page to:
- View connected accounts (`GET /email/accounts`)
- Set default sender
- Connect new accounts (OAuth links)

#### 3. Error Handling

Handle `MISSING_SENDER_ACCOUNT` error:
```typescript
if (error.detail?.error === "MISSING_SENDER_ACCOUNT") {
  const accounts = error.detail.accounts;
  // Show account picker with accounts list
}
```

## User Experience Flow

### Scenario 1: Single Account
```
User: "Draft an email to john@example.com about the meeting"
Agent: [Creates draft]
User: "Send it"
Agent: [Auto-selects Gmail] ✅ Email sent successfully via Gmail!
```

### Scenario 2: Multiple Accounts (First Time)
```
User: "Send it"
Agent: 📬 **Which email account should I send from?**
       You have multiple email accounts connected:
       📧 Gmail: user@gmail.com
       📧 Outlook: user@outlook.com
       Please reply with 'gmail' or 'outlook'
User: "gmail"
Agent: ✅ Email sent successfully via Gmail!
```

### Scenario 3: Multiple Accounts (Default Set)
```
User: "Send it"
Agent: [Uses default sender] ✅ Email sent successfully via Gmail!
```

## Testing Checklist

- [x] Create user settings storage
- [x] Add GET /email/accounts endpoint
- [x] Add POST /email/accounts/set-default endpoint
- [x] Update POST /email/send with multi-account logic
- [x] Add get_user_email() to providers
- [x] Update Executive Agent confirmation handler
- [ ] Test single account scenario
- [ ] Test multiple accounts with default
- [ ] Test multiple accounts without default
- [ ] Test account selection flow
- [ ] Test error cases (no accounts, invalid provider)

## API Integration Examples

### List User's Email Accounts

```bash
curl http://localhost:8000/api/email/accounts?user_id=default_user
```

### Set Default Sender

```bash
curl -X POST "http://localhost:8000/api/email/accounts/set-default?provider=gmail&account_id=default_user&user_id=default_user"
```

### Send Email (Multi-Account Aware)

```bash
curl -X POST http://localhost:8000/api/email/send \
  -H "Content-Type: application/json" \
  -d '{
    "to": ["recipient@example.com"],
    "subject": "Test",
    "body": "Hello",
    "dry_run": false,
    "confirm": true
  }' \
  -G --data-urlencode "user_id=default_user"
```

## Database Schema

### User Settings File Structure
```
data/user_settings/
  └── default_user_settings.json
```

**Example Content:**
```json
{
  "default_sender_account": {
    "provider": "gmail",
    "account_id": "default_user"
  }
}
```

## Security Considerations

1. **Token Validation:** Each account selection validates OAuth tokens exist
2. **User Isolation:** Settings are per-user (user_id based)
3. **No Credential Exposure:** Email addresses fetched securely via APIs
4. **Explicit Confirmation:** Email sending still requires `confirm=true`

## Migration Notes

### Existing Users

- No breaking changes for single-account users
- Multi-account users will be prompted to select on first send
- Can set default account to avoid future prompts

### Data Migration

No database migration needed - settings are created on-demand.

## Future Enhancements

1. **Account Aliases:** Allow users to name their accounts
2. **Per-Recipient Defaults:** Remember which account to use for specific recipients
3. **Account Switching UI:** Visual switcher in email compose
4. **Shared Mailboxes:** Support for delegated/shared mailboxes
5. **Account Health:** Show connection status for each account

## Troubleshooting

### "No email accounts connected"
**Solution:** User needs to authorize via OAuth:
- Gmail: `/oauth/google/authorize`
- Outlook: `/oauth/outlook/authorize`

###  "MISSING_SENDER_ACCOUNT" error persists
**Solution:** Set default account:
```bash
POST /api/email/accounts/set-default?provider=gmail&...
```

### Email shows as sent but wasn't
**Solution:** Check backend logs for actual send status. Only `status: "success"` means email was delivered.

## Summary

This implementation provides a robust solution for multi-account email management in OrganAIzer. Users can:
- ✅ Connect multiple email accounts (Gmail + Outlook)
- ✅ View all connected accounts
- ✅ Set a default sender account
- ✅ Select sender account when needed
- ✅ Auto-select when only one account exists
- ✅ Get accurate send confirmations

The system intelligently handles account selection, falling back to user prompts only when necessary, while ensuring emails are never sent from the wrong account.
