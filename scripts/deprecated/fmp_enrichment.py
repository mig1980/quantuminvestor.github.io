"""
Financial Modeling Prep (FMP) Free Tier Enrichment Script
Complements Marketstack by adding fundamental data not available in Marketstack

API Documentation: https://site.financialmodelingprep.com/developer/docs

FREE TIER ENDPOINTS USED (250 calls/day limit):
- Company Profile: Sector, industry, description, CEO, employees, country
- Financial Ratios: P/E, P/B, ROE, ROA, debt/equity, current ratio
- Income Statement Growth: Revenue growth, net income growth, EPS growth
- Key Metrics: Market cap verification, EPS, dividend yield

NOT USED (requires paid tiers):
- Institutional Holdings (Ultimate $99/mo)
- Intraday data (Premium+)

Usage:
    python fmp_enrichment.py --week 7

Features:
    - Adds fundamental data that Marketstack doesn't provide
    - Marketstack provides: Price, volume, momentum (already in pipeline)
    - FMP adds: Company info, financial ratios, growth metrics
    - Non-blocking: Always returns success to not break automation
    - Detailed logging to Data/W{week}/fmp_enrichment.log
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests

# Configure paths
SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parent
DATA_DIR = WORKSPACE_ROOT / "Data"

# FMP API Configuration
# Updated to use /stable/ endpoint (v3 is legacy as of Aug 31, 2025)
FMP_BASE_URL = "https://financialmodelingprep.com/stable"
FMP_API_KEY = os.getenv("FMP_API_KEY")
REQUEST_TIMEOUT = 30.0
DELAY_BETWEEN_CALLS = 0.5  # Rate limiting: 250 calls/day = ~0.35s minimum


class FMPEnricher:
    """Enriches candidates using Financial Modeling Prep API"""

    def __init__(self, week_number: int):
        self.week_number = week_number
        self.data_dir = DATA_DIR / f"W{week_number}"
        self.candidates_file = self.data_dir / "research_candidates.json"
        self.decision_file = self.data_dir / "decision_summary.json"
        self.log_file = self.data_dir / "fmp_enrichment.log"
        self.candidates: List[Dict] = []
        self.stats = {"total": 0, "enriched": 0, "failed": 0, "fields_added": 0}

        self._setup_logging()

    def _setup_logging(self):
        """Configure logging to file and console"""
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.logger = logging.getLogger(f"FMP_W{self.week_number}")
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()

        # File handler
        fh = logging.FileHandler(self.log_file, mode="w", encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

        # Console handler
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))

        self.logger.addHandler(fh)
        self.logger.addHandler(ch)

        if not FMP_API_KEY:
            self.logger.warning("⚠️  FMP_API_KEY not set - enrichment will be skipped")
        else:
            self.logger.info("✅ FMP API key configured")

    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make HTTP request to FMP API"""
        if not FMP_API_KEY:
            return None

        url = f"{FMP_BASE_URL}/{endpoint}"
        params = params or {}
        params["apikey"] = FMP_API_KEY

        try:
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()

            # Handle error responses
            if isinstance(data, dict) and "Error Message" in data:
                self.logger.warning(f"   ⚠️  API error: {data['Error Message']}")
                return None

            return data
        except requests.exceptions.RequestException as e:
            self.logger.warning(f"   ⚠️  Request error: {str(e)}")
            return None
        except json.JSONDecodeError as e:
            self.logger.warning(f"   ⚠️  JSON decode error: {str(e)}")
            return None

    def load_candidates(self) -> bool:
        """Load research_candidates.json"""
        try:
            if not self.candidates_file.exists():
                self.logger.error(f"❌ File not found: {self.candidates_file}")
                return False

            with open(self.candidates_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Handle both formats: {"candidates": [...]} or [...]
                if isinstance(data, dict):
                    self.candidates = data.get("candidates", [])
                else:
                    self.candidates = data

            if not self.candidates:
                self.logger.warning("⚠️  No candidates found")
                return False

            self.stats["total"] = len(self.candidates)
            self.logger.info(f"✅ Loaded {len(self.candidates)} candidates")
            return True
        except Exception as e:
            self.logger.error(f"❌ Error loading candidates: {e}")
            return False

    def enrich_company_profile(self, ticker: str) -> Dict:
        """Fetch company profile (FREE tier)

        Endpoint: /profile/{ticker}
        Returns: Sector, industry, description, CEO, employees, website, country
        """
        self.logger.debug(f"   Querying company profile...")

        data = self._make_request(f"profile/{ticker}")

        if not data or not isinstance(data, list) or len(data) == 0:
            self.logger.debug(f"      No company profile available")
            return {}

        profile = data[0]
        enrichments = {}

        # Company basics
        if "companyName" in profile:
            enrichments["company_name"] = profile["companyName"]

        if "sector" in profile:
            enrichments["sector"] = profile["sector"]
            self.logger.info(f"      • Sector: {profile['sector']}")

        if "industry" in profile:
            enrichments["industry"] = profile["industry"]
            self.logger.info(f"      • Industry: {profile['industry']}")

        if "country" in profile:
            enrichments["country"] = profile["country"]

        if "ceo" in profile:
            enrichments["ceo"] = profile["ceo"]

        if "fullTimeEmployees" in profile:
            enrichments["employees"] = profile["fullTimeEmployees"]

        if "website" in profile:
            enrichments["website"] = profile["website"]

        # Description (truncate if too long)
        if "description" in profile:
            desc = profile["description"]
            enrichments["description"] = desc[:200] + "..." if len(desc) > 200 else desc

        time.sleep(DELAY_BETWEEN_CALLS)
        return enrichments

    def enrich_financial_ratios(self, ticker: str) -> Dict:
        """Fetch financial ratios (FREE tier)

        Endpoint: /ratios/{ticker}
        Returns: P/E, P/B, ROE, ROA, debt/equity, current ratio, etc.
        """
        self.logger.debug(f"   Querying financial ratios...")

        data = self._make_request(f"ratios/{ticker}", {"limit": 1})

        if not data or not isinstance(data, list) or len(data) == 0:
            self.logger.debug(f"      No financial ratios available")
            return {}

        ratios = data[0]
        enrichments = {}

        # Valuation ratios
        if "priceEarningsRatio" in ratios and ratios["priceEarningsRatio"]:
            pe = ratios["priceEarningsRatio"]
            enrichments["pe_ratio"] = round(pe, 2)
            self.logger.info(f"      • P/E Ratio: {pe:.2f}")

        if "priceToBookRatio" in ratios and ratios["priceToBookRatio"]:
            pb = ratios["priceToBookRatio"]
            enrichments["pb_ratio"] = round(pb, 2)

        if "priceToSalesRatio" in ratios and ratios["priceToSalesRatio"]:
            ps = ratios["priceToSalesRatio"]
            enrichments["ps_ratio"] = round(ps, 2)

        # Profitability ratios
        if "returnOnEquity" in ratios and ratios["returnOnEquity"]:
            roe = ratios["returnOnEquity"] * 100
            enrichments["roe_pct"] = round(roe, 2)
            self.logger.info(f"      • ROE: {roe:.2f}%")

        if "returnOnAssets" in ratios and ratios["returnOnAssets"]:
            roa = ratios["returnOnAssets"] * 100
            enrichments["roa_pct"] = round(roa, 2)

        if "netProfitMargin" in ratios and ratios["netProfitMargin"]:
            npm = ratios["netProfitMargin"] * 100
            enrichments["profit_margin_pct"] = round(npm, 2)

        # Leverage ratios
        if "debtEquityRatio" in ratios and ratios["debtEquityRatio"]:
            de = ratios["debtEquityRatio"]
            enrichments["debt_equity_ratio"] = round(de, 2)

        # Liquidity ratios
        if "currentRatio" in ratios and ratios["currentRatio"]:
            cr = ratios["currentRatio"]
            enrichments["current_ratio"] = round(cr, 2)

        time.sleep(DELAY_BETWEEN_CALLS)
        return enrichments

    def enrich_financial_growth(self, ticker: str) -> Dict:
        """Fetch financial growth metrics

        Endpoint: /income-statement-growth/{ticker}
        Available: All tiers including free
        """
        self.logger.debug(f"   Querying financial growth...")

        # Get annual growth data
        data = self._make_request(f"income-statement-growth/{ticker}", {"period": "annual", "limit": 1})

        if not data or not isinstance(data, list) or len(data) == 0:
            self.logger.debug(f"      No financial growth data available")
            return {}

        growth = data[0]
        enrichments = {}

        # Extract revenue growth
        if "growthRevenue" in growth:
            revenue_growth_pct = growth["growthRevenue"] * 100
            enrichments["revenue_growth_yoy"] = round(revenue_growth_pct, 1)
            self.logger.info(f"      • Revenue growth: {revenue_growth_pct:+.1f}%")

        # Extract net income growth
        if "growthNetIncome" in growth:
            net_income_growth_pct = growth["growthNetIncome"] * 100
            enrichments["net_income_growth_yoy"] = round(net_income_growth_pct, 1)
            self.logger.info(f"      • Net income growth: {net_income_growth_pct:+.1f}%")

        # Extract operating income growth
        if "growthOperatingIncome" in growth:
            op_growth_pct = growth["growthOperatingIncome"] * 100
            enrichments["operating_income_growth_yoy"] = round(op_growth_pct, 1)

        # Extract EPS growth
        if "growthEPS" in growth:
            eps_growth_pct = growth["growthEPS"] * 100
            enrichments["eps_growth_yoy"] = round(eps_growth_pct, 1)

        time.sleep(DELAY_BETWEEN_CALLS)
        return enrichments

    def enrich_candidate(self, candidate: Dict) -> Dict:
        """Enrich single candidate with FREE tier data only

        Fetches 3 endpoints per candidate (all FREE tier):
        1. Company profile - sector, industry, CEO, employees
        2. Financial ratios - P/E, ROE, debt/equity, etc.
        3. Financial growth - revenue/income/EPS growth rates

        Marketstack already provides: price, volume, momentum
        """
        ticker = candidate.get("ticker", "UNKNOWN")
        self.logger.info(f"\n🔍 Enriching {ticker}...")

        enrichments = {}

        # Fetch company profile (FREE tier)
        enrichments.update(self.enrich_company_profile(ticker))

        # Fetch financial ratios (FREE tier)
        enrichments.update(self.enrich_financial_ratios(ticker))

        # Fetch financial growth (FREE tier)
        enrichments.update(self.enrich_financial_growth(ticker))

        if enrichments:
            self.stats["enriched"] += 1
            self.stats["fields_added"] += len(enrichments)
            self.logger.info(f"✅ Added {len(enrichments)} field(s)")
        else:
            self.stats["failed"] += 1
            self.logger.warning(f"⚠️  No data obtained")

        return {**candidate, **enrichments}

    def save_candidates(self, enriched: List[Dict]) -> bool:
        """Save enriched candidates"""
        try:
            with open(self.candidates_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Handle both formats
            if isinstance(data, dict):
                data["candidates"] = enriched
            else:
                data = {"candidates": enriched}

            if "enrichment" not in data:
                data["enrichment"] = {}

            data["enrichment"]["fmp"] = {
                "timestamp": datetime.now().isoformat(),
                "week": self.week_number,
                **self.stats,
            }

            tmp = self.candidates_file.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            tmp.replace(self.candidates_file)
            self.logger.info(f"\n✅ Saved to {self.candidates_file.name}")
            return True
        except Exception as e:
            self.logger.error(f"❌ Save error: {e}")
            return False

    def should_run_enrichment(self) -> bool:
        """Always run enrichment - provides fundamental data Marketstack doesn't have

        Unlike OctagonAI (credit-constrained), FMP free tier has 250 calls/day.
        With 3 candidates × 3 endpoints = 9 calls/week, we use only 3.6% of daily limit.
        No need to skip on HOLD weeks.
        """
        if self.candidates_file.exists():
            try:
                with open(self.candidates_file, "r", encoding="utf-8") as f:
                    candidates_data = json.load(f)
                if isinstance(candidates_data, dict):
                    candidate_count = len(candidates_data.get("candidates", []))
                else:
                    candidate_count = len(candidates_data)
                expected_calls = candidate_count * 3  # 3 FREE tier endpoints per candidate
                self.logger.info(f"📊 {candidate_count} candidate(s) × 3 endpoints = {expected_calls} API calls")
                self.logger.info(f"   Free tier: {expected_calls}/250 daily limit ({expected_calls/250*100:.1f}%)")
            except Exception:  # nosec B110
                pass  # Non-critical logging, safe to ignore

        return True

    def run(self) -> bool:
        """Execute enrichment workflow"""
        self.logger.info("=" * 60)
        self.logger.info(f"FMP FREE TIER ENRICHMENT - WEEK {self.week_number}")
        self.logger.info("=" * 60)
        self.logger.info("📌 Complements Marketstack (price/volume/momentum)")
        self.logger.info("📌 Adds fundamentals: company info, ratios, growth")
        self.logger.info("=" * 60)

        if not FMP_API_KEY:
            self.logger.warning("⚠️  FMP_API_KEY not set - enrichment skipped")
            self.logger.warning("   Set environment variable: FMP_API_KEY=your_key")
            self.logger.warning("   Get FREE key: https://site.financialmodelingprep.com/")
            self.logger.info("=" * 60)
            return True

        # Check if we should run (always yes for free tier)
        if not self.should_run_enrichment():
            return True

        if not self.load_candidates():
            self.logger.warning("⚠️  Skipping enrichment")
            return True

        enriched = []
        for i, candidate in enumerate(self.candidates, 1):
            ticker = candidate.get("ticker", f"Unknown_{i}")
            self.logger.info(f"\n[{i}/{len(self.candidates)}] {ticker}")

            try:
                enriched.append(self.enrich_candidate(candidate))
            except Exception as e:
                self.logger.error(f"❌ Error: {e}")
                enriched.append(candidate)
                self.stats["failed"] += 1

        self.save_candidates(enriched)

        self.logger.info("\n" + "=" * 60)
        self.logger.info("SUMMARY")
        self.logger.info("=" * 60)
        self.logger.info(f"Total: {self.stats['total']}")
        self.logger.info(f"Enriched: {self.stats['enriched']}")
        self.logger.info(f"Failed: {self.stats['failed']}")
        self.logger.info(f"Fields added: {self.stats['fields_added']}")
        self.logger.info(f"\nLog: {self.log_file}")
        self.logger.info("=" * 60)

        return True


def main():
    parser = argparse.ArgumentParser(
        description="Enrich candidates with FMP free tier fundamentals (complements Marketstack price/volume data)"
    )
    parser.add_argument("--week", type=int, required=True, help="Week number (e.g., 7)")
    args = parser.parse_args()

    enricher = FMPEnricher(args.week)
    enricher.run()
    sys.exit(0)  # Always success to not break automation


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n❌ Cancelled")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(0)  # Non-fatal
