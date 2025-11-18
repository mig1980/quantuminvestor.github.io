# Portfolio Automation Guide

## Overview

This guide explains how to set up GitHub Actions to automatically generate weekly portfolio update HTML pages using the `portfolio_automation.py` script.

---

## Prerequisites

Before setting up automation, ensure you have:

1. **API Keys** (required):
   - OpenAI API Key (for GPT-4 narrative generation)
   - Alpha Vantage API Key (for stock price data)
   - Marketstack API Key (optional, as fallback for price data)
   - Pexels API Key (optional, for hero images)
   - Pixabay API Key (optional, for hero images)

2. **Repository Structure**:
   - `scripts/portfolio_automation.py` - Main automation script
   - `master data/master.json` - Portfolio data file
   - `Prompt/` - Prompt files (A, B, C, D)
   - `Posts/` - Output directory for generated HTML

---

## Step 1: Add GitHub Secrets

GitHub Secrets store your API keys securely.

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add each secret:

| Secret Name | Description | Required |
|------------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key for GPT-4 | ✅ Yes |
| `ALPHAVANTAGE_API_KEY` | Alpha Vantage API key | ✅ Yes |
| `MARKETSTACK_API_KEY` | Marketstack API key (fallback) | Optional |
| `PEXELS_API_KEY` | Pexels API for hero images | Optional |
| `PIXABAY_API_KEY` | Pixabay API for hero images | Optional |

---

## Step 2: Create GitHub Actions Workflow

Create a workflow file to run the automation weekly.

### Create Workflow File

1. In your repository, create: `.github/workflows/weekly-portfolio.yml`

2. Add the following content:

```yaml
name: Weekly Portfolio Update

on:
  schedule:
    # Run every Friday at 5 PM UTC (adjust timezone as needed)
    - cron: '0 17 * * 5'
  workflow_dispatch:  # Allows manual triggering

jobs:
  generate-portfolio:
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout repository
      uses: actions/checkout@v4
      with:
        fetch-depth: 0  # Full history for proper git operations

    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        pip install --upgrade pip
        pip install -r scripts/requirements.txt

    - name: Run portfolio automation
      env:
        OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        ALPHAVANTAGE_API_KEY: ${{ secrets.ALPHAVANTAGE_API_KEY }}
        MARKETSTACK_API_KEY: ${{ secrets.MARKETSTACK_API_KEY }}
        PEXELS_API_KEY: ${{ secrets.PEXELS_API_KEY }}
        PIXABAY_API_KEY: ${{ secrets.PIXABAY_API_KEY }}
      run: |
        cd scripts
        python portfolio_automation.py --data-source alphavantage --model gpt-4-turbo-preview

    - name: Commit and push changes
      run: |
        git config --local user.email "github-actions[bot]@users.noreply.github.com"
        git config --local user.name "github-actions[bot]"
        git add .
        git diff --quiet && git diff --staged --quiet || (git commit -m "Auto-generate weekly portfolio update" && git push)
```

---

## Step 3: Configure Schedule

The workflow runs automatically based on the `cron` schedule:

```yaml
- cron: '0 17 * * 5'  # Every Friday at 5 PM UTC
```

### Cron Schedule Examples

| Schedule | Cron Expression | Description |
|----------|----------------|-------------|
| Every Friday 5 PM UTC | `0 17 * * 5` | End of trading week |
| Every Monday 9 AM UTC | `0 9 * * 1` | Start of trading week |
| Every Sunday midnight | `0 0 * * 0` | Weekend processing |

