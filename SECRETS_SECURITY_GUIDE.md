# AuraLink Secrets Security Guide

## 🔒 Current Status

### ✅ Verified Security Measures
- `.env` files are properly excluded in `.gitignore`
- Secrets directory (`secrets/`) is ignored
- Key files (`*.key`, `*.pem`, `*.crt`) are excluded from version control

### ⚠️ IMMEDIATE ACTION REQUIRED

If you have committed production credentials to version control:

1. **Rotate ALL credentials immediately**:
   - Supabase Service Role Key
   - Supabase JWT Secret
   - Supabase Anon Key
   - Database passwords
   - Redis passwords
   - API keys (OpenAI, ElevenLabs, etc.)
   - LiveKit API credentials
   - Stripe API keys

2. **Audit git history**:
   ```bash
   # Check if .env was ever committed
   git log --all --full-history -- .env
   
   # Search for potential secrets in history
   git log --all --source --full-history -S "SUPABASE_SERVICE_ROLE_KEY"
   ```

3. **If secrets were exposed**:
   ```bash
   # Use BFG Repo-Cleaner to remove from history
   # https://rtyley.github.io/bfg-repo-cleaner/
   
   # Or use git filter-branch (more complex)
   git filter-branch --force --index-filter \
     'git rm --cached --ignore-unmatch .env' \
     --prune-empty --tag-name-filter cat -- --all
   ```

## 🔐 Production Secrets Management

### Recommended Approach: Kubernetes Secrets

For production deployment, use Kubernetes Secrets with encryption at rest:

```bash
# Create secrets in Kubernetes
kubectl create secret generic auralink-db-secrets \
  --from-literal=database-url='postgresql://...' \
  --from-literal=redis-password='...' \
  -n auralink

kubectl create secret generic auralink-api-keys \
  --from-literal=openai-api-key='...' \
  --from-literal=elevenlabs-api-key='...' \
  --from-literal=supabase-service-role-key='...' \
  --from-literal=supabase-jwt-secret='...' \
  -n auralink

kubectl create secret generic auralink-livekit \
  --from-literal=api-key='...' \
  --from-literal=api-secret='...' \
  -n auralink
```

### Alternative: AWS Secrets Manager

```python
# Example: Load secrets in AI Core startup
import boto3
import json

def load_secrets():
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name='us-east-1'
    )
    
    secret_value = client.get_secret_value(SecretId='auralink/production')
    return json.loads(secret_value['SecretString'])
```

### Alternative: HashiCorp Vault

```bash
# Store secrets
vault kv put secret/auralink/production \
  database_url='postgresql://...' \
  openai_api_key='sk-...'

# Read in application
vault kv get -field=openai_api_key secret/auralink/production
```

## 📋 Secret Rotation Procedure

### 1. Database Credentials

```bash
# Generate new password
NEW_PASSWORD=$(openssl rand -base64 32)

# Update in Supabase dashboard or run SQL:
ALTER USER auralink WITH PASSWORD 'new_password';

# Update in Kubernetes secret
kubectl create secret generic auralink-db-secrets \
  --from-literal=database-url="postgresql://user:${NEW_PASSWORD}@host/db" \
  --dry-run=client -o yaml | kubectl apply -f -

# Rolling restart services
kubectl rollout restart deployment/ai-core -n auralink
kubectl rollout restart deployment/dashboard-service -n auralink
```

### 2. Supabase Keys

1. Go to Supabase Dashboard → Settings → API
2. Click "Generate new service role key"
3. Copy new key
4. Update Kubernetes secret:
   ```bash
   kubectl create secret generic auralink-api-keys \
     --from-literal=supabase-service-role-key='NEW_KEY' \
     --dry-run=client -o yaml | kubectl apply -f -
   ```
5. Restart pods with rolling update

### 3. API Keys (OpenAI, ElevenLabs, etc.)

1. Generate new key in provider dashboard
2. Update secret in Kubernetes/AWS Secrets Manager
3. Test with new key in staging
4. Rolling update production
5. Revoke old key after confirming new key works

## 🔍 Secret Scanning

### Install Pre-commit Hooks

```bash
# Install gitleaks
brew install gitleaks

# Create .pre-commit-config.yaml
cat > .pre-commit-config.yaml << 'EOF'
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.0
    hooks:
      - id: gitleaks
EOF

# Install pre-commit
pip install pre-commit
pre-commit install
```

### Run Manual Scan

```bash
# Scan entire repository
gitleaks detect --source . --verbose

# Scan specific file
gitleaks detect --source .env.example --verbose
```

### GitHub Actions Secret Scanning

Create `.github/workflows/secret-scan.yml`:

```yaml
name: Secret Scanning
on: [push, pull_request]

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          fetch-depth: 0
      
      - name: Run Gitleaks
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## 🎯 Environment-Specific Configuration

### Development (.env.development)

```bash
# Use non-production credentials
DATABASE_URL=postgresql://dev:dev@localhost:5432/auralink_dev
OPENAI_API_KEY=sk-test-...
SUPABASE_URL=http://localhost:54321
ENABLE_DEBUG=true
```

### Staging (.env.staging)

```bash
# Use dedicated staging credentials
DATABASE_URL=postgresql://staging:...@staging-db/auralink_staging
OPENAI_API_KEY=sk-staging-...
ENABLE_DEBUG=false
ENABLE_MONITORING=true
```

### Production (Kubernetes Secrets)

**Never use .env files in production.** Always use:
- Kubernetes Secrets
- AWS Secrets Manager
- HashiCorp Vault
- Cloud provider secret services

## ✅ Security Checklist

- [ ] Verified `.env` is in `.gitignore`
- [ ] Audited git history for exposed secrets
- [ ] Rotated all production credentials
- [ ] Implemented Kubernetes Secrets or equivalent
- [ ] Enabled secret encryption at rest
- [ ] Set up secret rotation schedule (every 90 days)
- [ ] Configured secret scanning in CI/CD
- [ ] Documented emergency rotation procedure
- [ ] Tested disaster recovery with rotated secrets
- [ ] Set up alerts for secret access/changes
- [ ] Implemented least-privilege access to secrets
- [ ] Created separate secrets per environment
- [ ] Disabled root/admin access with secrets
- [ ] Enabled audit logging for secret access

## 🚨 Emergency Response

If a secret is compromised:

1. **Immediately rotate** the compromised credential
2. **Audit access logs** to determine scope of exposure
3. **Notify security team** and affected stakeholders
4. **Update incident response log**
5. **Review and update** security procedures
6. **Conduct post-mortem** within 48 hours

## 📞 Contacts

- Security Team: security@auralink.io
- On-Call Engineer: Use PagerDuty escalation
- Compliance Officer: compliance@auralink.io

---

**Last Updated**: 2025-10-16  
**Next Review**: 2026-01-16  
**Owner**: Security & DevOps Team
