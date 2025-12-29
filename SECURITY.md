# Security Guide for Organizer Service

## 🔒 Security Best Practices

This guide outlines the security measures implemented in the Organizer Service and how to use them safely.

## 🚨 CRITICAL: Never Commit Secrets

### What NOT to commit:
- `.env` files with real API keys
- `backend/credentials.json` (Google OAuth)
- `backend/token.json` (Google OAuth tokens)
- `backend/keys.csv` (API keys)
- Any files containing API keys, tokens, or secrets
- SSL certificates and private keys

### What TO commit:
- `.env.example` (template with placeholders)
- `SECURITY.md` (this file)
- `.gitignore` (to prevent accidental commits)

## 🛡️ Current Security Measures

### 1. Environment Variables
All secrets are loaded from `.env` files using `python-dotenv`.

```python
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv('GOOGLE_API_KEY')
```

### 2. CORS Configuration
CORS is restricted to specific domains:
- Production: `https://organaizer.com2u.selfhost.eu`, `https://organaizer_backend.com2u.selfhost.eu`
- Development: `localhost`, `192.168.0.95`, `100.117.42.75`

### 3. API Key Authentication
Required header: `X-API-Key`
Keys are stored in `backend/keys.csv` (should be moved to environment variables)

### 4. Docker Security
- Containers run with minimal privileges
- Health checks for monitoring
- Separate networks for services

## 🔐 Setting Up Securely

### Step 1: Create .env File
```bash
cp .env.example .env
```

### Step 2: Add Your Real API Keys
Edit `.env` and replace placeholders with real values:
```bash
GOOGLE_API_KEY=your_actual_key_here
OPENROUTER_API_KEY=your_actual_key_here
# etc.
```

### Step 3: Secure Your API Keys
```bash
# Set proper permissions
chmod 600 .env

# Add to .gitignore (already done)
echo ".env" >> .gitignore
```

### Step 4: Remove Existing Secrets from Git
If you accidentally committed secrets:
```bash
# Remove from git history (use with caution)
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch backend/credentials.json backend/token.json backend/keys.csv .env' \
  --prune-empty --tag-name-filter cat -- --all

# Add to .gitignore to prevent future commits
echo ".env" >> .gitignore
echo "backend/credentials.json" >> .gitignore
echo "backend/token.json" >> .gitignore
echo "backend/keys.csv" >> .gitignore

# Commit the .gitignore changes
git add .gitignore
git commit -m "Update .gitignore to exclude secrets"
```

## 🔄 API Key Rotation

### When to Rotate Keys:
- Employee departure
- Suspected compromise
- Regular schedule (every 90 days)
- After accidental exposure

### How to Rotate:

#### Google API Key:
1. Go to Google Cloud Console
2. Navigate to APIs & Services > Credentials
3. Create new API key
4. Update `.env` file
5. Test functionality
6. Delete old key

#### Azure Credentials:
1. Go to Azure Portal
2. Navigate to Azure Active Directory > App registrations
3. Create new client secret
4. Update `.env` file
5. Test functionality
6. Revoke old secret

#### OpenRouter API Key:
1. Log into OpenRouter
2. Generate new API key
3. Update `.env` file
4. Test functionality
5. Revoke old key

## 🚨 Incident Response

### If You Expose a Secret:

1. **Immediately rotate the key**
2. **Check access logs** for unauthorized use
3. **Notify relevant parties**
4. **Update all environments**
5. **Document the incident**

### If You Commit Secrets by Mistake:

1. **Don't panic** - but act quickly
2. **Rotate all exposed keys immediately**
3. **Use BFG Repo-Cleaner** or `git filter-branch`
4. **Force push to remote** (if necessary)
5. **Notify team members**
6. **Update webhooks/CI/CD** with new keys

## 🔍 Security Checklist

### Before Deployment:
- [ ] All secrets in `.env` (not committed)
- [ ] `.env.example` created with placeholders
- [ ] `.gitignore` includes all secret patterns
- [ ] CORS configured for production domains only
- [ ] API keys rotated and tested
- [ ] SSL certificates configured
- [ ] Firewall rules set up
- [ ] Logging enabled for security events
- [ ] Health checks configured
- [ ] Container security settings applied

### Regular Maintenance:
- [ ] Review access logs weekly
- [ ] Rotate keys every 90 days
- [ ] Update dependencies monthly
- [ ] Check for leaked secrets in git history
- [ ] Review CORS origins periodically
- [ ] Monitor for suspicious activity

## 🛡️ Production Security

### Environment Hardening:
```bash
# Set strict file permissions
chmod 600 .env
chmod 600 backend/credentials.json
chmod 600 backend/token.json
chmod 600 backend/keys.csv

# Use secrets manager in production
# Example: AWS Secrets Manager, HashiCorp Vault
```

### Network Security:
```bash
# Configure firewall
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp
sudo ufw enable

# Use VPN for admin access
# Restrict SSH to key-based auth only
```

### Docker Security:
```bash
# Run containers with non-root user
# Use read-only filesystems where possible
# Limit container resources
# Enable security options
```

## 📊 Monitoring & Logging

### What to Monitor:
- Failed authentication attempts
- Unusual API usage patterns
- Geographic anomalies
- Rate limit violations
- File upload sizes/types

### Log Configuration:
```python
# In backend/main.py
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
```

## 🔐 Advanced Security Features

### 1. Rate Limiting
```python
# Add to FastAPI
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
```

### 2. Input Validation
```python
from pydantic import BaseModel, validator

class RequestModel(BaseModel):
    api_key: str
    
    @validator('api_key')
    def validate_api_key(cls, v):
        if len(v) < 32:
            raise ValueError('API key too short')
        return v
```

### 3. Secure Headers
```python
# Add security headers
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response
```

## 🚨 Emergency Contacts

- **Security Team**: [Your security contact]
- **API Providers**: 
  - Google: https://support.google.com/cloud
  - Azure: https://azure.microsoft.com/support
  - OpenRouter: https://openrouter.ai/support

## 📝 Security Log Template

```markdown
## Security Incident Report

**Date**: [Date]
**Severity**: [Low/Medium/High/Critical]
**Affected Systems**: [Systems]
**Description**: [What happened]
**Impact**: [Potential damage]
**Response**: [Actions taken]
**Lessons Learned**: [Prevention measures]
**Follow-up**: [Next steps]
```

## 🔄 Regular Security Tasks

### Daily:
- Monitor logs for suspicious activity
- Check for failed authentication attempts

### Weekly:
- Review access patterns
- Check for new vulnerabilities in dependencies

### Monthly:
- Rotate API keys
- Update dependencies
- Review CORS origins
- Audit user access

### Quarterly:
- Full security audit
- Penetration testing
- Incident response drill
- Update security documentation

## 📚 Additional Resources

- [OWASP Security Guidelines](https://owasp.org)
- [Docker Security Best Practices](https://docs.docker.com/engine/security/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [CORS Security](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)

---

**Remember**: Security is an ongoing process, not a one-time setup. Stay vigilant and keep your secrets safe!