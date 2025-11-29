# Yahoo Finance Enrichment Guide

## Overview

**Yahoo Finance enrichment** is the recommended solution for adding fundamental data to research candidates. It's completely **FREE**, has **no rate limits**, and provides comprehensive company information.

## Why Yahoo Finance?

### Comparison with Alternatives

| Feature | Yahoo Finance (yfinance) | OctagonAI | FMP Free Tier |
|---------|-------------------------|-----------|---------------|
| **Cost** | $0 | $0 | $0 |
| **Rate Limit** | None (unlimited) | 10 calls/month ⚠️ | Deprecated ❌ |
| **API Key** | Not required ✅ | Required | Required |
| **Data Coverage** | 20+ fields | Institutional + fundamentals | API changed Aug 31, 2025 |
| **Reliability** | High (unofficial but stable) | Credit constraints | No longer functional |
| **Status** | ✅ **RECOMMENDED** | Limited capacity | ❌ Deprecated |

### What Happened to FMP?

On **August 31, 2025**, Financial Modeling Prep (FMP) deprecated free tier endpoints:
- `/api/v3/profile/{ticker}` → 403 Forbidden
- `/api/v4/profile/{ticker}` → 403 Forbidden
- `/api/v3/ratios/{ticker}` → 403 Forbidden

Error message: *"Legacy Endpoint: Due to Legacy endpoints being no longer supported - This endpoint is only available for legacy users who have valid subscriptions prior August 31, 2025"*

**Solution**: Migrated to Yahoo Finance (yfinance library).

---

## Quick Start

### 1. Install yfinance

```bash
pip install yfinance
```

### 2. Run Enrichment

```bash
python scripts/yfinance_enrichment.py --week 8
```

That's it! No API key required.

---

## Data Coverage

Yahoo Finance enrichment adds **20-25 fields** per candidate:

### Company Information
- `sector` - Business sector (e.g., "Technology")
- `industry` - Industry classification (e.g., "Semiconductors")
- `description` - Company description
- `website` - Corporate website URL
- `employees` - Number of employees
- `country` - Headquarters country

### Valuation Metrics
- `pe_ratio_forward` - Forward P/E ratio
- `pe_ratio_trailing` - Trailing P/E ratio
- `pb_ratio` - Price-to-book ratio
- `market_cap` - Market capitalization (USD)
- `dividend_yield_pct` - Dividend yield percentage

### Profitability Metrics
- `profit_margin_pct` - Net profit margin
- `operating_margin_pct` - Operating profit margin
- `roe_pct` - Return on equity (%)
- `roa_pct` - Return on assets (%)

### Growth Metrics
- `revenue_growth_yoy` - Revenue growth year-over-year (%)
- `earnings_growth_yoy` - Earnings growth year-over-year (%)

### Financial Health
- `debt_equity_ratio` - Debt-to-equity ratio
- `current_ratio` - Current ratio (liquidity)
- `cash_millions` - Cash and equivalents (millions USD)
- `debt_millions` - Total debt (millions USD)

### Risk & Performance
- `beta` - Stock beta (volatility vs market)
- `year_high` - 52-week high price
- `year_low` - 52-week low price

---

## Usage

### Command Line

```bash
# Basic usage
python scripts/yfinance_enrichment.py --week 8

# Help
python scripts/yfinance_enrichment.py --help
```

### Integration with Automation

Add after `portfolio_automation.py` in your weekly workflow:

```bash
# Step 1: Main automation (includes Marketstack enrichment)
python scripts/portfolio_automation.py --week 8

# Step 2: Add Yahoo Finance fundamentals
python scripts/yfinance_enrichment.py --week 8
```

---

## How It Works

### Data Flow

```
INPUT: Data/W8/research_candidates.json
├─ ticker: "AVGO"
├─ momentum_4w: "+12.3%"        [Marketstack]
├─ momentum_12w: "+28.7%"       [Marketstack]
├─ volume_avg: "3.2M"           [Marketstack]
└─ price: "$176.41"             [Marketstack]

ENRICHMENT: yfinance_enrichment.py
├─ Fetch ticker info from Yahoo Finance
├─ Extract 20-25 fundamental fields
└─ Add to candidate object

OUTPUT: Data/W8/research_candidates.json (enriched)
├─ ticker: "AVGO"
├─ momentum_4w: "+12.3%"        [Marketstack]
├─ momentum_12w: "+28.7%"       [Marketstack]
├─ volume_avg: "3.2M"           [Marketstack]
├─ price: "$176.41"             [Marketstack]
├─ sector: "Technology"         [Yahoo Finance] ✅
├─ industry: "Semiconductors"   [Yahoo Finance] ✅
├─ pe_ratio_forward: 65.31      [Yahoo Finance] ✅
├─ roe_pct: 27.08               [Yahoo Finance] ✅
└─ revenue_growth_yoy: 16.4     [Yahoo Finance] ✅
```

