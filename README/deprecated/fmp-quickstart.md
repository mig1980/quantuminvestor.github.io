# Quick Start: Adding FMP Free Tier Enrichment

## 1. Get Your Free API Key

Visit: https://site.financialmodelingprep.com/

- Click "Get Free API Key"
- Sign up (no credit card required)
- Copy your API key

## 2. Set Environment Variable

```powershell
# Windows PowerShell
$env:FMP_API_KEY = "paste_your_key_here"

# To make it permanent (survives terminal restarts)
[System.Environment]::SetEnvironmentVariable('FMP_API_KEY', 'paste_your_key_here', 'User')
```

## 3. Add to Your Weekly Workflow

```powershell
# Your existing workflow
python scripts/portfolio_automation.py --week 7

# NEW: Add FMP enrichment after automation completes
python scripts/fmp_enrichment.py --week 7
```

That's it! Your `research_candidates.json` now includes:
- ✅ Price & momentum (from Marketstack)
- ✅ Company info: sector, industry, CEO, employees (from FMP)
- ✅ Financial ratios: P/E, ROE, debt/equity (from FMP)
- ✅ Growth metrics: revenue growth, net income growth (from FMP)

## What Gets Added?

**Before FMP** (Marketstack only):
```json
{
  "ticker": "AVGO",
  "momentum_4w": "+12.3%",
  "momentum_12w": "+28.7%",
  "volume_avg": "3.2M",
  "price": "$176.41"
}
```

**After FMP** (Marketstack + FMP):
```json
{
  "ticker": "AVGO",
  "momentum_4w": "+12.3%",
  "momentum_12w": "+28.7%",
  "volume_avg": "3.2M",
  "price": "$176.41",
  "sector": "Technology",
  "industry": "Semiconductors",
  "ceo": "Hock Tan",
  "employees": 20000,
  "pe_ratio": 32.5,
  "roe_pct": 28.3,
  "debt_equity_ratio": 1.2,
  "current_ratio": 2.1,
  "profit_margin_pct": 25.4,
  "revenue_growth_yoy": 47.3,
  "net_income_growth_yoy": 35.2,
  "eps_growth_yoy": 38.1
}
```

## Cost

- **Marketstack Free**: 100 calls/month (already using)
- **FMP Free**: 250 calls/day = 7,500/month
- **Your usage**: ~9 calls/week = 36 calls/month
- **Total cost**: **$0/month** ✅

## Questions?

See full documentation: `README/fmp-migration-guide.md`