**Tip**: Use [crontab.guru](https://crontab.guru/) to create custom schedules.

---

## Step 4: Manual Triggering

You can manually trigger the workflow anytime:

1. Go to **Actions** tab in your repository
2. Click **Weekly Portfolio Update**
3. Click **Run workflow**
4. Select branch (usually `main`)
5. Click **Run workflow** button

---

## Step 5: Monitor Execution

### View Workflow Runs

1. Go to **Actions** tab
2. Click on the workflow run
3. View logs for each step

### Where to Find Logs

#### GitHub Actions
- **Location**: Actions tab → Workflow run → "Run portfolio automation" step
- **Format**: Real-time console output with timestamps
- **Retention**: 90 days (GitHub default)

#### Local Execution
- **Location**: Terminal/PowerShell window (stdout)
- **Format**: `YYYY-MM-DD HH:MM:SS - LEVEL - Message`
- **Example**:
  ```
  2025-11-18 14:30:15 - INFO - Running Alpha Vantage data engine...
  2025-11-18 14:30:20 - INFO - → [1/10] Fetching AAPL...
  2025-11-18 14:30:25 - INFO - Prompt B completed - narrative and SEO generated
  ```

**Note**: The script logs to console only (no log file created by default).

### Check Output

After successful run:
- New HTML file in `Posts/` folder
- Updated `master.json` with new week data
- New hero image in `Media/` folder
- Updated `posts.html` listing
- Execution report printed at end of logs

---

## Automation Script Options

The script supports various command-line options:

### Basic Usage

```bash
python portfolio_automation.py
```

### With Options

```bash
python portfolio_automation.py \
  --week auto \
  --data-source alphavantage \
  --model gpt-4-turbo-preview \
  --eval-date 2025-11-15
```

### Available Options

| Option | Description | Default |
|--------|-------------|---------|
| `--week` | Week number or `auto` | `auto` |
| `--data-source` | `ai` or `alphavantage` | `ai` |
| `--model` | OpenAI model name | `gpt-4-turbo-preview` |
| `--eval-date` | Manual date (YYYY-MM-DD) | Current date |
| `--palette` | Theme palette | `default` |

---

## Viewing Execution Reports

The script generates a detailed execution report at the end of each run:

```
================================================================================
 AUTOMATION EXECUTION REPORT - Week 6
================================================================================
Started:  2025-11-18 14:30:00
Finished: 2025-11-18 14:35:30
Duration: 330.5 seconds
Status:   ✅ SUCCESS
--------------------------------------------------------------------------------
EXECUTION STEPS:
--------------------------------------------------------------------------------
1. ✅ Load Prompts
   Status: SUCCESS
   All 4 prompt files loaded successfully

2. ✅ Load Master Data
   Status: SUCCESS
   Loaded master.json with 5 completed weeks

3. ✅ Fetch Market Prices
   Status: SUCCESS
   Fetched prices for 10 stocks + 2 benchmarks

4. ✅ Generate Hero Image
   Status: SUCCESS
   Created 1200x800 hero image

5. ✅ Prompt B - Narrative Writer
   Status: SUCCESS
   Generated narrative HTML and SEO metadata

6. ✅ Prompt C - Visual Generator
   Status: SUCCESS
   Generated performance table and chart

7. ✅ Prompt D - Final Assembler
   Status: SUCCESS
   Generated complete HTML page for Week post
================================================================================
SUMMARY: 7 succeeded, 0 warnings, 0 errors
================================================================================
```

This report shows:
- Total execution time
- Success/failure status
- Each step with detailed status
- Any warnings or errors encountered

## Troubleshooting

### Common Issues

#### 1. **API Rate Limits**

**Error**: `Rate limit exceeded`

**Solution**: 
- Alpha Vantage: Free tier = 5 requests/min
- Add delays between requests (script handles this automatically)
- Consider premium API key for higher limits

#### 2. **Missing Dependencies**

**Error**: `ModuleNotFoundError: No module named 'X'`

**Solution**:
```bash
pip install -r scripts/requirements.txt
```

#### 3. **Invalid API Key**

**Error**: `Invalid API key`

**Solution**:
- Verify secret names match exactly (case-sensitive)
- Check API key is active and valid
- Regenerate key if expired

#### 4. **Git Push Failed**

**Error**: `Permission denied (publickey)`

**Solution**:
- GitHub Actions has automatic GITHUB_TOKEN
- Ensure workflow has write permissions:
  - Go to **Settings** → **Actions** → **General**
  - Under "Workflow permissions", select **Read and write permissions**

#### 5. **Master Data Not Found**

**Error**: `Master data file not found`

**Solution**:
- Ensure `master data/master.json` exists in repository
- Check file path is correct (case-sensitive on Linux)

---

## Testing Locally

Before enabling automation, test locally:

### 1. **Set Environment Variables** (PowerShell)

```powershell
$env:OPENAI_API_KEY="your-key-here"
$env:ALPHAVANTAGE_API_KEY="your-key-here"
$env:MARKETSTACK_API_KEY="your-key-here"
```

### 2. **Run Script**

```powershell
cd scripts
python portfolio_automation.py --data-source alphavantage
```

### 3. **Verify Output**

Check generated files:
- `Posts/GenAi-Managed-Stocks-Portfolio-Week-X.html`
- `Media/WX.webp`
- `master data/master.json` (updated)

### 4. **View Logs**

Logs appear in your PowerShell terminal showing:
- Each step of execution
- API calls and responses
- File generation status
- Final execution report with summary

---

## Advanced Configuration

### Custom Data Source

Use AI-generated data instead of live API:

```yaml
run: |
  python portfolio_automation.py --data-source ai
```

### Specific Week Number

Generate specific week manually:

```yaml
run: |
  python portfolio_automation.py --week 10 --eval-date 2025-12-20
```

### Different Model

Use different OpenAI model:

```yaml
run: |
  python portfolio_automation.py --model gpt-4 --data-source alphavantage
```

---

## Security Best Practices

1. **Never commit API keys** to repository
2. **Use GitHub Secrets** for all sensitive data
3. **Rotate keys regularly** (every 90 days)
4. **Monitor API usage** for unusual activity
5. **Set spending limits** on API accounts
6. **Review workflow logs** for exposed secrets

---

## Maintenance

### Weekly Checklist

- [ ] Verify workflow ran successfully
- [ ] Check generated HTML renders correctly
- [ ] Verify data accuracy in master.json
- [ ] Review hero image generated properly
- [ ] Confirm posts.html listing updated

### Monthly Checklist

- [ ] Review API usage and costs
- [ ] Check for script errors in logs
- [ ] Update dependencies if needed
- [ ] Verify all prompts working correctly

### Quarterly Checklist

- [ ] Rotate API keys
- [ ] Update Python dependencies
- [ ] Review and optimize prompt templates
- [ ] Archive old data backups

---

## Support & Resources

### Documentation

- Script: `scripts/portfolio_automation.py`
- Prompts: `Prompt/Prompt-{A,B,C,D}-v5.4{A,B,C,D}.md`
- Requirements: `scripts/requirements.txt`

### GitHub Actions Docs

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Workflow Syntax](https://docs.github.com/en/actions/reference/workflow-syntax-for-github-actions)
- [Schedule Events](https://docs.github.com/en/actions/reference/events-that-trigger-workflows#schedule)

### API Documentation

- [OpenAI API](https://platform.openai.com/docs)
- [Alpha Vantage](https://www.alphavantage.co/documentation/)
- [Marketstack](https://marketstack.com/documentation)
- [Pexels](https://www.pexels.com/api/documentation/)
- [Pixabay](https://pixabay.com/api/docs/)

---

## Quick Reference

### Enable Automation (3 Steps)

1. **Add Secrets**: Settings → Secrets → Add API keys
2. **Create Workflow**: `.github/workflows/weekly-portfolio.yml`
3. **Enable**: Commit and push workflow file

### Manual Run

1. Go to **Actions** tab
2. Select **Weekly Portfolio Update**
3. Click **Run workflow**

### Check Status

1. **Actions** tab → View latest run
2. Check generated files in repository
3. Visit website to verify HTML

---

## Changelog

### Version 1.0 (Current)
- Initial automation setup
- Weekly schedule on Fridays
- Alpha Vantage data source
- GPT-4 narrative generation
- Hero image generation
- Automatic git commit/push
