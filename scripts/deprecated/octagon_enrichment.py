"""
OctagonAI Integration Script
Enriches research_candidates.json with institutional ownership and fundamental data

Follows official API documentation: https://docs.octagonagents.com/guide/rest-api/

Usage:
    python octagon_enrichment.py --week 7

Features:
    - Non-blocking: Always returns success to not break automation pipeline
    - Uses OpenAI SDK per official docs (responses.create endpoint)
    - Queries 3 specialized agents: holdings, stock-data, financials
    - Detailed logging to Data/W{week}/octagon_enrichment.log
    - Graceful degradation if API unavailable
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

try:
    from openai import OpenAI
except ImportError:
    print("❌ ERROR: OpenAI SDK not installed")
    print("Run: pip install openai")
    sys.exit(1)

# Configure paths
SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parent
DATA_DIR = WORKSPACE_ROOT / "Data"

# OctagonAI API Configuration (per https://docs.octagonagents.com/)
OCTAGON_BASE_URL = "https://api-gateway.octagonagents.com/v1"
OCTAGON_API_KEY = os.getenv("OCTAGON_API_KEY")
REQUEST_TIMEOUT = 30.0
DELAY_BETWEEN_AGENTS = 2.0  # Seconds between agent calls for same ticker
DELAY_BETWEEN_TICKERS = 3.0  # Seconds between different tickers


class OctagonEnricher:
    """Enriches candidates using OctagonAI agents via OpenAI SDK"""

    def __init__(self, week_number: int):
        self.week_number = week_number
        self.data_dir = DATA_DIR / f"W{week_number}"
        self.candidates_file = self.data_dir / "research_candidates.json"
        self.log_file = self.data_dir / "octagon_enrichment.log"
        self.candidates: List[Dict] = []
        self.client: Optional[OpenAI] = None
        self.stats = {"total": 0, "enriched": 0, "failed": 0, "fields_added": 0}

        self._setup_logging()
        self._init_client()

    def _setup_logging(self):
        """Configure logging to file and console"""
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.logger = logging.getLogger(f"Octagon_W{self.week_number}")
        self.logger.setLevel(logging.DEBUG)  # Enable debug logging
        self.logger.handlers.clear()

        # File handler
        fh = logging.FileHandler(self.log_file, mode="w", encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

        # Console handler
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))

        self.logger.addHandler(fh)
        self.logger.addHandler(ch)

    def _init_client(self):
        """Initialize OpenAI client for Octagon API"""
        if not OCTAGON_API_KEY:
            self.logger.warning("⚠️  OCTAGON_API_KEY not set - enrichment will be skipped")
            return

        try:
            self.client = OpenAI(api_key=OCTAGON_API_KEY, base_url=OCTAGON_BASE_URL, timeout=REQUEST_TIMEOUT)
            self.logger.info("✅ Octagon client initialized")
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize client: {e}")

    def load_candidates(self) -> bool:
        """Load research_candidates.json"""
        try:
            if not self.candidates_file.exists():
                self.logger.error(f"❌ File not found: {self.candidates_file}")
                return False

            with open(self.candidates_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.candidates = data.get("candidates", [])

            if not self.candidates:
                self.logger.warning("⚠️  No candidates found")
                return False

            self.stats["total"] = len(self.candidates)
            self.logger.info(f"✅ Loaded {len(self.candidates)} candidates")
            return True
        except Exception as e:
            self.logger.error(f"❌ Error loading candidates: {e}")
            return False

    def _query_agent(self, model: str, query: str) -> Optional[str]:
        """Query Octagon agent using responses.create (per official docs)"""
        if not self.client:
            return None

        try:
            response = self.client.responses.create(
                model=model, input=query, instructions="Provide concise, factual data focusing on quantitative metrics."
            )

            if response.output and len(response.output) > 0:
                content = response.output[0].content
                if content and len(content) > 0:
                    text = content[0].text
                    self.logger.debug(f"   Response: {text[:200]}...")  # Log first 200 chars
                    return text

            self.logger.debug(f"   Empty response from {model}")
            return None
        except Exception as e:
            self.logger.warning(f"   ⚠️  {model} error: {str(e)}")
            return None

    def _parse_percentage(self, text: str, keywords: List[str]) -> Optional[float]:
        """Extract percentage from text"""
        for kw in keywords:
            match = re.search(rf"{kw}[:\s]+(\d+\.?\d*)\s*%", text, re.IGNORECASE)
            if match:
                return float(match.group(1))
        return None

    def _parse_number(self, text: str, keywords: List[str]) -> Optional[float]:
        """Extract number from text"""
        for kw in keywords:
            match = re.search(rf"{kw}[:\s]+\$?(\d+\.?\d*)", text, re.IGNORECASE)
            if match:
                return float(match.group(1))
        return None

    def _parse_boolean(self, text: str, keywords: List[str]) -> Optional[bool]:
        """Extract boolean from text"""
        text_lower = text.lower()
        for kw in keywords:
            if f"{kw.lower()} yes" in text_lower:
                return True
            if f"{kw.lower()} no" in text_lower:
                return False
        return None

    def enrich_holdings(self, ticker: str) -> Dict:
        """Query octagon-holdings-agent"""
        query = f"What are the latest institutional holdings for {ticker}? Provide the most recent quarter's data including number of investors holding and changes from previous quarter."
        response = self._query_agent("octagon-holdings-agent", query)
        if not response:
            return {}

        try:
            # Parse JSON response
            holdings_data = json.loads(response)
            if isinstance(holdings_data, list) and len(holdings_data) > 0:
                item = holdings_data[0]
            else:
                item = holdings_data

            data = {}

            # Extract investor counts
            if "investorsHolding" in item:
                data["investors_holding"] = item["investorsHolding"]
                self.logger.info(f"      • Investors holding: {item['investorsHolding']}")

            # Extract holder changes
            if "investorsHoldingChange" in item:
                change = item["investorsHoldingChange"]
                if change > 0:
                    data["holder_changes"] = "increasing"
                    self.logger.info(f"      • Holder activity: increasing (+{change})")
                elif change < 0:
                    data["holder_changes"] = "decreasing"
                    self.logger.info(f"      • Holder activity: decreasing ({change})")

            return data
        except Exception as e:
            self.logger.debug(f"      Parse error: {e}")
            return {}

    def enrich_stock_data(self, ticker: str) -> Dict:
        """Query octagon-stock-data-agent"""
        query = f"Stock market data for {ticker}"
        response = self._query_agent("octagon-stock-data-agent", query)
        if not response:
            return {}

        try:
            # Parse JSON response
            stock_data = json.loads(response)
            if isinstance(stock_data, list) and len(stock_data) > 0:
                item = stock_data[0]
            else:
                item = stock_data

            data = {}

            # Extract current price
            if "price" in item:
                data["current_price"] = round(item["price"], 2)
                self.logger.info(f"      • Current price: ${item['price']:.2f}")

            # Extract volume
            if "volume" in item:
                data["avg_volume"] = item["volume"]

            # Extract price change
            if "changePercentage" in item:
                data["price_change_pct"] = round(item["changePercentage"], 2)

            # Extract 52-week metrics if available
            if "yearHigh" in item:
                data["year_high"] = round(item["yearHigh"], 2)
            if "yearLow" in item:
                data["year_low"] = round(item["yearLow"], 2)

            return data
        except Exception as e:
            self.logger.debug(f"      Parse error: {e}")
            return {}

    def enrich_financials(self, ticker: str) -> Dict:
        """Query octagon-financials-agent"""
        query = f"Financial metrics for {ticker}"
        response = self._query_agent("octagon-financials-agent", query)
        if not response:
            return {}

        try:
            # Parse JSON response
            financials_data = json.loads(response)
            if isinstance(financials_data, list) and len(financials_data) > 0:
                item = financials_data[0]
            else:
                item = financials_data

            data = {}

            # Extract revenue growth
            if "growthRevenue" in item:
                growth_pct = item["growthRevenue"] * 100  # Convert to percentage
                data["revenue_growth_yoy"] = round(growth_pct, 1)
                self.logger.info(f"      • Revenue growth: {growth_pct:+.1f}%")

            # Extract cost growth
            if "growthCostOfRevenue" in item:
                cost_growth = item["growthCostOfRevenue"] * 100
                data["cost_growth_yoy"] = round(cost_growth, 1)

            # Extract other financial metrics if available
            if "growthOperatingIncome" in item:
                op_growth = item["growthOperatingIncome"] * 100
                data["operating_income_growth"] = round(op_growth, 1)

            if "growthNetIncome" in item:
                net_growth = item["growthNetIncome"] * 100
                data["net_income_growth"] = round(net_growth, 1)
                self.logger.info(f"      • Net income growth: {net_growth:+.1f}%")

            return data
        except Exception as e:
            self.logger.debug(f"      Parse error: {e}")
            return {}

    def enrich_candidate(self, candidate: Dict) -> Dict:
        """Enrich single candidate"""
        ticker = candidate.get("ticker", "UNKNOWN")
        self.logger.info(f"\n🔍 Enriching {ticker}...")

        enrichments = {}

        # Query holdings agent
        enrichments.update(self.enrich_holdings(ticker))
        if enrichments:
            time.sleep(DELAY_BETWEEN_AGENTS)

        # Query stock data agent
        enrichments.update(self.enrich_stock_data(ticker))
        if enrichments:
            time.sleep(DELAY_BETWEEN_AGENTS)

        # Query financials agent
        enrichments.update(self.enrich_financials(ticker))

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

            data["candidates"] = enriched

            if "enrichment" not in data:
                data["enrichment"] = {}

            data["enrichment"]["octagon_ai"] = {
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

    def run(self) -> bool:
        """Execute enrichment workflow"""
        self.logger.info("=" * 60)
        self.logger.info(f"OCTAGON AI ENRICHMENT - WEEK {self.week_number}")
        self.logger.info("=" * 60)

        if not OCTAGON_API_KEY or not self.client:
            self.logger.warning("⚠️  Enrichment skipped - automation continues")
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

                # Delay between tickers (except after last one)
                if i < len(self.candidates):
                    self.logger.debug(f"   Waiting {DELAY_BETWEEN_TICKERS}s before next ticker...")
                    time.sleep(DELAY_BETWEEN_TICKERS)
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
    parser = argparse.ArgumentParser(description="Enrich candidates with Octagon AI")
    parser.add_argument("--week", type=int, required=True, help="Week number (e.g., 7)")
    args = parser.parse_args()

    enricher = OctagonEnricher(args.week)
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
