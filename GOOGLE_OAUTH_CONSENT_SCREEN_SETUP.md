# Google OAuth Consent Screen Configuration Guide

## Important: Scope Configuration Issue

**Critical Understanding:** Scopes requested in your application code do NOT automatically appear in the Google OAuth consent screen's "Data access" section. This is a common source of confusion and can cause OAuth failures.

### The Problem

When you define scopes in your code (e.g., `backend/api/integrations.py`, `server.js`, `backend/services/google_service.py`), these scopes are sent during the OAuth flow, but Google will **reject** them if they haven't been explicitly added to your OAuth consent screen configuration in Google Cloud Console.

### The Solution

You must **manually add scopes** in Google Cloud Console → OAuth consent screen → Data access section.

---

## 📋 Current Required Scopes

The application uses the following scopes (as of the latest update):

### Gmail Scopes (Unchanged)
- `https://www.googleapis.com/auth/gmail.send` - Send emails on behalf of user
- `https://www.googleapis.com/auth/gmail.readonly` - Read emails from user's mailbox

### Calendar Scope (Updated)
- `https://www.googleapis.com/auth/calendar.events` - Manage calendar events
  - **Note:** Changed from `https://www.googleapis.com/auth/calendar` (full calendar access) to `calendar.events` (events only) for better security and scope minimization

### Identity Scopes (Automatic)
- `openid` - OpenID Connect authentication
- `https://www.googleapis.com/auth/userinfo.email` - User email address

---

## 🔧 Step-by-Step: Adding Scopes to OAuth Consent Screen

### Step 1: Access Google Cloud Console

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project (the one with your OAuth credentials)

### Step 2: Navigate to OAuth Consent Screen

1. In the left sidebar, go to **APIs & Services** → **OAuth consent screen**
2. You should see your existing consent screen configuration

### Step 3: Add or Remove Scopes

1. Click **"EDIT APP"** button at the top
2. Click **"SAVE AND CONTINUE"** on the first page (App information)
3. On the **"Scopes"** page, click **"ADD OR REMOVE SCOPES"**

### Step 4: Add Required Scopes

In the "Add or remove scopes" modal:

#### Method A: Using the Filter (Recommended)

1. **For Gmail scopes:**
   - In the filter box, type: `gmail.send`
   - Check the box for: `https://www.googleapis.com/auth/gmail.send`
   - Type: `gmail.readonly`
   - Check the box for: `https://www.googleapis.com/auth/gmail.readonly`

2. **For Calendar scope:**
   - In the filter box, type: `calendar.events`
   - Check the box for: `https://www.googleapis.com/auth/calendar.events`
   - **Important:** Do NOT select `https://www.googleapis.com/auth/calendar` (full calendar access)

#### Method B: Manual Entry

1. Scroll to the bottom of the modal
2. Click **"MANUALLY ADD SCOPES"**
3. In the text area, paste each scope on a new line:
   ```
   https://www.googleapis.com/auth/gmail.send
   https://www.googleapis.com/auth/gmail.readonly
   https://www.googleapis.com/auth/calendar.events
   ```
4. Click **"ADD TO TABLE"**

### Step 5: Verify Scopes

After adding scopes, you should see them in the "Your sensitive scopes" or "Your restricted scopes" table:

| API | Scope | User-facing Description |
|-----|-------|------------------------|
| Gmail API | `../auth/gmail.send` | Send email on your behalf |
| Gmail API | `../auth/gmail.readonly` | View your email messages and settings |
| Google Calendar API | `../auth/calendar.events` | View and edit events on all your calendars |

### Step 6: Save Configuration

1. Click **"UPDATE"** at the bottom of the modal
2. Click **"SAVE AND CONTINUE"** on the Scopes page
3. Review Test users (add yourself if not already there)
4. Click **"SAVE AND CONTINUE"**
5. Review the summary page
6. Click **"BACK TO DASHBOARD"**

