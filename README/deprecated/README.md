# Deprecated Documentation

This directory contains documentation for **deprecated features** that are no longer supported or functional. Kept for historical reference only.

## ❌ fmp-migration-guide.md

**Status**: DEPRECATED - FMP free tier no longer functional (Aug 31, 2025)

**Original Purpose**: Guide for integrating Financial Modeling Prep (FMP) free tier API for fundamental data enrichment.

**Why Deprecated**: 
- FMP deprecated free tier endpoints on August 31, 2025
- All `/api/v3/profile`, `/api/v3/ratios`, `/api/v3/income-statement-growth` endpoints return 403 Forbidden
- Error: "Legacy Endpoint: This endpoint is only available for legacy users who have valid subscriptions prior August 31, 2025"

**Replacement**: See [../yfinance-guide.md](../yfinance-guide.md) for current enrichment solution.

---

## ❌ fmp-quickstart.md

**Status**: DEPRECATED - FMP free tier no longer functional (Aug 31, 2025)

**Original Purpose**: Quick setup guide for FMP API integration.

**Why Deprecated**: Same as above - API endpoints no longer accessible on free tier.

**Replacement**: See [../yfinance-guide.md](../yfinance-guide.md) for current enrichment solution.

---

## Current Documentation

For **active** documentation, see:

- [../yfinance-guide.md](../yfinance-guide.md) - Yahoo Finance enrichment (RECOMMENDED)
- [../../scripts/README.md](../../scripts/README.md) - All scripts documentation
- [../../README.md](../../README.md) - Main project README

---

## Historical Context

### What Happened to FMP?

**Timeline**:
- **Before Aug 31, 2025**: FMP free tier provided 250 calls/day to profile, ratios, and growth endpoints
- **Aug 31, 2025**: FMP deprecated "legacy endpoints" for new free tier users
- **After Aug 31, 2025**: Free tier limited to basic quote/search endpoints only

**Impact**: 
- `fmp_enrichment.py` script no longer functional
- All fundamental data endpoints return 403 Forbidden
- Migration to Yahoo Finance (yfinance) completed

**Lesson**: Reliance on free tier APIs carries deprecation risk. Yahoo Finance (via yfinance library) is more stable as it's widely used and community-maintained.

---

## Do Not Use

This documentation is **for reference only**. Do not follow setup instructions in these files:

- ❌ `fmp-migration-guide.md` - API no longer works
- ❌ `fmp-quickstart.md` - API no longer works

Use current documentation instead.