### Example Output

```json
{
  "week": 8,
  "candidates": [
    {
      "ticker": "AVGO",
      "momentum_4w": "+12.3%",
      "momentum_12w": "+28.7%",
      "volume_avg": "3.2M",
      "price": "$176.41",
      "sector": "Technology",
      "industry": "Semiconductors",
      "description": "Broadcom Inc. designs, develops, and supplies...",
      "website": "https://www.broadcom.com",
      "employees": 20000,
      "country": "United States",
      "pe_ratio_forward": 65.31,
      "pe_ratio_trailing": 70.25,
      "pb_ratio": 14.2,
      "market_cap": 1902924136448,
      "dividend_yield_pct": 1.8,
      "profit_margin_pct": 31.59,
      "operating_margin_pct": 45.2,
      "roe_pct": 27.08,
      "roa_pct": 12.5,
      "revenue_growth_yoy": 16.4,
      "earnings_growth_yoy": 188.1,
      "debt_equity_ratio": 1.66,
      "current_ratio": 1.5,
      "cash_millions": 11105.0,
      "debt_millions": 38450.0,
      "beta": 1.21,
      "year_high": 240.00,
      "year_low": 95.50
    }
  ],
  "enrichment": {
    "yahoo_finance": {
      "timestamp": "2025-12-06T10:30:00",
      "week": 8,
      "total": 3,
      "enriched": 3,
      "failed": 0,
      "fields_added": 66
    }
  }
}
```

---

## Features

### Non-Blocking Execution

The script is designed to **never break the automation pipeline**:

```python
def run(self) -> bool:
    """Always returns True - non-blocking for automation"""
    try:
        # Enrichment logic
    except Exception as e:
        self.logger.error(f"❌ Enrichment failed: {e}")
        return True  # Still return success
```

**Why?** Enrichment is **optional enhancement**, not critical. If Yahoo Finance is down or a ticker fails, the rest of the workflow continues.

### Respectful Rate Limiting

```python
DELAY_BETWEEN_TICKERS = 0.5  # 0.5 seconds delay
```

Even though Yahoo Finance has no explicit rate limits, the script adds delays to be respectful to their servers.

### Comprehensive Logging

All operations logged to `Data/W{n}/yfinance_enrichment.log`:

```
2025-12-06 10:30:15 - INFO - ============================================================
2025-12-06 10:30:15 - INFO - YAHOO FINANCE ENRICHMENT - WEEK 8
2025-12-06 10:30:15 - INFO - ============================================================
2025-12-06 10:30:15 - INFO - 📌 FREE & UNLIMITED - No API key required
2025-12-06 10:30:15 - INFO - 📌 Complements Marketstack (price/volume/momentum)
2025-12-06 10:30:15 - INFO - 📌 Adds: company info, ratios, growth, financials
2025-12-06 10:30:15 - INFO - ============================================================
2025-12-06 10:30:16 - INFO - ✅ Loaded 3 candidates
2025-12-06 10:30:16 - INFO - 
2025-12-06 10:30:16 - INFO - [1/3] AVGO
2025-12-06 10:30:17 - INFO -    • Sector: Technology
2025-12-06 10:30:17 - INFO -    • Industry: Semiconductors
2025-12-06 10:30:17 - INFO -    • P/E (Forward): 65.31
2025-12-06 10:30:17 - INFO -    • Market Cap: $1902.9B
2025-12-06 10:30:17 - INFO -    • Profit Margin: 31.59%
2025-12-06 10:30:17 - INFO -    • ROE: 27.08%
2025-12-06 10:30:17 - INFO -    • Revenue Growth: +16.4%
2025-12-06 10:30:17 - INFO -    • Earnings Growth: +188.1%
2025-12-06 10:30:17 - INFO - ✅ Added 23 field(s)
```

---

## Troubleshooting

### Error: ModuleNotFoundError: No module named 'yfinance'

**Solution**:
```bash
pip install yfinance
```

### Error: No data returned for ticker

**Cause**: Ticker not found or Yahoo Finance temporarily unavailable.

**Solution**: This is **normal** and **non-blocking**. The script logs the failure and continues with other candidates.