---

## ⚠️ Re-Consent Required for Existing Users

### Why Re-Consent is Needed

When you change scopes (add new ones or modify existing ones), users who previously authorized your app will **NOT** automatically get the new permissions. They must re-consent to grant the new scopes.

### Scenarios Requiring Re-Consent

1. **Adding new scopes** (e.g., adding `calendar.events`)
2. **Changing scope granularity** (e.g., from `calendar` to `calendar.events`)
3. **Removing and re-adding scopes** in the consent screen
4. **Users who see "insufficient permissions" errors**

### How to Force Re-Consent

There are two methods to force users to re-consent:

#### Method 1: Add `prompt=consent` to OAuth URL (Recommended)

The application already includes this in the OAuth flow:

```python
# backend/api/integrations.py
authorization_url, _ = flow.authorization_url(
    access_type='offline',
    include_granted_scopes='true',
    prompt='consent'  # Forces consent screen every time
)
```

This ensures users always see the consent screen and can grant new permissions.

#### Method 2: Revoke Application Access

Users can manually revoke access and re-authenticate:

1. **For users to revoke access:**
   - Go to [Google Account Permissions](https://myaccount.google.com/permissions)
   - Find your application name
   - Click **"Remove Access"**
   - Re-authenticate through your application

2. **For developers to test:**
   - Delete stored tokens (e.g., `backend/data/user_settings/default_user_google.json`)
   - Clear browser cookies for your application
   - Restart the OAuth flow from `/api/integrations/google/auth/start`

---

## 🧪 Testing the Configuration

### Verify Scopes are Configured Correctly

1. **Check the OAuth consent screen:**
   - Go to Google Cloud Console → OAuth consent screen
   - You should see the scopes listed in the "Scopes" section
   - Click "VIEW SCOPES" to see all configured scopes

2. **Test the OAuth flow:**
   - Start your application
   - Navigate to: `http://localhost:8000/api/integrations/google/auth/start`
   - Sign in with your Google account
   - **On the consent screen, verify you see:**
     - "Send email on your behalf" (Gmail send)
     - "View your email messages and settings" (Gmail readonly)
     - "View and edit events on all your calendars" (Calendar events)
   - Grant permissions
   - Verify successful token exchange

3. **Check granted scopes in response:**
   After successful OAuth, the callback response should include:
   ```json
   {
     "status": "success",
     "message": "Google account connected successfully",
     "scopes": [
       "openid",
       "https://www.googleapis.com/auth/userinfo.email",
       "https://www.googleapis.com/auth/calendar.events",
       "https://www.googleapis.com/auth/gmail.readonly",
       "https://www.googleapis.com/auth/gmail.send"
     ],
     "has_refresh_token": true
   }
   ```

### Common Verification Errors

#### Error: "access_denied" or "unauthorized_client"
- **Cause:** Scopes in code don't match scopes in consent screen
- **Fix:** Add missing scopes to OAuth consent screen (see Step 3-6 above)

#### Error: "invalid_scope"
- **Cause:** Typo in scope URL or scope doesn't exist
- **Fix:** Double-check scope URLs match exactly:
  - ✓ `https://www.googleapis.com/auth/calendar.events`
  - ✗ `https://www.googleapis.com/auth/calendar.event` (missing 's')

#### Error: Consent screen shows different scopes than expected
- **Cause:** Code and consent screen are out of sync
- **Fix:** Update consent screen to match code scopes

---

## 📝 Scope Update Checklist

When updating scopes in your application:

- [ ] **Update code files:**
  - [ ] `backend/api/integrations.py` - GOOGLE_SCOPES list
  - [ ] `server.js` - SCOPES array
  - [ ] `backend/services/google_service.py` - SCOPES list
  - [ ] Any other files that define scopes

- [ ] **Update Google Cloud Console:**
  - [ ] Navigate to OAuth consent screen
  - [ ] Click "EDIT APP"
  - [ ] Go to Scopes section
  - [ ] Click "ADD OR REMOVE SCOPES"
  - [ ] Add new scopes / remove old scopes
  - [ ] Verify scopes list is correct
  - [ ] Save changes

- [ ] **Update documentation:**
  - [ ] Update README files with new scope requirements
  - [ ] Update setup guides
  - [ ] Document any permission changes for users

- [ ] **Notify users:**
  - [ ] Inform existing users about permission changes
  - [ ] Explain what new permissions enable
  - [ ] Provide instructions for re-authenticating

- [ ] **Test thoroughly:**
  - [ ] Test OAuth flow with new scopes
  - [ ] Verify all scopes are granted
  - [ ] Test API calls that use new scopes
  - [ ] Test with fresh user (no prior tokens)
  - [ ] Test re-consent flow for existing user

---

## 🔒 Security Best Practices

### Principle of Least Privilege

Always request the **minimum scopes** necessary for your application:

- ✓ **Good:** `calendar.events` - Only manage events
- ✗ **Bad:** `calendar` - Full calendar access (includes settings, ACLs, etc.)

### Scope Granularity

Google provides different granularity levels for scopes:

**Calendar Scopes:**
- `calendar` - Full access (read/write calendars, events, settings)
- `calendar.events` - Read/write events only ✓ **Use this**
- `calendar.events.readonly` - Read events only
- `calendar.readonly` - Read all calendar data

**Gmail Scopes:**
- `gmail.modify` - Read and modify (not delete) emails
- `gmail.readonly` - Read emails only ✓ **We use this**
- `gmail.send` - Send emails only ✓ **We use this**
- `gmail.compose` - Create drafts

### Incremental Authorization

Consider requesting scopes only when needed:

1. Start with basic scopes (email, profile)
2. Request Gmail scopes when user wants email features
3. Request Calendar scopes when user wants calendar features

**Note:** Current implementation requests all scopes upfront for simplicity.

---

## 🐛 Troubleshooting

### Issue: "This app isn't verified" warning

**Cause:** Your app is in testing mode and not verified by Google.

**Solutions:**
- **For testing:** Add users as "Test users" in OAuth consent screen
- **For production:** Submit app for verification (required after 100 users)

### Issue: Scopes don't appear in "Data access" table

**Cause:** Scopes must be manually added; they don't auto-populate from code.

**Solution:** Follow Steps 3-6 above to manually add scopes.

### Issue: User granted permissions but API calls fail with 403

**Cause:** User granted old scopes; new scopes weren't included.

**Solution:** Force re-consent (revoke access and re-authenticate).

### Issue: Refresh token not received

**Cause:** Missing `access_type='offline'` or user already consented before.

**Solution:** 
- Ensure `access_type='offline'` in authorization URL
- Use `prompt='consent'` to force consent screen
- Have user revoke access and re-authenticate

---

## 📚 Additional Resources

- [Google OAuth 2.0 Scopes](https://developers.google.com/identity/protocols/oauth2/scopes)
- [Gmail API Scopes](https://developers.google.com/gmail/api/auth/scopes)
- [Google Calendar API Scopes](https://developers.google.com/calendar/api/auth)
- [OAuth Consent Screen Configuration](https://support.google.com/cloud/answer/10311615)
- [Incremental Authorization](https://developers.google.com/identity/protocols/oauth2/web-server#incrementalAuth)

---

## 📞 Summary

**Remember:**

1. ✅ **Scopes in code** define what your app requests
2. ✅ **Scopes in consent screen** define what Google allows
3. ✅ **Both must match** for OAuth to work
4. ✅ **Use `calendar.events`** (not `calendar`) for better security
5. ✅ **Force re-consent** when scopes change
6. ✅ **Test thoroughly** after any scope changes

This is a **configuration issue**, not an agent logic issue. The code is correct; the Google Cloud Console configuration must be updated manually.
