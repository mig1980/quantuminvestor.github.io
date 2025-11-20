# Portfolio Automation - Quick Start Guide

## Prerequisites

### 1. GitHub Token (for AI)
```powershell
# Get token: https://github.com/settings/tokens
# No scopes needed - leave all unchecked
$env:GH_TOKEN = "ghp_your-token-here"
```

### 2. Alpha Vantage Key (for market data)
```powershell
# Get free key: https://www.alphavantage.co/support/#api-key
$env:ALPHAVANTAGE_API_KEY = "your-key-here"
```

### 3. Install Dependencies
```powershell
cd scripts
pip install -r requirements.txt
```

## Usage

### Basic Run (Auto-detect next week)
```powershell
python scripts/portfolio_automation.py
```

### Specify Week Number
```powershell
python scripts/portfolio_automation.py --week 6
```

### Use Different Model
```powershell
# Use GPT-4o instead of GPT-5
python scripts/portfolio_automation.py --model "openai/gpt-4o"
```

### Data-Only Mode (No AI)
```powershell
# Skip AI narrative generation, just update data
python scripts/portfolio_automation.py --data-source alphavantage
```

### Custom Evaluation Date
```powershell
# Override the current date
python scripts/portfolio_automation.py --eval-date 2025-11-15
```

## GitHub Actions

Add to `.github/workflows/portfolio-update.yml`:

```yaml
name: Weekly Portfolio Update

on:
  schedule:
    - cron: '0 20 * * 5'  # Friday 8 PM UTC
  workflow_dispatch:

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - uses: actions/setup-python@v5
        with:
          python-version: '3.13'
      
      - name: Install dependencies
        run: pip install -r scripts/requirements.txt
      
      - name: Run automation
        env:
          GH_TOKEN: ${{ secrets.GH_MODELS_TOKEN }}
          ALPHAVANTAGE_API_KEY: ${{ secrets.ALPHAVANTAGE_API_KEY }}
          FINNHUB_API_KEY: ${{ secrets.FINNHUB_API_KEY }}
        run: python scripts/portfolio_automation.py --data-source alphavantage
      
      - name: Commit changes
        run: |
          git config user.name "GitHub Actions"
          git config user.email "actions@github.com"
          git add .
          git commit -m "Week ${{ github.run_number }} update" || echo "No changes"
          git push
```

## Key Files Generated

```
master data/
  ├── master.json              # Main data file (updated)
  └── archive/
      └── master-20251119.json # Timestamped backup

Posts/
  └── GenAi-Managed-Stocks-Portfolio-Week-6.html  # Weekly post

Media/
  └── W6.webp                  # Hero image

Data/W6/                       # Legacy backup
  └── master.json
```

## Testing

### Test GitHub Models Connection
```powershell
cd scripts
python test_ai_apis.py
```

### Dry Run (Check without committing)
```powershell
# Review what would be generated
python scripts/portfolio_automation.py --week 999
```

## Troubleshooting

### Error: "AI client not initialized"
**Solution**: Set `GH_TOKEN` environment variable
```powershell
$env:GH_TOKEN = "ghp_..."
```

### Error: "Alpha Vantage API key required"
**Solution**: Set `ALPHAVANTAGE_API_KEY` or use AI mode
```powershell
$env:ALPHAVANTAGE_API_KEY = "your-key"
# OR use AI mode (slower)
python portfolio_automation.py --data-source ai
```

### Rate Limiting Issues
The script handles rate limits automatically:
- **Alpha Vantage**: 5 req/min (12s between calls)
- **Finnhub**: 5 req/min (12s between calls)
- **Marketstack**: 2s between calls

### Check Logs
Look for symbols in output:
- ✓ = Success
- ✗ = Error  
- ⚠ = Warning

## Environment Variables Reference

| Variable | Required | Purpose |
|----------|----------|---------|
| `GH_TOKEN` | For AI | GitHub Models access (GPT-5) |
| `ALPHAVANTAGE_API_KEY` | For data | Stock/crypto prices |
| `FINNHUB_API_KEY` | Optional | Fallback price data |
| `MARKETSTACK_API_KEY` | Optional | Additional fallback |

## Model Options

```powershell
# GPT-5 (default, best)
python portfolio_automation.py --model "openai/gpt-5"

# GPT-4o (fallback)
python portfolio_automation.py --model "openai/gpt-4o"

# GPT-4o-mini (fastest)
python portfolio_automation.py --model "openai/gpt-4o-mini"
```

## Tips

1. **Weekly Schedule**: Run Friday evenings after market close
2. **Backup First**: Script auto-backups to `master data/archive/`
3. **Version Control**: Commit changes after each run
4. **Monitor Output**: Check execution report at the end
5. **Test First**: Use `test_ai_apis.py` before automation

## Support

- Full docs: `GITHUB_MODELS_MIGRATION.md`
- Issues: Check execution report for detailed error logs
- Test script: `scripts/test_ai_apis.py`
