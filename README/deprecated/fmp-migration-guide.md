# Dual API Strategy: Marketstack + FMP Free Tier

## Overview

Your portfolio automation uses **two complementary APIs** to enrich research candidates:

1. **Marketstack** (built into `portfolio_automation.py`) - Price & momentum data
2. **FMP Free Tier** (`fmp_enrichment.py`) - Fundamental & company data

## Quick Start

### 1. Get FMP Free API Key
- Sign up: https://site.financialmodelingprep.com/
- Select: **FREE tier** (250 calls/day - no credit card required)
- Copy your API key

### 2. Set Environment Variable

```powershell
# Windows PowerShell
$env:FMP_API_KEY = "your_fmp_api_key_here"

# Or add permanently
[System.Environment]::SetEnvironmentVariable('FMP_API_KEY', 'your_key', 'User')
```

### 3. Run Enrichment

```bash
# FMP enrichment (complements Marketstack data)
python scripts/fmp_enrichment.py --week 7
```

## Data Coverage - What Each API Provides

### Marketstack (Already Integrated)
**Source**: Built into `portfolio_automation.py` → `enrich_candidates_with_marketstack()`

| Data Point | Endpoint | Status |
|------------|----------|--------|
| Current Price | `/eod/latest` | ✅ Working |
| Historical Prices (12 weeks) | `/eod` | ✅ Working |
| 4-week Momentum | Calculated from EOD | ✅ Working |
| 12-week Momentum | Calculated from EOD | ✅ Working |
| Average Volume | Calculated from EOD | ✅ Working |

**Rate Limit**: 100 calls/month (free tier)  
**Cost**: $0

### FMP Free Tier (New Addition)
**Source**: Separate script `fmp_enrichment.py`

| Data Point | Endpoint | Status |
|------------|----------|--------|
| **Company Profile** | `/profile/{ticker}` | ✅ FREE |
| - Sector, Industry | | ✅ |
| - CEO, Employees | | ✅ |
| - Description, Website | | ✅ |
| **Financial Ratios** | `/ratios/{ticker}` | ✅ FREE |
| - P/E Ratio | | ✅ |
| - P/B, P/S Ratios | | ✅ |
| - ROE, ROA | | ✅ |
| - Debt/Equity Ratio | | ✅ |
| - Current Ratio | | ✅ |
| - Profit Margin | | ✅ |
| **Growth Metrics** | `/income-statement-growth/{ticker}` | ✅ FREE |
| - Revenue Growth YoY | | ✅ |
| - Net Income Growth | | ✅ |
| - EPS Growth | | ✅ |
| - Operating Income Growth | | ✅ |

**Rate Limit**: 250 calls/day (free tier)  
**Cost**: $0

### What's NOT Included (Requires Paid Tiers)

| Data Point | Tier Required | Cost |
|------------|---------------|------|
| 13F Institutional Holdings | Ultimate | $99/mo |
| Intraday Price Data | Premium+ | $49/mo |
| Earnings Transcripts | Ultimate | $99/mo |

## API Endpoints Used

### FMP Free Tier (3 endpoints per candidate)

1. **Company Profile** (`/profile/{ticker}`)
   - Available: FREE tier ✅
   - Returns: `sector`, `industry`, `ceo`, `fullTimeEmployees`, `description`, `website`, `country`
   - Rate: 250 calls/day

2. **Financial Ratios** (`/ratios/{ticker}`)
   - Available: FREE tier ✅
   - Returns: `priceEarningsRatio`, `returnOnEquity`, `debtEquityRatio`, `currentRatio`, etc.
   - Rate: 250 calls/day

3. **Income Statement Growth** (`/income-statement-growth/{ticker}`)
   - Available: FREE tier ✅
   - Returns: `growthRevenue`, `growthNetIncome`, `growthOperatingIncome`, `growthEPS`
   - Rate: 250 calls/day

## How It Works - Data Flow

