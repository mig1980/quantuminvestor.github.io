# GitHub Actions Setup Guide

**Complete step-by-step instructions to automate weekly portfolio updates**

---

## Prerequisites

Before starting, ensure you have:
- ✅ GitHub repository with this code
- ✅ Admin access to repository settings
- ✅ GitHub Personal Access Token (or can create one)
- ✅ Alpha Vantage API key (or can get one)

---

## Step 1: Get Your API Keys

### 1.1 GitHub Personal Access Token (Required)

1. Go to https://github.com/settings/tokens
2. Click **"Generate new token"** → **"Generate new token (classic)"**
3. Fill in:
   - **Note**: `Portfolio Automation`
   - **Expiration**: Choose duration (recommend: No expiration)
   - **Scopes**: ⚠️ **Leave all unchecked** (no scopes needed for GitHub Models)
4. Scroll to bottom, click **"Generate token"**
5. **⚠️ COPY TOKEN IMMEDIATELY** - shown only once!
   - Format: `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
6. Save it somewhere safe temporarily

### 1.2 Alpha Vantage API Key (Required)

1. Go to https://www.alphavantage.co/support/#api-key
2. Fill in:
   - Email address
   - Click "GET FREE API KEY"
3. Check your email
4. Copy your API key (format: `XXXXXXXXXXXXXXXX`)

### 1.3 Finnhub API Key (Optional - Recommended)

1. Go to https://finnhub.io/register
2. Sign up with email
3. Verify email
4. Go to https://finnhub.io/dashboard
5. Copy your API key from dashboard

### 1.4 Marketstack API Key (Optional)

1. Go to https://marketstack.com/product
2. Sign up for free plan
3. Verify email
4. Go to dashboard
5. Copy your API key

---

## Step 2: Add Secrets to GitHub Repository

### 2.1 Navigate to Secrets Settings

1. Go to your GitHub repository: https://github.com/mig1980/quantuminvestor
2. Click **"Settings"** tab (top menu)
3. In left sidebar, click **"Secrets and variables"** → **"Actions"**

### 2.2 Add Required Secrets

Click **"New repository secret"** for each:

#### Secret 1: GH_MODELS_TOKEN (Required)
- **Name**: `GH_MODELS_TOKEN`
- **Secret**: Paste your GitHub token (from Step 1.1)
- Click **"Add secret"**

#### Secret 2: ALPHAVANTAGE_API_KEY (Required)
- **Name**: `ALPHAVANTAGE_API_KEY`
- **Secret**: Paste your Alpha Vantage key (from Step 1.2)
- Click **"Add secret"**

#### Secret 3: FINNHUB_API_KEY (Optional but Recommended)
- **Name**: `FINNHUB_API_KEY`
- **Secret**: Paste your Finnhub key (from Step 1.3)
- Click **"Add secret"**

#### Secret 4: MARKETSTACK_API_KEY (Optional)
- **Name**: `MARKETSTACK_API_KEY`
- **Secret**: Paste your Marketstack key (from Step 1.4)
- Click **"Add secret"**

### 2.3 Verify Secrets

You should now see these secrets listed:
- ✅ `GH_MODELS_TOKEN`
- ✅ `ALPHAVANTAGE_API_KEY`
- ✅ `FINNHUB_API_KEY` (if added)
- ✅ `MARKETSTACK_API_KEY` (if added)

---

## Step 3: Enable Workflow Permissions

### 3.1 Configure Repository Permissions

1. Still in **Settings**, scroll down left sidebar
2. Click **"Actions"** → **"General"**
3. Scroll to **"Workflow permissions"** section
4. Select: ⚪ **"Read and write permissions"**
5. Check: ☑️ **"Allow GitHub Actions to create and approve pull requests"**
6. Click **"Save"**

This allows the workflow to commit and push changes.

---

## Step 4: Verify Workflow File Exists

### 4.1 Check Workflow File

1. In your repository, navigate to: `.github/workflows/`
2. Verify file exists: `weekly-portfolio.yml`
3. If missing, the file should contain:

{% raw %}
```yaml
name: Weekly Portfolio Update

on:
  schedule:
    - cron: '45 21 * * 4'  # Every Thursday at 4:45 PM EST
  workflow_dispatch:
    inputs:
      week:
        description: 'Week number (leave empty for auto)'
        required: false
        default: 'auto'
      eval_date:
        description: 'Evaluation date (YYYY-MM-DD, leave empty for latest)'
        required: false

