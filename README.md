# GenAI-Managed Stock Portfolio

An automated portfolio management system that uses AI (Azure OpenAI) to analyze market data, research stock candidates, and generate weekly performance reports.

## 🎯 Project Overview

This project demonstrates a fully automated investment portfolio managed by AI:

- **Weekly Analysis**: Automated price fetching, performance calculations, and benchmark comparisons
- **AI-Driven Research**: GPT-4 analyzes candidates using technical indicators and fundamental data
- **Automated Reporting**: Generates HTML blog posts and email newsletters
- **Data Enrichment**: Integrates multiple APIs (Marketstack, Yahoo Finance) for comprehensive market data

## 📁 Repository Structure

```
My-blog/
├── scripts/              # Python automation scripts
├── Data/                 # Weekly data snapshots (W5, W6, W7, etc.)
├── master data/          # Single source of truth (master.json)
│   └── archive/          # Timestamped backups
├── Posts/                # Generated HTML blog posts
├── Prompt/               # AI prompt templates
├── README/               # Documentation files
├── Media/                # Images and assets
├── templates/            # HTML templates (header, footer)
└── js/                   # Frontend JavaScript

```

## 🚀 Quick Start

### Prerequisites

- **Python 3.9+**
- **API Keys** (set as environment variables):
  - `AZURE_OPENAI_ENDPOINT` - Azure OpenAI endpoint URL
  - `AZURE_OPENAI_KEY` - Azure OpenAI API key
  - `AZURE_OPENAI_DEPLOYMENT` - Model deployment name (your Azure OpenAI deployment)
  - `MARKETSTACK_API_KEY` - Marketstack API key (free tier: 100 calls/month)
  - `FINNHUB_API_KEY` - Finnhub API key (optional, fallback for Marketstack)

### Installation

```bash
# Clone the repository
git clone https://github.com/mig1980/quantuminvestor.git
cd quantuminvestor

# Install dependencies
pip install -r scripts/requirements.txt

# Set environment variables (PowerShell example)
$env:AZURE_OPENAI_ENDPOINT = "https://your-endpoint.openai.azure.com/"
$env:AZURE_OPENAI_KEY = "your-key-here"
$env:AZURE_OPENAI_DEPLOYMENT = "your-deployment-name"
$env:MARKETSTACK_API_KEY = "your-marketstack-key"
```

### Weekly Automation Workflow

```bash
# Step 1: Run main portfolio automation (price fetch, calculations, AI analysis)
python scripts/portfolio_automation.py --week 8

# Step 2: Enrich candidates with Yahoo Finance fundamentals (FREE, unlimited)
python scripts/yfinance_enrichment.py --week 8

# Step 3: (Optional) Execute rebalancing if AI recommends changes
python scripts/automated_rebalance.py --week 8

# Step 4: Generate newsletter narrative
python scripts/generate_newsletter_narrative.py --week 8

# Step 5: Generate newsletter HTML
python scripts/generate_newsletter_html.py --week 8
```

## 📊 Data Flow

```
1. PRICE FETCHING
   ├─ Marketstack API (primary): 12 weeks EOD data
   └─ Finnhub API (fallback): Current quotes

2. ENRICHMENT
   ├─ Marketstack: Price, momentum (4w/12w), volume
   └─ Yahoo Finance (yfinance): Fundamentals, ratios, growth metrics

3. AI ANALYSIS
   ├─ Prompt A: Validate calculations
   ├─ Prompt B: Research candidates, generate decision
   └─ Prompt D: Assemble final HTML page

4. OUTPUTS
   ├─ Data/W{n}/research_candidates.json    # Enriched candidates
   ├─ Data/W{n}/decision_summary.json       # AI decision (HOLD/REBALANCE)
   ├─ Data/W{n}/master.json                 # Week snapshot
   ├─ Posts/GenAi-Managed-Stocks-Portfolio-Week-{n}.html
   └─ newsletters/week{n}_newsletter.html
```

## 🛠️ Scripts Overview

| Script | Purpose | Dependencies |
|--------|---------|--------------|
| `portfolio_automation.py` | Main orchestrator: fetch prices, calculate metrics, run AI prompts | Azure OpenAI, Marketstack |
| `yfinance_enrichment.py` | Enrich candidates with Yahoo Finance fundamentals | yfinance (FREE) |
| `automated_rebalance.py` | Execute portfolio rebalancing based on AI decision | Finnhub |
| `execute_rebalance.py` | Interactive rebalance helper (manual mode) | Finnhub |
| `generate_newsletter_narrative.py` | Generate newsletter narrative from weekly data | None |
| `generate_newsletter_html.py` | Create email-optimized HTML newsletter | None |
| `pixabay_hero_fetcher.py` | Fetch hero images from Pixabay API | Pixabay API |
| `upload_newsletter_to_blob.py` | Upload newsletter to Azure Blob Storage | Azure Storage |