```
WEEK 7 ENRICHMENT FLOW
=====================

Step 1: Marketstack (Built-in)
------------------------------
portfolio_automation.py generates research_candidates.json with:
✅ ticker, momentum_4w, momentum_12w, volume_avg, price

Step 2: FMP Free Tier (Add-on)
-------------------------------
fmp_enrichment.py enriches research_candidates.json with:
✅ sector, industry, CEO, employees
✅ P/E ratio, ROE, debt/equity ratio
✅ revenue growth, net income growth, EPS growth

Final Output: research_candidates.json
---------------------------------------
{
  "ticker": "AVGO",
  "momentum_4w": "+12.3%",           // ← Marketstack
  "momentum_12w": "+28.7%",          // ← Marketstack
  "volume_avg": "3.2M",              // ← Marketstack
  "price": "$176.41",                // ← Marketstack
  "sector": "Technology",            // ← FMP
  "industry": "Semiconductors",      // ← FMP
  "ceo": "Hock Tan",                 // ← FMP
  "employees": 20000,                // ← FMP
  "pe_ratio": 32.5,                  // ← FMP
  "roe_pct": 28.3,                   // ← FMP
  "debt_equity_ratio": 1.2,          // ← FMP
  "revenue_growth_yoy": 47.3,        // ← FMP
  "net_income_growth_yoy": 35.2      // ← FMP
}
```

## Integration into Automation

### Current Setup (Marketstack Only)

Your `portfolio_automation.py` already has Marketstack built-in:

```python
# Line ~1650 in portfolio_automation.py
if self.marketstack_key:
    research_candidates = self.enrich_candidates_with_marketstack(research_candidates)
```

### Add FMP Enrichment (Recommended)

Run FMP enrichment **after** `portfolio_automation.py` completes:

```powershell
# Weekly automation workflow
python scripts/portfolio_automation.py --week 7
python scripts/fmp_enrichment.py --week 7        # ← Add this line
```

This ensures:
1. Marketstack provides price/momentum data first
2. FMP adds fundamental data on top
3. Both APIs' data merged in final `research_candidates.json`

## Cost Analysis

### API Usage Calculator

**Weekly Usage**: 3-5 research candidates per week

| API | Calls/Week | Calls/Month | Limit | Utilization | Cost |
|-----|-----------|-------------|-------|-------------|------|
| **Marketstack** | ~10 | ~40 | 100/mo | 40% | $0 |
| **FMP Free** | 9-15 | 36-60 | 7,500/mo | <1% | $0 |
| **Total** | | 76-100 | | | **$0/month** ✅ |

### Detailed Breakdown

**Marketstack** (Built into portfolio_automation.py):
- Fetches 12 weeks EOD data per candidate
- ~3-5 candidates/week = 10 API calls
- 100 calls/month free tier = **Sufficient**

**FMP Free Tier** (fmp_enrichment.py):
- 3 endpoints per candidate (profile, ratios, growth)
- 3 candidates × 3 endpoints = 9 calls/week
- 9 × 4 weeks = 36 calls/month
- 250 calls/day limit = 7,500/month
- **Only 0.5% of daily limit used** ✅

### Cost Comparison

| Solution | Monthly Cost | Institutional Data | Fundamentals | Momentum | Rate Limits |
|----------|--------------|-------------------|--------------|----------|-------------|
| **Marketstack + FMP Free** | $0 | ❌ | ✅ | ✅ | Generous |
| OctagonAI | $0 | ✅ | ✅ | ✅ | 10 calls/mo ⚠️ |
| FMP Ultimate | $99 | ✅ | ✅ | ✅ | 3K/min |

**Winner**: Marketstack + FMP Free (no institutional data, but $0 cost)

## Testing

### Step 1: Set API Key

```powershell
# Get FREE key from https://site.financialmodelingprep.com/
$env:FMP_API_KEY = "your_free_tier_key_here"
```

### Step 2: Test Enrichment

```bash
python scripts/fmp_enrichment.py --week 7
```