jobs:
  generate-portfolio:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
      
      - name: Install dependencies
        run: pip install -r scripts/requirements.txt
      
      - name: Generate portfolio update
        env:
          GH_TOKEN: ${{ secrets.GH_MODELS_TOKEN }}
          ALPHAVANTAGE_API_KEY: ${{ secrets.ALPHAVANTAGE_API_KEY }}
          FINNHUB_API_KEY: ${{ secrets.FINNHUB_API_KEY }}
          MARKETSTACK_API_KEY: ${{ secrets.MARKETSTACK_API_KEY }}
          PEXELS_API_KEY: ${{ secrets.PEXELS_API_KEY }}
          PIXABAY_API_KEY: ${{ secrets.PIXABAY_API_KEY }}
        run: |
          python scripts/portfolio_automation.py \
            --data-source alphavantage \
            --week ${{ github.event.inputs.week || 'auto' }} \
            ${{ github.event.inputs.eval_date && format('--eval-date {0}', github.event.inputs.eval_date) || '' }}
      
      - name: Commit and push changes
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add .
          if git diff --staged --quiet; then
            echo "No changes to commit"
          else
            git commit -m "📊 Weekly portfolio update - Week $(date +%V) [automated]"
            git push
          fi
      
      - name: Upload execution report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: portfolio-report-${{ github.run_number }}
          path: |
            Posts/*.html
            Media/*.webp
            master data/master.json
          retention-days: 30
```
{% endraw %}

---

## Step 5: Test Manual Run (Important!)

### 5.1 Trigger Manual Run

1. Go to repository: **"Actions"** tab
2. Left sidebar: Click **"Weekly Portfolio Update"**
3. Right side: Click **"Run workflow"** button
4. Dropdown appears:
   - **Branch**: `main` (or your default branch)
   - **Week number**: Leave empty (auto)
   - **Evaluation date**: Leave empty (auto)
5. Click green **"Run workflow"** button

### 5.2 Monitor Execution

1. Wait 5-10 seconds, refresh page
2. You'll see a new workflow run appear (yellow dot = running)
3. Click on the run to see details
4. Click on **"generate-portfolio"** job to see logs
5. Watch each step execute:
   - ✅ Checkout repository
   - ✅ Setup Python
   - ✅ Install dependencies
   - ✅ Generate portfolio update (this takes 5-10 minutes)
   - ✅ Commit and push changes
   - ✅ Upload execution report

### 5.3 Check for Errors

**If successful (green checkmark):**
- ✅ Workflow completed successfully
- ✅ Check repository for new files:
  - `Posts/GenAi-Managed-Stocks-Portfolio-Week-X.html`
  - `Media/WX.webp`
  - `master data/master.json` (updated)
- ✅ Check commit history for automated commit

**If failed (red X):**
- Click on failed step to see error
- Common issues:
  - ❌ Missing secrets → Go back to Step 2
  - ❌ Permission denied → Go back to Step 3
  - ❌ API rate limit → Wait 1 minute, try again
  - ❌ Invalid API key → Verify keys in Step 1

---

## Step 6: Verify Scheduled Run is Enabled

### 6.1 Check Schedule Status

1. Go to **"Actions"** tab
2. Left sidebar: Click **"Weekly Portfolio Update"**
3. You should see: `This workflow has a workflow_dispatch event trigger.`
4. Schedule is active: Runs every **Thursday at 4:45 PM EST (9:45 PM UTC)**

### 6.2 Wait for First Scheduled Run

- First automatic run: Next Thursday at 4:45 PM EST
- You'll receive email notification (if enabled)
- Check **"Actions"** tab to see scheduled runs

---

## Step 7: Download Execution Artifacts (Optional)

### 7.1 Access Artifacts

After each run (manual or scheduled):

1. Go to **"Actions"** tab
2. Click on completed workflow run
3. Scroll down to **"Artifacts"** section
4. Download: `portfolio-report-XXX`
5. Contains:
   - Generated HTML files
   - Hero images
   - Updated master.json

Artifacts kept for 30 days.

---

## Troubleshooting

### Issue: "AI mode requires GH_TOKEN"

**Problem**: GitHub token not found

**Solution**:
1. Verify secret name is exactly `GH_MODELS_TOKEN`
2. Re-add secret if needed (Step 2.2)
3. Trigger new manual run

### Issue: "Rate limit exceeded"

**Problem**: Too many API calls to Alpha Vantage

**Solution**:
- Alpha Vantage free tier: 5 calls/min, 500/day
- Wait 12 seconds between retries
- Add Finnhub API key for fallback (Step 1.3)

### Issue: "Permission denied" on git push

**Problem**: Workflow doesn't have write access

**Solution**:
1. Go to Step 3: Enable Workflow Permissions
2. Ensure "Read and write permissions" selected
3. Save changes
4. Trigger new manual run

### Issue: "Could not extract narrative HTML"

**Problem**: AI response format unexpected

**Solution**:
- Check GitHub Models status: https://www.githubstatus.com/
- Try alternative model: Edit workflow, add `--model openai/gpt-4o`
- Verify GitHub token is valid

### Issue: Workflow doesn't appear in Actions tab

**Problem**: Workflow file syntax error

**Solution**:
1. Check `.github/workflows/weekly-portfolio.yml` exists
2. Verify YAML syntax (no tabs, proper indentation)
3. Commit and push changes
4. Refresh Actions tab

---

## Monitoring & Maintenance

### Weekly Checks

After each automated run:
1. ✅ Check **"Actions"** tab for green checkmark
2. ✅ Verify new HTML file in `Posts/`
3. ✅ Check hero image in `Media/`
4. ✅ Review commit message

### Monthly Maintenance

1. Review API usage:
   - Alpha Vantage: https://www.alphavantage.co/
   - Finnhub: https://finnhub.io/dashboard
2. Check for dependency updates
3. Verify secrets haven't expired

### Quarterly Tasks

1. Rotate GitHub token (Step 1.1)
2. Update secrets (Step 2.2)
3. Review workflow logs for warnings

---

## Advanced Configuration

### Change Schedule

Edit `.github/workflows/weekly-portfolio.yml`:

```yaml
on:
  schedule:
    - cron: '45 21 * * 4'  # Modify this line
```

Examples:
- Every Friday 5 PM UTC: `0 17 * * 5`
- Every Monday 9 AM UTC: `0 9 * * 1`
- First of month: `0 0 1 * *`

Use https://crontab.guru/ to create custom schedules.

### Add Email Notifications

1. Go to GitHub profile → **Settings** → **Notifications**
2. Check: ☑️ **"Actions"** under "Email notification preferences"
3. You'll receive emails on workflow failures

### Manual Run with Custom Week

1. Go to **"Actions"** tab
2. Click **"Weekly Portfolio Update"**
3. Click **"Run workflow"**
4. Set inputs:
   - **Week number**: `10`
   - **Evaluation date**: `2025-12-20`
5. Click **"Run workflow"**

---

## Success Checklist

After completing all steps:

- ✅ All secrets added to repository
- ✅ Workflow permissions enabled (read and write)
- ✅ Manual test run completed successfully
- ✅ New HTML file generated in `Posts/`
- ✅ Hero image created in `Media/`
- ✅ `master.json` updated with new week
- ✅ Automated commit visible in history
- ✅ Schedule enabled for Thursday 4:45 PM EST

**🎉 Automation is now live!**

Next automated run: **Thursday at 4:45 PM EST**

---

## Quick Reference

### Repository URLs
- Settings: `https://github.com/mig1980/quantuminvestor/settings`
- Secrets: `https://github.com/mig1980/quantuminvestor/settings/secrets/actions`
- Actions: `https://github.com/mig1980/quantuminvestor/actions`

### Required Secrets
1. `GH_MODELS_TOKEN` - GitHub Personal Access Token
2. `ALPHAVANTAGE_API_KEY` - Alpha Vantage API key

### Optional Secrets
3. `FINNHUB_API_KEY` - Finnhub fallback
4. `MARKETSTACK_API_KEY` - Marketstack fallback
5. `PEXELS_API_KEY` - Hero images
6. `PIXABAY_API_KEY` - Hero images

### Schedule
- **When**: Every Thursday
- **Time**: 4:45 PM Eastern (9:45 PM UTC)
- **Duration**: ~5-10 minutes
- **Auto-commit**: Yes

---

## Support

If you encounter issues:

1. Check workflow logs in Actions tab
2. Review error messages carefully
3. Verify all secrets are correctly named
4. Test locally first: `python scripts/portfolio_automation.py --data-source alphavantage`
5. Check API status pages for outages

**Documentation:**
- Main guide: `README/Automation_readme.md`
- Quick start: `QUICK_START.md`
- This guide: `GITHUB_ACTIONS_SETUP.md`
