# Portfolio Automation Guide

**Automated weekly portfolio HTML generation using GitHub Models (GPT-5) and Alpha Vantage**

---

## Quick Start

### Local Setup (3 Steps)

1. **Set environment variables**:
   ```powershell
   $env:GH_TOKEN = "ghp_your-github-token"
   $env:ALPHAVANTAGE_API_KEY = "your-alphavantage-key"
   ```

2. **Install dependencies**:
   ```powershell
   pip install -r scripts/requirements.txt
   ```

3. **Run automation**:
   ```powershell
   python scripts/portfolio_automation.py --data-source alphavantage
   ```

### GitHub Actions Setup (2 Steps)

1. **Add secrets** (Settings → Secrets → Actions):
   - `GH_MODELS_TOKEN` - GitHub Personal Access Token
   - `ALPHAVANTAGE_API_KEY` - Alpha Vantage API key
   - `FINNHUB_API_KEY` - (Optional) Finnhub fallback
   - `MARKETSTACK_API_KEY` - (Optional) Marketstack fallback

2. **Create workflow** (`.github/workflows/weekly-portfolio.yml`):
   {% raw %}
   ```yaml
   name: Weekly Portfolio Update

   on:
     schedule:
       - cron: '0 17 * * 5'  # Every Friday 5 PM UTC
     workflow_dispatch:

   jobs:
     generate:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         
         - uses: actions/setup-python@v5
           with:
             python-version: '3.11'
         
         - name: Install dependencies
           run: pip install -r scripts/requirements.txt
         
         - name: Generate portfolio update
           env:
             GH_TOKEN: ${{ secrets.GH_MODELS_TOKEN }}
             ALPHAVANTAGE_API_KEY: ${{ secrets.ALPHAVANTAGE_API_KEY }}
             FINNHUB_API_KEY: ${{ secrets.FINNHUB_API_KEY }}
             MARKETSTACK_API_KEY: ${{ secrets.MARKETSTACK_API_KEY }}
           run: python scripts/portfolio_automation.py --data-source alphavantage
         
         - name: Commit changes
           run: |
             git config user.name "github-actions[bot]"
             git config user.email "actions@github.com"
             git add .
             git diff --quiet || (git commit -m "Weekly update" && git push)
   ```
   {% endraw %}

---

## What It Does

The automation script generates a complete weekly portfolio update:

1. **Fetches market data** from Alpha Vantage (stocks + benchmarks)
2. **Generates AI narrative** using GitHub Models (GPT-5)
3. **Creates visualizations** (performance table + chart)
4. **Builds complete HTML page** with SEO metadata
5. **Generates hero image** (1200x800 webp)
6. **Updates master.json** with new week's data
7. **Regenerates posts listing** (posts.html)

### Output Files

```
Posts/GenAi-Managed-Stocks-Portfolio-Week-6.html  # Complete weekly post
Media/W6.webp                                      # Hero image
master data/master.json                            # Updated portfolio data
master data/archive/master-20251115.json           # Timestamped backup
Data/W6/master.json                                # Legacy snapshot
Posts/posts.html                                   # Updated listing
```

---

## API Requirements

### Required

