# Deprecated Scripts

This directory contains scripts that are **no longer used** in the active workflow but kept for reference purposes.

## ❌ octagon_enrichment.py

**Status**: DEPRECATED - Replaced by `yfinance_enrichment.py`

**Reason**: OctagonAI free tier limited to 10 credits/month, but weekly automation requires ~36 credits/month (3-5 candidates × 4 weeks × 3 agents).

**Original Purpose**: 
- Enriched research candidates with institutional ownership data
- Queried 3 OctagonAI agents: holdings, stock-data, financials
- Provided unique institutional investor insights

**Why Kept**:
- Reference implementation of OpenAI SDK integration
- Documentation of OctagonAI API patterns
- May be useful if switching to paid OctagonAI tier in future

**Replacement**: `yfinance_enrichment.py` (FREE, unlimited)

---

## ❌ fmp_enrichment.py

**Status**: DEPRECATED - No longer functional (API changes)

**Reason**: Financial Modeling Prep (FMP) deprecated free tier endpoints on **August 31, 2025**. All profile, ratios, and growth endpoints now return:
```
403 Forbidden - Legacy Endpoint: This endpoint is only available for legacy users 
who have valid subscriptions prior August 31, 2025
```

**Original Purpose**:
- Enriched research candidates with fundamental data from FMP API
- Company profiles (sector, industry, CEO, employees)
- Financial ratios (P/E, ROE, debt/equity)
- Growth metrics (revenue, earnings, EPS growth)

**What Changed**:
- FMP discontinued free access to `/api/v3/profile`, `/api/v3/ratios`, `/api/v3/income-statement-growth`
- Free tier now limited to very basic endpoints (quote, search)
- Premium tier required ($49-99/month) for fundamental data

**Why Kept**:
- Reference implementation of FMP API integration
- Documentation of API patterns and data structures
- Historical record of what worked before API changes

**Replacement**: `yfinance_enrichment.py` (FREE, unlimited)

---

## Migration Path

If you were using these scripts, migrate to `yfinance_enrichment.py`:

### Before (Deprecated)
```bash
# OctagonAI (10 credits/month - insufficient)
python scripts/octagon_enrichment.py --week 8

# FMP (no longer works)
python scripts/fmp_enrichment.py --week 8
```

### After (Current)
```bash
# Yahoo Finance (FREE, unlimited)
python scripts/yfinance_enrichment.py --week 8
```

### Data Comparison

| Data Point | OctagonAI | FMP | Yahoo Finance |
|------------|-----------|-----|---------------|
| Company Profile | ✅ | ❌ (403) | ✅ |
| Financial Ratios | ✅ | ❌ (403) | ✅ |
| Growth Metrics | ✅ | ❌ (403) | ✅ |
| Institutional Holdings | ✅ | ❌ (403) | ❌ |
| **Cost** | $0 (but limited) | $0 (broken) | $0 (works) |
| **Rate Limit** | 10/month | Deprecated | Unlimited |

**Trade-off**: Yahoo Finance doesn't provide institutional holdings data, but it's the only working free option.

---

## Do Not Use

These scripts are kept **for reference only**. Do not add them back to your workflow:

- ❌ `octagon_enrichment.py` - Insufficient credits
- ❌ `fmp_enrichment.py` - API no longer functional

Use `yfinance_enrichment.py` instead.
