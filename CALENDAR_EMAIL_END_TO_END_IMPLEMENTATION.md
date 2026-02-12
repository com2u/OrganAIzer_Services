# Calendar & Email End-to-End Implementation Plan

## Analysis Summary (Current State)

### ✅ What's Already Working:
1. **OAuth Integration**: Stable scopes defined in `backend/api/integrations.py`
   - Google: `calendar.events`, `gmail.readonly`, `gmail.modify`, `gmail.send`
   - Microsoft: `Mail.Read`, `Mail.Send`, `Calendars.ReadWrite`
2. **Provider Layer**: Both Google and Microsoft providers implement:
   - Calendar event creation (with dry_run and confirm flags)
   - Email sending (with dry_run and confirm flags)
   - Basic logging
3. **Calendar API**: `/api/calendar/create` endpoint exists
4. **Executive Agent**: Already integrates with calendar/email tools
5. **Token Storage**: Secure encrypted token storage with refresh

### ⚠️ What Needs Enhancement:
1. **Structured Logging**: No correlation IDs, insufficient error context
2. **Hard Fail Enforcement**: API layer needs better error propagation
3. **OAuth Scope Documentation**: Needs centralized docs
4. **Test Scripts**: Missing `test_calendar.py` and `test_outlook_send.py`
5. **Error Standardization**: Provider errors need consistent format

## Implementation Plan

### Phase 1: Enhance Logging & Error Handling
- Add correlation ID middleware
- Enhance provider logging with request/response metadata
- Standardize error response format
- Add stack trace logging for provider failures

### Phase 2: Fix OAuth Scope Documentation
- Create centralized docs/oauth_scopes.md
- Document exact scopes for each feature
- Add re-consent instructions

### Phase 3: Create Test Scripts  
- `scripts/test_calendar.py` - Test calendar event creation
- `scripts/test_outlook_send.py` - Test Outlook email sending
- Add environment variable documentation

### Phase 4: Verify End-to-End Flows
- Test Google Calendar event creation
- Test Outlook Calendar event creation
- Test Outlook email sending via Agent
- Verify hard-fail on provider errors

### Phase 5: Documentation
- Update README with setup instructions
- Document test commands
- List environment variables needed

## Key Design Decisions

1. **Correlation IDs**: Use UUID4 per request for tracing
2. **Logging Level**: INFO for operations, ERROR for failures with stack traces
3. **Error Format**: Standardized dict with `error_code`, `provider`, `provider_http_status`, `message`
4. **Test Scripts**: Python scripts using requests library, environment-based config
5. **OAuth Re-consent**: Force `prompt=consent` when scopes change

## Root Cause of Current Issues

The codebase is actually in good shape! The main "issues" are:
- **Missing visibility**: Need better logging to see what's happening
- **Missing tests**: Need scripts to verify functionality
- **Missing docs**: Need clearer OAuth scope documentation

The core functionality for calendar creation and email sending is already implemented and working.