### Warning: Failed to enrich candidate

**Cause**: Network timeout, invalid ticker, or data unavailable.

**Impact**: **None** - Script continues and returns success. Check logs for details.

### Slow enrichment (>5 seconds per ticker)

**Cause**: Network latency or Yahoo Finance server load.

**Solution**: The script already has 0.5s delays. Increase if needed:

```python
DELAY_BETWEEN_TICKERS = 1.0  # Increase to 1 second
```

---

## Maintenance

### Update yfinance Library

```bash
pip install --upgrade yfinance
```

### Monitor Yahoo Finance Changes

yfinance is an **unofficial library** that scrapes Yahoo Finance. While stable, it may break if Yahoo changes their website structure.

**Mitigation**:
- Keep yfinance updated
- Monitor GitHub issues: https://github.com/ranaroussi/yfinance/issues
- Script is non-blocking, so failures won't break automation

---

## Comparison with Deprecated Solutions

### vs. OctagonAI

| Feature | Yahoo Finance | OctagonAI |
|---------|--------------|-----------|
| **Cost** | $0 | $0 |
| **Rate Limit** | Unlimited | 10 calls/month |
| **Weekly Usage** | 3-5 calls (no limit) | 3-5 calls (runs out in 2 weeks) |
| **Data** | 20+ fundamental fields | Institutional + fundamentals |
| **API Key** | Not required | Required |
| **Status** | ✅ Active | ⚠️ Limited capacity |

**Decision**: Use Yahoo Finance for unlimited enrichment. OctagonAI's 10 credits/month is insufficient for weekly automation (needs 36/month).

### vs. FMP Free Tier

| Feature | Yahoo Finance | FMP Free Tier |
|---------|--------------|---------------|
| **Cost** | $0 | $0 |
| **Rate Limit** | Unlimited | 250 calls/day |
| **Endpoints** | All functional | Deprecated Aug 31, 2025 ❌ |
| **Error** | None | 403 Forbidden (Legacy Endpoint) |
| **API Key** | Not required | Required |
| **Status** | ✅ Active | ❌ Deprecated |

**Decision**: FMP free tier no longer functional. Yahoo Finance is the only viable free option.

---

## Script Architecture

### Class Structure

```python
class YahooFinanceEnricher:
    def __init__(self, week_number: int):
        """Initialize enricher with week number"""
        
    def load_candidates(self) -> bool:
        """Load research_candidates.json"""
        
    def enrich_candidate(self, candidate: Dict) -> Dict:
        """Enrich single candidate with Yahoo Finance data"""
        
    def save_candidates(self) -> bool:
        """Save enriched candidates back to JSON"""
        
    def run(self) -> bool:
        """Main execution - always returns True (non-blocking)"""
```

### Error Handling Strategy

```python
try:
    info = yf.Ticker(ticker).info
    # Extract fields
    enriched = {...}
except Exception as e:
    logger.error(f"❌ Failed to enrich {ticker}: {e}")
    enriched = {}  # Return empty dict, continue with others
```

**Design Principle**: Fail gracefully, never abort pipeline.

---

## Future Enhancements

Potential improvements (not yet implemented):

1. **Retry Logic**: Add retries for transient network errors
2. **Data Quality Checks**: Flag missing critical fields (e.g., no P/E ratio)
3. **Summary Report**: Generate enrichment quality report per week
4. **Caching**: Cache ticker data to reduce redundant API calls
5. **Batch Processing**: Fetch multiple tickers in parallel (if yfinance supports)

---

## Summary

### ✅ Recommended Setup

**Use Yahoo Finance** for all fundamental data enrichment:

```bash
# Weekly workflow
python scripts/portfolio_automation.py --week 8      # Marketstack
python scripts/yfinance_enrichment.py --week 8       # Yahoo Finance
```

**Benefits**:
- ✅ Zero cost
- ✅ No rate limits
- ✅ No API key required
- ✅ Comprehensive data (20-25 fields)
- ✅ Non-blocking (safe for automation)

**Tradeoffs**:
- ⚠️ Unofficial library (may break if Yahoo changes)
- ⚠️ No institutional holdings data (vs OctagonAI)

**Overall**: Best free solution for fundamental data enrichment.

---

## Support

For issues or questions:
1. Check logs: `Data/W{n}/yfinance_enrichment.log`
2. Verify yfinance: `pip show yfinance`
3. Test manually: `python -c "import yfinance as yf; print(yf.Ticker('AAPL').info)"`
4. GitHub Issues: https://github.com/mig1980/quantuminvestor/issues