**Expected output**:
```
============================================================
FMP FREE TIER ENRICHMENT - WEEK 7
============================================================
📌 Complements Marketstack (price/volume/momentum)
📌 Adds fundamentals: company info, ratios, growth
============================================================
✅ FMP API key configured
✅ Loaded 3 candidates
📊 3 candidate(s) × 3 endpoints = 9 API calls
   Free tier: 9/250 daily limit (3.6%)

[1/3] AVGO
🔍 Enriching AVGO...
   Querying company profile...
      • Sector: Technology
      • Industry: Semiconductors
   Querying financial ratios...
      • P/E Ratio: 32.5
      • ROE: 28.3%
   Querying financial growth...
      • Revenue growth: +47.3%
      • Net income growth: +35.2%
✅ Added 12 field(s)

[2/3] PLTR
...
```

### Step 3: Verify Output

Check `Data/W7/research_candidates.json`:

```json
{
  "week": 7,
  "candidates": [
    {
      "ticker": "AVGO",
      "momentum_4w": "+12.3%",        // Marketstack
      "momentum_12w": "+28.7%",       // Marketstack
      "sector": "Technology",         // FMP
      "industry": "Semiconductors",   // FMP
      "pe_ratio": 32.5,               // FMP
      "roe_pct": 28.3,                // FMP
      "revenue_growth_yoy": 47.3      // FMP
    }
  ],
  "enrichment": {
    "fmp": {
      "timestamp": "2025-11-29T...",
      "total": 3,
      "enriched": 3,
      "fields_added": 36
    }
  }
}
```

## Output Format

Both scripts produce the same enriched JSON structure:

```json
{
  "week": 7,
  "candidates": [
    {
      "ticker": "AVGO",
      "investors_holding": 4380,
      "holder_changes": "increasing",
      "market_cap": 957000000000,
      "current_price": 176.41,
      "revenue_growth_yoy": 47.3,
      "net_income_growth_yoy": 35.2
    }
  ],
  "enrichment": {
    "fmp": {
      "timestamp": "2025-11-29T16:00:00",
      "week": 7,
      "total": 3,
      "enriched": 3,
      "failed": 0,
      "fields_added": 18
    }
  }
}
```

## Troubleshooting

### Error: "Error Message: This endpoint is only for premium users"

**Cause**: Trying to access institutional holdings with free FMP tier

**Solution**:
- Upgrade to Ultimate tier ($99/mo), OR
- Comment out `enrich_institutional_holdings()` in `fmp_enrichment.py`, OR
- Use OctagonAI for institutional data (10 credits/mo free)

### Error: "Limit Reach"

**Cause**: Exceeded FMP API rate limit

**Solution**:
- Free tier: 250 calls/day (wait until next day)
- Ultimate tier: Should not happen (3,000 calls/minute)

### Error: No data returned

**Cause**: Ticker not found or data unavailable

**Solution**: Normal for some tickers - script continues with other candidates

## Summary

### Recommended Setup

**Use Both APIs** (Total cost: $0/month):

1. **Marketstack** (already integrated) - Price, volume, momentum
2. **FMP Free Tier** (new) - Company fundamentals, ratios, growth

**Benefits**:
- ✅ Zero cost
- ✅ Comprehensive data coverage
- ✅ No institutional holdings, but saves $99/mo
- ✅ Generous rate limits (100/mo + 250/day)

### Data You Get

| Category | Data Points | Source |
|----------|-------------|--------|
| **Price & Momentum** | Current price, 4w/12w momentum, volume | Marketstack |
| **Company Info** | Sector, industry, CEO, employees, description | FMP Free |
| **Valuation** | P/E, P/B, P/S ratios | FMP Free |
| **Profitability** | ROE, ROA, profit margin | FMP Free |
| **Leverage** | Debt/equity ratio, current ratio | FMP Free |
| **Growth** | Revenue, net income, EPS growth | FMP Free |

### Data You DON'T Get (vs OctagonAI)

| Data Point | Why Missing | Workaround |
|------------|-------------|------------|
| Institutional investor counts | Requires FMP Ultimate ($99/mo) | Use qualitative research instead |
| Holder change trends | Requires FMP Ultimate ($99/mo) | Not critical for momentum strategy |

### Files Created/Modified

- ✅ Created: `scripts/fmp_enrichment.py` (498 lines)
- ✅ Updated: `README/fmp-migration-guide.md` (this file)
- 📄 Kept: `scripts/portfolio_automation.py` (Marketstack integration unchanged)
