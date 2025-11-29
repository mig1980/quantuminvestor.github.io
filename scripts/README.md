# Scripts Documentation

Comprehensive guide to all automation scripts in the portfolio management system.

## 📋 Table of Contents

- [Core Scripts](#core-scripts)
- [Enrichment Scripts](#enrichment-scripts)
- [Newsletter Scripts](#newsletter-scripts)
- [Utility Scripts](#utility-scripts)
- [Deprecated Scripts](#deprecated-scripts)

---

## Core Scripts

### portfolio_automation.py

**Main orchestrator** - Handles the entire weekly portfolio update workflow.

#### Purpose
- Fetches current prices from Finnhub/Marketstack
- Calculates portfolio metrics, performance, benchmarks
- Generates visual components (performance table, chart)
- Runs AI validation (Prompt A), research (Prompt B), and assembly (Prompt D)

#### Usage
```bash
python scripts/portfolio_automation.py --week 8 [options]

Options:
  --week N              Week number (auto-detected if omitted)
  --model MODEL         Azure OpenAI model deployment name
  --data-source SOURCE  "data-only" (skip AI) or "full" (default)
  --eval-date DATE      Override evaluation date (YYYY-MM-DD)
  --palette PALETTE     Color scheme: default, blue, green, purple
```

#### Dependencies
- Azure OpenAI (your deployment)
- Marketstack API (primary data source)
- Finnhub API (fallback)

#### Environment Variables
```powershell
$env:AZURE_OPENAI_ENDPOINT = "https://your-endpoint.openai.azure.com/"
$env:AZURE_OPENAI_KEY = "your-key"
$env:AZURE_OPENAI_DEPLOYMENT = "your-deployment-name"
$env:MARKETSTACK_API_KEY = "your-key"
$env:FINNHUB_API_KEY = "your-key"  # Optional
```

#### Output Files
- `Data/W{n}/master.json` - Week snapshot
- `Data/W{n}/research_candidates.json` - Candidates with Marketstack data
- `Data/W{n}/decision_summary.json` - AI decision (HOLD/REBALANCE)
- `Data/W{n}/visuals.json` - Chart data
- `Data/W{n}/performance_table.html` - Performance table
- `Data/W{n}/performance_chart.svg` - Normalized chart
- `Posts/GenAi-Managed-Stocks-Portfolio-Week-{n}.html` - Final blog post

#### Error Handling
- **FATAL**: Missing data, calculation failures → Raises ValueError
- **NON-FATAL**: Validation failures → Continues with warning
- **TRANSIENT**: Network errors → Retries with exponential backoff

---

## Enrichment Scripts

### yfinance_enrichment.py ⭐ RECOMMENDED

**FREE and UNLIMITED** - Enriches candidates with fundamental data from Yahoo Finance.

#### Purpose
Adds comprehensive fundamental data to research candidates:
- Company info: sector, industry, employees, website
- Valuation: P/E ratios, P/B, market cap
- Profitability: ROE, ROA, profit margins
- Growth: revenue/earnings growth YoY
- Financial health: debt/equity, cash, current ratio

#### Usage
```bash
pip install yfinance
python scripts/yfinance_enrichment.py --week 8
```

#### Dependencies
- `yfinance` library (pip install yfinance)
- No API key required ✅

#### Output
Enriches `Data/W{n}/research_candidates.json` with 20-25 fields per candidate:

```json
{
  "ticker": "AVGO",
  "sector": "Technology",
  "industry": "Semiconductors",
  "pe_ratio_forward": 65.31,
  "roe_pct": 27.08,
  "revenue_growth_yoy": 16.4,
  "debt_equity_ratio": 1.66
}
```

#### Logging
`Data/W{n}/yfinance_enrichment.log`

#### Features
- Non-blocking: Returns success even if enrichment fails
- Complements Marketstack (price/momentum)
- 0.5s delay between tickers (respectful to Yahoo servers)

---

## Newsletter Scripts

### generate_newsletter_narrative.py

Generates newsletter narrative from weekly data.

#### Purpose
- Extracts key data from master.json, decision_summary.json
- Formats portfolio performance, holdings, benchmarks
- Creates structured JSON for HTML generation

#### Usage
```bash
python scripts/generate_newsletter_narrative.py --week 8
```

#### Output
`newsletters/week{n}_narrative.json`

```json
{
  "week": 8,
  "evaluation_date": "2025-12-06",
  "portfolio_value": 155876.45,
  "week_return": 2.34,
  "decision": "HOLD",
  "holdings": [...],
  "benchmarks": {...}
}
```

---

### generate_newsletter_html.py

Creates email-optimized HTML newsletter.

#### Purpose
- Converts narrative JSON to HTML email
- 95%+ email client compatibility
- ~50KB file size, mobile/desktop responsive
- Inline CSS, table-based layout

#### Usage
```bash
python scripts/generate_newsletter_html.py --week 8
```

#### Input
`newsletters/week{n}_narrative.json`

#### Output
`newsletters/week{n}_newsletter.html`

#### Features
- Gmail, Outlook, Apple Mail compatible
- Dark mode support
- Mobile-first responsive design

---

## Rebalancing Scripts

### automated_rebalance.py

Executes portfolio rebalancing based on AI decision.

#### Purpose
- Loads decision_summary.json from Prompt B
- Fetches current market prices
- Applies trades: exit, buy, trim, add_to_existing
- Validates constraints (6-10 positions, 20% cap, $500 min)
- Updates master.json with backup

#### Usage
```bash
python scripts/automated_rebalance.py --week 8 [--dry-run]

Options:
  --week N      Week number (required)
  --dry-run     Preview changes without updating master.json
```

#### Dependencies
- Finnhub API (fetch prices)

#### Environment Variables
```powershell
$env:FINNHUB_API_KEY = "your-key"
```

#### Process
1. Load decision_summary.json
2. Validate structure and trade instructions
3. Fetch current prices
4. Apply trades sequentially
5. Validate portfolio constraints
6. Create backup → Update master.json

#### Output
- `master data/archive/master-before-week{n}-rebalance-{timestamp}.json` (backup)
- `master data/master.json` (updated)

---

### execute_rebalance.py

Interactive rebalancing helper (manual mode).

#### Purpose
Manual alternative to automated_rebalance.py:
- Prompts for positions to exit/buy
- Calculates share quantities
- Updates master.json interactively

#### Usage
```bash
python scripts/execute_rebalance.py
```

#### Use Case
When you want manual control over rebalancing or automated script fails.

---

## Utility Scripts

### pixabay_hero_fetcher.py

Fetches hero images from Pixabay API.

#### Purpose
Download and optimize images for blog posts.

#### Usage
```bash
python scripts/pixabay_hero_fetcher.py --query "stock market" --week 8
```

#### Dependencies
- Pixabay API key
- Pillow (image processing)

---

### upload_newsletter_to_blob.py

Uploads newsletter HTML to Azure Blob Storage.

#### Purpose
Upload newsletter to public blob for email campaigns.

#### Usage
```bash
python scripts/upload_newsletter_to_blob.py --week 8
```

#### Dependencies
- Azure Storage Account
- azure-storage-blob, azure-identity

---

### verify_icons.py

Verifies CDN icon URLs are accessible.

#### Usage
```bash
python scripts/verify_icons.py
```

---

## Deprecated Scripts

### octagon_enrichment.py ❌ DEPRECATED

**Reason**: OctagonAI free tier limited to 10 credits/month (36 needed).

**Replacement**: `yfinance_enrichment.py`

### fmp_enrichment.py ❌ DEPRECATED

**Reason**: FMP deprecated free tier endpoints on August 31, 2025. All profile, ratios, and growth endpoints return 403 Forbidden.

**Replacement**: `yfinance_enrichment.py`

**Note**: Kept in repository for reference but not functional.

---

## Integration Example

### Weekly Automation Workflow

```bash
# Step 1: Main portfolio automation
python scripts/portfolio_automation.py --week 8

# Step 2: Enrich with Yahoo Finance fundamentals (FREE)
python scripts/yfinance_enrichment.py --week 8

# Step 3: Execute rebalancing (if AI recommends REBALANCE)
python scripts/automated_rebalance.py --week 8 --dry-run  # Preview
python scripts/automated_rebalance.py --week 8           # Execute

# Step 4: Generate newsletter
python scripts/generate_newsletter_narrative.py --week 8
python scripts/generate_newsletter_html.py --week 8

# Step 5: Upload to Azure (optional)
python scripts/upload_newsletter_to_blob.py --week 8
```

---

## Error Handling Patterns

All scripts follow consistent error handling:

### Non-Blocking (Enrichment)
Scripts that add optional data return success even on failure:
- `yfinance_enrichment.py`
- `octagon_enrichment.py` (deprecated)
- `fmp_enrichment.py` (deprecated)

**Behavior**: Logs error, continues automation pipeline.

### Blocking (Core Operations)
Scripts critical to workflow raise exceptions:
- `portfolio_automation.py` - Missing prices, calculation failures
- `automated_rebalance.py` - Invalid decision structure, constraint violations

**Behavior**: Raises ValueError, aborts execution.

### Transient (Network)
All scripts retry network operations:
- 3 retries with exponential backoff (1s, 2s, 4s)
- Handles 429 (rate limit), 500 (server error), timeouts

---

## Logging

All scripts use consistent logging format:

```
2025-11-29 14:30:15 - INFO - ✅ Portfolio automation initialized
2025-11-29 14:30:16 - INFO - 📊 Fetching prices for 8 positions...
2025-11-29 14:30:18 - ERROR - ❌ Failed to fetch NVDA: Timeout
2025-11-29 14:30:20 - WARNING - ⚠️  Validation failed: Minor calculation discrepancy
```

**Log Levels**:
- `INFO`: Normal operations
- `WARNING`: Non-critical issues (validation failures, enrichment skips)
- `ERROR`: Critical failures (API errors, missing data)

---

## Testing

### Test Individual Scripts

```bash
# Test enrichment (non-blocking)
python scripts/yfinance_enrichment.py --week 7

# Test automation (data-only mode, skip AI)
python scripts/portfolio_automation.py --week 7 --data-source data-only

# Test rebalancing (dry run)
python scripts/automated_rebalance.py --week 7 --dry-run
```

### Verify Outputs

```bash
# Check enriched candidates
cat Data/W7/research_candidates.json | python -m json.tool

# Check AI decision
cat Data/W7/decision_summary.json | python -m json.tool

# Check master.json backup
ls "master data/archive/" | Sort-Object -Descending | Select-Object -First 5
```

---

## Maintenance

### Update Dependencies

```bash
pip install --upgrade -r scripts/requirements.txt
```

### Clean Up Old Logs

```bash
# Remove logs older than 30 days
Get-ChildItem -Path "Data\W*\*.log" -Recurse | 
  Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-30)} | 
  Remove-Item
```

### Archive Old Data

```bash
# Move old weekly folders to archive
Move-Item "Data\W5" "Data\archive\W5"
```

---

## API Rate Limits

| API | Free Tier | Usage | Buffer |
|-----|-----------|-------|--------|
| Marketstack | 100 calls/month | ~10 calls/week | ✅ Sufficient |
| Yahoo Finance | Unlimited | ~3-5 calls/week | ✅ Generous |
| Azure OpenAI | Pay-per-token | ~3 prompts/week | ⚠️ Pay-as-go |
| Finnhub | 60 calls/min | ~10 calls/week | ✅ More than enough |

---

## Support

For issues or questions:
1. Check script docstrings: `python scripts/portfolio_automation.py --help`
2. Review logs: `Data/W{n}/*.log`
3. Verify API keys: `echo $env:AZURE_OPENAI_KEY`
4. GitHub Issues: https://github.com/mig1980/quantuminvestor/issues
