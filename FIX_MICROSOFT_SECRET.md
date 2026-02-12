# Fix Microsoft Client Secret - Step by Step Guide

## The Problem
Your current secret: `b9331284-00e5-47a6-b776-7342615eee19`

❌ This is the **Secret ID** (UUID format)  
✅ You need the **Secret VALUE** (random string of characters)

## Why This Happens
When you create a client secret in Azure Portal, you see TWO fields:
- **Secret ID**: A UUID like `b9331284-00e5-47a6-b776-7342615eee19`
- **Value**: The actual secret like `abc~XyZ1234567890...` ⚠️ **Only shown once!**

You accidentally copied the Secret ID instead of the Value.

## Solution: Generate a NEW Client Secret

### Step 1: Go to Azure Portal
1. Visit: https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade
2. Sign in with your Microsoft account
3. Find your app: **a2da9786-3455-435e-ba02-1df2b292b8a7**

### Step 2: Navigate to Certificates & Secrets
1. Click on your app name
2. In the left sidebar, click **"Certificates & secrets"**
3. You'll see your existing secret(s) listed with:
   - Description
   - Expires
   - **Secret ID** (the UUID you copied by mistake)
   - Value: `••••••••` (hidden)

### Step 3: Create a NEW Secret
⚠️ **Important:** The old secret's value cannot be retrieved. You must create a new one.

1. Click **"+ New client secret"**
2. Add a description (e.g., "OrganAIzer OAuth Secret")
3. Choose an expiration period (6 months, 12 months, or 24 months)
4. Click **"Add"**

### Step 4: Copy the CORRECT Value
🚨 **CRITICAL:** After clicking "Add", you'll see the new secret with these fields:

```
Description: OrganAIzer OAuth Secret
Secret ID: [Another UUID - DON'T copy this!]
Value: abc1~XyZ234567890aBcDeF... [Long random string - COPY THIS!]
Expires: 2027-01-26
```

**Copy the VALUE field immediately!** It will look like:
- Starts with random characters
- May contain `~` or other special characters
- Usually 30-40+ characters long
- Example format: `abc~123XYZ456def789...`

⚠️ **You can only see this value ONCE!** If you navigate away, you'll need to create another new secret.

### Step 5: Update Your .env File
Replace your current secret in `backend/.env`:

```env
# OLD (Secret ID - WRONG):
MICROSOFT_CLIENT_SECRET=b9331284-00e5-47a6-b776-7342615eee19

# NEW (Secret VALUE - CORRECT):
MICROSOFT_CLIENT_SECRET=Wxyz~1234567890aBcDeF...  # Paste the actual value here
```

### Step 6: Restart Your Backend
After updating the .env file:
```bash
# Stop your backend server (Ctrl+C)
# Then restart it
cd backend
python main.py
```

## Verification
Your secret VALUE should:
- ✅ Be 30-40+ characters long
- ✅ Contain alphanumeric characters and possibly special chars like `~`, `.`, `-`
- ✅ NOT look like a UUID (no pattern like `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)
- ✅ Be different from your client ID

## Quick Reference
Your current configuration:
- **Client ID**: `a2da9786-3455-435e-ba02-1df2b292b8a7` ✅ (Correct)
- **Client Secret**: `b9331284-00e5-47a6-b776-7342615eee19` ❌ (Secret ID, not Value)
- **Tenant ID**: `c6593da7-44f3-4f6e-bcf2-a6e48e2016e9` ✅ (Correct)

## Screenshot Guide
When you create the new secret, here's what to look for:

```
┌─────────────────────────────────────────────────────────────┐
│ Certificates & secrets                                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ✓ Client secret added                                      │
│                                                             │
│ Description: OrganAIzer OAuth Secret                       │
│ Secret ID: b9331284-00e5-47a6-b776-7342615eee19           │
│ ⚠️ DON'T COPY THIS ⚠️                                       │
│                                                             │
│ Value: Wxyz~1Ab2Cd3Ef4Gh5Ij6Kl7Mn8Op9Qr0St...           │
│ 👆 COPY THIS VALUE! 👆                                      │
│                                                             │
│ Expires: 1/26/2027                                         │
│                                                             │
│ ⚠️ Save this secret value now. You won't be able to       │
│    retrieve it after you leave this page.                 │
└─────────────────────────────────────────────────────────────┘
```

## After Fixing
Once you update the secret:
1. The error should disappear
2. You should be able to connect to Outlook successfully
3. Test by trying the OAuth connection again

## Need Help?
If you still have issues after following these steps, double-check:
1. You copied the **Value** field (not Secret ID)
2. You didn't accidentally copy extra spaces or line breaks
3. The secret hasn't expired
4. You restarted the backend server after updating .env
