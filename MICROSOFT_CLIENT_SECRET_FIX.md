# Microsoft Client Secret Fix Guide

## Problem
You're currently using the **Client Secret ID** instead of the **Client Secret Value** in your `.env` file.

**Current (WRONG):** `2ff77288-ef44-4e5f-9955-aede489e05e7` ← This is the Secret ID (GUID format)

**You need:** The actual Secret Value (a longer random string shown only once)

## Solution

### Option 1: Retrieve the Existing Secret Value (If You Saved It)
If you saved the secret value when you first created it, simply update your `.env` file with that value.

### Option 2: Create a NEW Client Secret (Recommended)
Since the secret value is only shown once when created, you'll likely need to create a new one:

#### Steps to Create a New Client Secret:

1. **Go to Azure Portal**
   - Visit: https://portal.azure.com
   - Navigate to: **Azure Active Directory** > **App registrations**

2. **Find Your App**
   - Search for your app with Client ID: `a2da9786-3455-435e-ba02-1df2b292b8a7`
   - Click on it to open

3. **Go to Certificates & secrets**
   - In the left sidebar, click **Certificates & secrets**

4. **Create New Client Secret**
   - Click **+ New client secret**
   - Add a description (e.g., "OrganAIzer OAuth Secret")
   - Choose expiration period (e.g., 24 months)
   - Click **Add**

5. **COPY THE SECRET VALUE IMMEDIATELY**
   - ⚠️ **CRITICAL:** The **Value** column shows the actual secret (this is what you need!)
   - Copy this value RIGHT NOW - it will never be shown again!
   - The **Secret ID** column shows the GUID (which is what you currently have - DON'T use this)

6. **Update Your .env File**
   ```env
   MICROSOFT_CLIENT_SECRET=<paste the Value here, not the Secret ID>
   ```

   The value should look like: `abc123XYZ~longRandomString-_here`
   NOT like: `2ff77288-ef44-4e5f-9955-aede489e05e7` (this is a Secret ID)

7. **Restart Your Backend**
   ```bash
   # Stop the backend if running (Ctrl+C)
   # Then restart it
   cd backend
   python main.py
   ```

## Visual Guide

When you create the secret, you'll see a table like this:

| Description | Secret ID | Value | Expires |
|------------|-----------|-------|---------|
| OrganAIzer OAuth Secret | 2ff77288-ef44-4e5f-9955-aede489e05e7 | `abc123XYZ~longRandomString-_here` | 1/26/2028 |

- ❌ **DON'T USE:** The "Secret ID" column (GUID format)
- ✅ **USE THIS:** The "Value" column (long random string)

## After Fixing

Once you update the `.env` file with the correct secret value:

1. Restart your backend server
2. Try the Microsoft OAuth flow again
3. The error should be resolved

## Additional Notes

- If you had previously created secrets, you can delete the old ones to keep things clean
- The secret value typically contains:
  - Letters (uppercase and lowercase)
  - Numbers
  - Special characters like `~`, `-`, `_`, `.`
- It's usually 40+ characters long
- Store it securely - you won't be able to see it again after initial creation!

## Quick Check

**Your current secret:** `2ff77288-ef44-4e5f-9955-aede489e05e7`
- ✅ Correct format for: Secret ID
- ❌ Correct format for: Secret Value

You need a value that looks more like: `dQw4JL9~someRandom.Characters-Here_123456XYZ`