**Deprecated** (kept for reference, not used):
- `octagon_enrichment.py` - OctagonAI integration (10 credits/month limit)
- `fmp_enrichment.py` - FMP free tier (deprecated Aug 31, 2025)

See [scripts/README.md](scripts/README.md) for detailed documentation.

## 🔑 API Requirements

### Active APIs (Required)

| API | Purpose | Free Tier | Cost | Status |
|-----|---------|-----------|------|--------|
| **Azure OpenAI** | AI analysis, decision-making | No | Pay-per-token | ✅ Required |
| **Marketstack** | Price data, EOD history | 100 calls/month | $0 | ✅ Required |
| **Yahoo Finance** (yfinance) | Fundamentals, ratios, growth | Unlimited | $0 | ✅ Recommended |
| **Finnhub** | Price fallback, rebalancing | 60 calls/min | $0 | ⚠️ Optional |

### Deprecated APIs (Not Used)

| API | Reason | Replacement |
|-----|--------|-------------|
| OctagonAI | 10 credits/month limit | Yahoo Finance |
| FMP Free Tier | Endpoints deprecated Aug 31, 2025 | Yahoo Finance |

## 📈 Portfolio Constraints

The system enforces these constraints:

- **Position Count**: 6-10 holdings
- **Max Position Size**: 20% of portfolio
- **Min Position Value**: $500
- **Rebalancing**: Only when AI signals REBALANCE (vs HOLD)

## 📝 Data Structure

### master.json (Single Source of Truth)

Located in `master data/master.json`:

```json
{
  "week": 7,
  "evaluation_date": "2025-11-29",
  "stocks": [
    {
      "ticker": "NVDA",
      "shares": 145,
      "entry_price": 119.51,
      "entry_date": "2025-10-18",
      "current_price": 138.25,
      "current_value": 20046.25,
      "pct_of_portfolio": 12.86
    }
  ],
  "cash": 7532.47,
  "total_value": 155876.45
}
```

### research_candidates.json

Generated by `portfolio_automation.py`, enriched by `yfinance_enrichment.py`:

```json
{
  "week": 7,
  "candidates": [
    {
      "ticker": "AVGO",
      "momentum_4w": "+12.3%",
      "momentum_12w": "+28.7%",
      "volume_avg": "3.2M",
      "price": "$176.41",
      "sector": "Technology",
      "industry": "Semiconductors",
      "pe_ratio_forward": 65.31,
      "market_cap": 1902924136448,
      "roe_pct": 27.08,
      "revenue_growth_yoy": 16.4
    }
  ]
}
```

## 🔒 Security

- **API Keys**: Never commit API keys. Use environment variables.
- **Git Ignore**: `.env`, `*.log`, `*.key` files excluded
- **Backups**: Automatic timestamped backups in `master data/archive/`

## 📚 Documentation

- [scripts/README.md](scripts/README.md) - Detailed script documentation
- [README/yfinance-guide.md](README/yfinance-guide.md) - Yahoo Finance enrichment guide
- [README/managed-identity-migration.md](README/managed-identity-migration.md) - Azure managed identity setup

**Deprecated Documentation** (kept for reference):
- [README/fmp-migration-guide.md](README/fmp-migration-guide.md) - FMP setup (no longer works)
- [README/fmp-quickstart.md](README/fmp-quickstart.md) - FMP quick start (no longer works)

## 🐛 Troubleshooting

### "ModuleNotFoundError: No module named 'yfinance'"

```bash
pip install yfinance
```

### "AZURE_OPENAI_DEPLOYMENT environment variable not set"

```powershell
$env:AZURE_OPENAI_DEPLOYMENT = "your-deployment-name"
```

### "Marketstack API limit exceeded"

Free tier: 100 calls/month. Each candidate requires ~12 weeks of EOD data = ~1 call per candidate.

### "Yahoo Finance enrichment failed"

yfinance is unofficial and may occasionally timeout. Script is non-blocking - failures won't stop automation.

## 📄 License

MIT License - See [LICENSE](LICENSE) file for details.

## 🤝 Contributing

This is a personal portfolio project, but suggestions and feedback are welcome via GitHub Issues.

## 📧 Contact

- **Blog**: https://quantuminvestor.me
- **GitHub**: https://github.com/mig1980/quantuminvestor