| API | Purpose | Cost | Get Key |
|-----|---------|------|---------|
| **GitHub Models** | AI narrative (GPT-5) | Free | [GitHub Settings](https://github.com/settings/tokens) |
| **Alpha Vantage** | Stock prices | Free tier: 5/min | [alphavantage.co](https://www.alphavantage.co/support/#api-key) |

### Optional (Fallbacks)

| API | Purpose | Notes |
|-----|---------|-------|
| Finnhub | Price fallback | 5 calls/min free |
| Marketstack | Price fallback | 100 calls/month free |
| Pexels | Hero images | Optional, has gradient fallback |
| Pixabay | Hero images | Optional, has gradient fallback |

### Getting GitHub Token

1. Go to [GitHub Settings → Developer settings → Personal access tokens](https://github.com/settings/tokens)
2. Click **Generate new token (classic)**
3. Name: "Portfolio Automation"
4. **No scopes needed** (GitHub Models doesn't require any)
5. Click **Generate token**
6. Copy token immediately (shown only once)

---

## Command Line Options

### Basic Usage
```bash
python portfolio_automation.py
```

### All Options
```bash
python portfolio_automation.py \
  --week auto \                      # Week number or 'auto'
  --data-source alphavantage \       # 'alphavantage' or 'ai'
  --model openai/gpt-5 \             # GitHub Models model name
  --eval-date 2025-11-15 \           # Manual date override (YYYY-MM-DD)
  --palette default \                # 'default' or 'alt'
  --github-token "ghp_..." \         # Override GH_TOKEN env var
  --alphavantage-key "..." \         # Override ALPHAVANTAGE_API_KEY
  --finnhub-key "..." \              # Override FINNHUB_API_KEY
  --marketstack-key "..."            # Override MARKETSTACK_API_KEY
```

### Common Scenarios

**Generate specific week**:
```bash
python portfolio_automation.py --week 10 --eval-date 2025-12-20
```

**Data-only mode** (no AI, manual HTML creation):
```bash
python portfolio_automation.py --data-source alphavantage
# Then manually create HTML from generated data
```

**Use alternative model**:
```bash
python portfolio_automation.py --model openai/gpt-4o
```

---

## Price Data Fallback Chain

The script uses a robust multi-provider fallback system:

```
Alpha Vantage → Finnhub → Marketstack
    (primary)    (backup)   (last resort)
```

### How It Works

1. **Attempts Alpha Vantage first** (12-second intervals)
2. **Falls back to Finnhub** if Alpha Vantage fails (12-second intervals)
3. **Falls back to Marketstack** if Finnhub fails (2-second intervals)
4. **Fails fast** if all providers fail for a symbol

### Rate Limits

| Provider | Free Tier | Script Handling |
|----------|-----------|-----------------|
| Alpha Vantage | 5 calls/min | 12 sec between calls |
| Finnhub | 5 calls/min | 12 sec between calls |
| Marketstack | 100 calls/month | 2 sec between calls |

### Log Indicators

```
→ [1/10] Fetching AAPL...                    # Starting fetch
✓ Alpha Vantage: $150.25 (2025-11-15)        # Success
→ Trying Finnhub for TSLA...                 # Fallback attempt
✗ All sources failed for NVDA                # Complete failure
```

---

## Execution Report

The script generates a detailed report at the end of each run:

```
============================================================
 AUTOMATION EXECUTION REPORT - Week 6
============================================================
Started:  2025-11-18 14:30:00
Finished: 2025-11-18 14:35:30
Duration: 5.5 minutes
Status:   ✅ SUCCESS
------------------------------------------------------------
STEPS:
------------------------------------------------------------
1. ✅ Load Prompts
   All 4 prompt files loaded

2. ✅ Load Master Data
   Previous week: 5 | New week: 6

3. ✅ Fetch Market Prices
   10 stocks + 2 benchmarks fetched
   Sources: Alpha Vantage (9), Finnhub (3)

4. ✅ Generate Hero Image
   1200x800 webp created (Pexels)

5. ✅ Prompt B - Narrative Writer
   Generated 8,432 chars narrative + SEO

6. ✅ Prompt C - Visual Generator
   Table: ✓ | Chart: ✓

7. ✅ Prompt D - Final Assembler
   Complete HTML: 45,678 bytes

8. ✅ Update Index Pages
   posts.html regenerated
------------------------------------------------------------
SUMMARY: 8 succeeded, 0 warnings, 0 errors
============================================================
```

---

## GitHub Actions Configuration

### Workflow Permissions

Enable write access for automatic commits:

1. **Settings** → **Actions** → **General**
2. Scroll to **Workflow permissions**
3. Select **Read and write permissions**
4. Click **Save**

### Schedule Options

Common cron schedules:

| Schedule | Cron Expression | Use Case |
|----------|----------------|----------|
| Every Friday 5 PM UTC | `0 17 * * 5` | End of trading week |
| Every Monday 9 AM UTC | `0 9 * * 1` | Start of trading week |
| Every Sunday midnight | `0 0 * * 0` | Weekend processing |
| First of month | `0 0 1 * *` | Monthly reports |

Use [crontab.guru](https://crontab.guru/) to create custom schedules.

### Manual Triggering

1. Go to **Actions** tab
2. Select **Weekly Portfolio Update**
3. Click **Run workflow**
4. Choose branch (usually `main`)
5. Click **Run workflow** button

---

## Troubleshooting

### Common Issues

#### "AI mode requires GH_TOKEN"

**Problem**: GitHub token not set or invalid

**Solution**:
```powershell
# Check if set
echo $env:GH_TOKEN

# Set token
$env:GH_TOKEN = "ghp_your-token-here"

# Verify it works
python -c "import os; print('Token found' if os.getenv('GH_TOKEN') else 'Token missing')"
```

#### "Rate limit exceeded"

**Problem**: Too many API calls to Alpha Vantage

**Solution**:
- Free tier: 5 calls/min, 500/day
- Script automatically enforces 12-second delays
- Consider upgrading to premium tier for higher limits
- Add Finnhub/Marketstack keys for fallback

#### "Could not extract narrative HTML"

**Problem**: AI response format unexpected

**Solution**:
- Check GitHub Models status: [status.github.com](https://www.githubstatus.com/)
- Try alternative model: `--model openai/gpt-4o`
- Check token has proper access (no scopes needed)
- Review AI response in logs for format issues

#### "Master data file not found"

**Problem**: Missing or incorrect path to master.json

**Solution**:
```powershell
# Check file exists
Test-Path "master data/master.json"

# Verify structure
Get-Content "master data/master.json" | ConvertFrom-Json | Select-Object -Property meta
```

#### Workflow fails to push changes

**Problem**: Insufficient permissions

**Solution**:
1. Enable workflow write permissions (see above)
2. Check repository isn't archived or locked
3. Verify GitHub Actions is enabled: **Settings** → **Actions** → **General**

---

## Testing Locally

### Minimal Test (Data Only)
```powershell
# Set only required keys
$env:ALPHAVANTAGE_API_KEY = "your-key"

# Run data generation only
python scripts/portfolio_automation.py --data-source alphavantage
```

### Full Test (With AI)
```powershell
# Set all keys
$env:GH_TOKEN = "ghp_your-token"
$env:ALPHAVANTAGE_API_KEY = "your-key"

# Run full pipeline
python scripts/portfolio_automation.py --data-source alphavantage
```

### Validation Checklist

After running locally:

- [ ] `master data/master.json` updated with new week
- [ ] `Posts/GenAi-Managed-Stocks-Portfolio-Week-X.html` created
- [ ] `Media/WX.webp` hero image generated
- [ ] `Posts/posts.html` listing updated
- [ ] No errors in execution report
- [ ] HTML renders correctly in browser

---

## Architecture

### Pipeline Flow

```
1. Load master.json (previous week)
         ↓
2. Fetch prices (Alpha Vantage → Finnhub → Marketstack)
         ↓
3. Update master.json (new week appended)
         ↓
4. Generate hero image (Pexels/Pixabay or gradient fallback)
         ↓
5. AI Prompt B → Narrative HTML + SEO metadata
         ↓
6. AI Prompt C → Performance table + chart SVG
         ↓
7. AI Prompt D → Complete HTML page assembly
         ↓
8. Save outputs + regenerate posts.html
         ↓
9. Print execution report
```

### Data Files

**Primary (Single Source of Truth)**:
- `master data/master.json` - Consolidated portfolio data

**Backups**:
- `master data/archive/master-YYYYMMDD.json` - Timestamped backups

**Legacy (Backward Compatibility)**:
- `Data/WX/master.json` - Weekly snapshots

### Error Handling

The script uses **fail-fast** behavior:

- ❌ **Data fetch fails** → Abort (don't create incomplete output)
- ❌ **AI generation fails** → Abort (don't save partial HTML)
- ✅ **All steps succeed** → Save all outputs atomically

This ensures you never have partially generated content.

---

## Security Best Practices

### API Keys

1. ✅ **Never commit keys** to repository
2. ✅ **Use environment variables** or GitHub Secrets
3. ✅ **Rotate tokens quarterly** (every 90 days)
4. ✅ **Set spending limits** on paid APIs
5. ✅ **Monitor usage** for unusual activity

### GitHub Token

- **No scopes required** for GitHub Models
- **Expires never** (but rotate quarterly)
- **Revoke immediately** if compromised
- **Don't share** or expose in logs

### Repository Settings

- Enable **branch protection** on main branch
- Require **status checks** before merging
- Enable **Dependabot** security updates
- Review **workflow logs** periodically

---

## Maintenance

### Weekly
- [ ] Verify automation ran successfully
- [ ] Check HTML renders correctly
- [ ] Review execution report for warnings

### Monthly
- [ ] Review API usage and costs
- [ ] Check for dependency updates
- [ ] Validate data accuracy

### Quarterly
- [ ] Rotate API keys and tokens
- [ ] Update Python dependencies: `pip install --upgrade -r requirements.txt`
- [ ] Review and optimize prompts
- [ ] Archive old backups

---

## Advanced Usage

### Custom Prompts

Modify prompt files in `Prompt/` directory:
- `Prompt-A-v5.4A.md` - Data generation (legacy, not used with `--data-source alphavantage`)
- `Prompt-B-v5.4B.md` - Narrative writer
- `Prompt-C-v5.4C.md` - Visual generator
- `Prompt-D-v5.4D.md` - Final assembler

After modifying, test locally before pushing.

### Multiple Models

GitHub Models supports various models:
- `openai/gpt-5` (default, most capable)
- `openai/gpt-4o` (faster, cheaper)
- `openai/gpt-4-turbo` (good balance)

Test model performance:
```bash
python scripts/portfolio_automation.py --model openai/gpt-4o --week 5
```

### Custom Palette

Use alternative color theme:
```bash
python scripts/portfolio_automation.py --palette alt
```

This sets `data-theme="alt"` attribute, enabling CSS variables for alternate styling.

---

## Resources

### Documentation
- **Script**: `scripts/portfolio_automation.py`
- **Prompts**: `Prompt/Prompt-{B,C,D}-v5.4{B,C,D}.md`
- **Dependencies**: `scripts/requirements.txt`
- **Quick Start**: `QUICK_START.md`

### External APIs
- [GitHub Models](https://github.com/marketplace/models) - AI models
- [Alpha Vantage](https://www.alphavantage.co/documentation/) - Stock data
- [Finnhub](https://finnhub.io/docs/api) - Market data
- [Marketstack](https://marketstack.com/documentation) - Stock API

### GitHub Resources
- [Actions Documentation](https://docs.github.com/en/actions)
- [Workflow Syntax](https://docs.github.com/en/actions/reference/workflow-syntax-for-github-actions)
- [Personal Access Tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token)

---

## FAQ

**Q: Why use GitHub Models instead of OpenAI directly?**  
A: GitHub Models provides free access to GPT-5 for authenticated users, no credit card required.

**Q: Can I run this without AI?**  
A: Yes, use `--data-source alphavantage` to generate data files, then create HTML manually.

**Q: How much does this cost?**  
A: Free tier: $0/month (GitHub Models free, Alpha Vantage 500 calls/day free). Optional: Alpha Vantage premium for higher limits.

**Q: Can I customize the HTML output?**  
A: Yes, modify prompt files in `Prompt/` directory. Prompts B, C, D control narrative, visuals, and final assembly.

**Q: What if Alpha Vantage is down?**  
A: Script automatically falls back to Finnhub (if key provided), then Marketstack (if key provided).

**Q: How do I backfill previous weeks?**  
A: Use `--week X --eval-date YYYY-MM-DD` to generate specific historical weeks.

---

## Support

For issues or questions:

1. **Check logs** for detailed error messages
2. **Review this guide** for troubleshooting steps
3. **Test locally** before deploying to GitHub Actions
4. **Check API status** pages for service outages

---

## Changelog

### v2.0 (Current - GitHub Models)
- Migrated from OpenAI to GitHub Models (GPT-5)
- Changed token from `GITHUB_TOKEN` to `GH_TOKEN`
- Improved price fallback chain
- Enhanced error handling and reporting
- Simplified documentation

### v1.0 (Legacy - OpenAI)
- Initial release with OpenAI API
- Alpha Vantage data source
- Basic automation workflow
