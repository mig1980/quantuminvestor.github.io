# 🚀 Deployment Checklist

**Quick reference for deploying fixes from architecture audit**

---

## ⚡ Immediate Actions (REQUIRED)

### 1. Azure Function App Settings
Open Azure Portal → Function App → Configuration → Application Settings:

```bash
✅ STORAGE_CONNECTION_STRING     # Already set
✅ BREVO_API_KEY                 # Already set
✅ BREVO_FROM_EMAIL              # Already set
✅ BREVO_FROM_NAME               # Already set

🔧 ADD THESE:
GITHUB_OWNER=mig1980
GITHUB_REPO=quantuminvestor
GITHUB_POSTS_PATH=Posts
CORS_ALLOWED_ORIGIN=https://quantuminvestor.net
```

**Save → Restart Function App**

---

### 2. GitHub Repository Secrets
Open GitHub → Settings → Secrets → Actions:

```bash
✅ AZURE_OPENAI_API_KEY          # Already set
✅ ALPHAVANTAGE_API_KEY          # Already set
✅ FINNHUB_API_KEY               # Already set
✅ MARKETSTACK_API_KEY           # Already set

🔧 ADD THIS:
STORAGE_CONNECTION_STRING        # Same value as Azure Function
```

**Repository → Settings → Secrets and variables → Actions → New repository secret**

---

### 3. Test Changes

#### Test 1: Azure Function Configuration
```bash
# Go to Azure Portal → Function App → Overview → URL
# Click your function URL - should NOT throw config errors

Expected: Clean startup (check Application Insights logs)
```

#### Test 2: Newsletter Workflow
```bash
# Go to GitHub → Actions → Generate & Upload Newsletter (Stage 2 & 3)
# Click "Run workflow"
# Select: Week 6, Overwrite: false

Expected: ✅ Success, blob uploaded to Azure Storage
```

#### Test 3: Weekly Newsletter Send (Manual)
```bash
# Go to Azure Portal → Function App → Functions → weekly_newsletter
# Click "Code + Test" → Test/Run → Run

Expected: Newsletter downloaded from blob and sent to subscribers
```

---

## 📝 Files Changed

### Modified
- ✅ `azure-functions/MyBlogSubscribers/requirements.txt` - Pinned versions
- ✅ `azure-functions/MyBlogSubscribers/function_app.py` - CORS security
- ✅ `azure-functions/MyBlogSubscribers/weekly_job.py` - GitHub config validation
- ✅ `scripts/upload_newsletter_to_blob.py` - Azure exception handling

### Created
- ✅ `.github/workflows/generate-newsletter-full.yml` - Complete automation
- ✅ `ARCHITECTURE_AUDIT_REPORT.md` - Full audit documentation
- ✅ `DEPLOYMENT_CHECKLIST.md` - This file

---

## 🔄 Deployment Order

### Phase 1: Configuration (5 minutes)
1. Add Azure Function App Settings (4 new variables)
2. Add GitHub Secret (STORAGE_CONNECTION_STRING)
3. Restart Azure Function App

### Phase 2: Code Deploy (10 minutes)
1. Commit changes to main branch
2. Push to GitHub
3. Wait for Azure Function deployment workflow
4. Verify deployment in Azure Portal

### Phase 3: Testing (15 minutes)
1. Test Azure Function startup (check logs)
2. Test newsletter workflow (GitHub Actions)
3. Manually trigger weekly_newsletter function
4. Verify email sends to test subscriber

---

## 🐛 Troubleshooting

### Azure Function won't start
```bash
Error: "GITHUB_OWNER and GITHUB_REPO must be set"
Fix: Add missing environment variables in App Settings
```

### Newsletter workflow fails on upload
```bash
Error: "STORAGE_CONNECTION_STRING not set"
Fix: Add secret to GitHub repository secrets
```

### CORS errors on subscription form
```bash
Error: "CORS policy: No 'Access-Control-Allow-Origin'"
Fix: Verify CORS_ALLOWED_ORIGIN='https://quantuminvestor.net' in App Settings
```

### Function can't download newsletter
```bash
Error: "Newsletter file not found in Azure Blob Storage"
Fix: Run "Generate & Upload Newsletter" workflow first
```

---

## ✅ Success Criteria

All these should work:
- [ ] Azure Function starts without config errors
- [ ] Subscription form accepts new email (check CORS)
- [ ] Newsletter workflow uploads to blob storage
- [ ] Weekly newsletter function downloads and sends
- [ ] No hardcoded secrets in code
- [ ] All environment variables explicitly configured

---

## 📞 Rollback Procedure

If something breaks:

### Option 1: Revert Azure Function
```bash
Azure Portal → Function App → Deployment Center → Deployments
→ Find previous successful deployment → Redeploy
```

### Option 2: Revert GitHub Changes
```bash
git revert HEAD
git push
```

### Option 3: Emergency Config
```bash
# Temporary fix: Re-add wildcard CORS (NOT RECOMMENDED)
CORS_ALLOWED_ORIGIN=*

# Add default GitHub values
GITHUB_OWNER=mig1980
GITHUB_REPO=quantuminvestor
```

---

## 📊 Post-Deployment Verification

### Azure Monitor Queries
```kusto
// Check for startup errors
traces
| where timestamp > ago(1h)
| where severityLevel >= 3
| where message contains "FATAL" or message contains "config"
| project timestamp, message, severityLevel

// Check newsletter sends
traces
| where timestamp > ago(7d)
| where message contains "newsletter"
| summarize count() by bin(timestamp, 1d)
```

### GitHub Actions Status
```bash
# Check last 5 workflow runs
gh run list --workflow=generate-newsletter-full.yml --limit=5

# View specific run
gh run view <run-id>
```

---

## 🎯 Next Steps After Deployment

1. Monitor Azure Function logs for 24 hours
2. Test full newsletter cycle (Stages 1-3)
3. Add test subscriber for dry runs
4. Document any new issues in GitHub Issues
5. Schedule next audit in 3 months

---

**Last Updated:** November 23, 2025  
**Version:** 1.0  
**Status:** ✅ Ready for deployment
