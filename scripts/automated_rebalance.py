"""
Automated Portfolio Rebalancing Script
Executes portfolio rebalancing based on decision_summary.json from Prompt B

Usage:
    python automated_rebalance.py --week 7 [--dry-run]

Process:
    1. Loads decision_summary.json from Data/W{week}/
    2. Validates decision structure and trade instructions
    3. Fetches current market prices from Finnhub
    4. Applies trades: exit, buy, trim, add_to_existing
    5. Validates portfolio constraints (6-10 positions, 20% cap, $500 min)
    6. Creates backup and updates master.json (unless --dry-run)
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", handlers=[logging.StreamHandler(sys.stdout)]
)

# Configure paths
SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parent
MASTER_JSON_PATH = WORKSPACE_ROOT / "master data" / "master.json"
DATA_DIR = WORKSPACE_ROOT / "Data"
ARCHIVE_DIR = WORKSPACE_ROOT / "master data" / "archive"

# Finnhub API configuration
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
FINNHUB_BASE_URL = "https://finnhub.io/api/v1"

# Portfolio constraints
MIN_POSITIONS = 6
MAX_POSITIONS = 10
MAX_POSITION_PCT = 0.20  # 20% cap
MIN_POSITION_VALUE = 500  # $500 minimum


class PortfolioRebalancer:
    """Handles automated portfolio rebalancing based on AI decisions"""

    def __init__(self, week_number: int, dry_run: bool = False):
        self.week_number = week_number
        self.dry_run = dry_run
        self.master_data: Optional[Dict] = None
        self.decision_data: Optional[Dict] = None
        self.current_date: Optional[str] = None

    def load_data(self) -> bool:
        """Load master.json and decision_summary.json"""
        try:
            # Load master.json
            if not MASTER_JSON_PATH.exists():
                logging.error(f"❌ master.json not found at {MASTER_JSON_PATH}")
                return False

            with open(MASTER_JSON_PATH, "r", encoding="utf-8") as f:
                self.master_data = json.load(f)
                self.current_date = self.master_data["meta"]["current_date"]
                logging.info(f"✅ Loaded master.json - {len(self.master_data['stocks'])} positions")

            # Load decision_summary.json
            decision_path = DATA_DIR / f"W{self.week_number}" / "decision_summary.json"
            if not decision_path.exists():
                logging.warning(f"⚠️  decision_summary.json not found at {decision_path}")
                logging.warning("This is expected if Prompt B produced a HOLD decision")
                return False

            with open(decision_path, "r", encoding="utf-8") as f:
                self.decision_data = json.load(f)
                logging.info(f"✅ Loaded decision_summary.json for Week {self.week_number}")

            return True

        except Exception as e:
            logging.error(f"❌ Error loading data: {str(e)}")
            return False

    def validate_decision(self) -> bool:
        """Validate decision_summary.json structure and content"""
        try:
            if not self.decision_data:
                return False

            # Check decision type
            decision = self.decision_data.get("decision", "").upper()
            if decision == "HOLD":
                logging.info("✅ Decision is HOLD - no rebalancing needed")
                return False

            if decision != "REBALANCE":
                logging.error(f"❌ Invalid decision type: {decision}")
                return False

            # Check for trades_executed
            if "trades_executed" not in self.decision_data:
                logging.error("❌ Missing 'trades_executed' in decision_summary.json")
                return False

            trades = self.decision_data["trades_executed"]
            if not trades or len(trades) == 0:
                logging.warning("⚠️  No trades specified in REBALANCE decision")
                return False

            logging.info(f"✅ Valid REBALANCE decision with {len(trades)} trade(s)")

            # Log trades for visibility
            for i, trade in enumerate(trades, 1):
                action = trade.get("action", "unknown")
                ticker = trade.get("ticker", "N/A")
                value = trade.get("value", 0)
                logging.info(f"   {i}. {action.upper()}: {ticker} (${value:,.0f})")

            return True

        except Exception as e:
            logging.error(f"❌ Error validating decision: {str(e)}")
            return False

    def fetch_current_price(self, ticker: str) -> Optional[float]:
        """Fetch current price from Finnhub API"""
        if not FINNHUB_API_KEY:
            logging.error("❌ FINNHUB_API_KEY not set in environment variables")
            return None

        try:
            url = f"{FINNHUB_BASE_URL}/quote"
            params = {"symbol": ticker, "token": FINNHUB_API_KEY}
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            current_price = data.get("c")  # Current price
            if current_price and current_price > 0:
                logging.info(f"   Fetched price for {ticker}: ${current_price:.2f}")
                return round(current_price, 2)
            else:
                logging.warning(f"⚠️  Invalid price for {ticker}")
                return None

        except Exception as e:
            logging.error(f"❌ Error fetching price for {ticker}: {str(e)}")
            return None

    def fetch_company_name(self, ticker: str) -> str:
        """Fetch company name from Finnhub API"""
        if not FINNHUB_API_KEY:
            return ticker

        try:
            url = f"{FINNHUB_BASE_URL}/search"
            params = {"q": ticker, "token": FINNHUB_API_KEY}
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            results = data.get("result", [])
            for result in results:
                if result.get("symbol") == ticker:
                    name = result.get("description", ticker)
                    logging.info(f"   Fetched name for {ticker}: {name}")
                    return name

            return ticker

        except Exception as e:
            logging.warning(f"⚠️  Could not fetch name for {ticker}: {str(e)}")
            return ticker

    def execute_trade_exit(self, trade: Dict, stocks: List[Dict]) -> List[Dict]:
        """Execute exit trade - remove stock from portfolio"""
        ticker = trade["ticker"]

        # Find and remove stock
        original_count = len(stocks)
        stocks = [s for s in stocks if s["ticker"] != ticker]

        if len(stocks) < original_count:
            logging.info(f"✅ EXIT: Removed {ticker} from portfolio")
        else:
            logging.warning(f"⚠️  EXIT: {ticker} not found in portfolio")

        return stocks

    def execute_trade_buy(self, trade: Dict, stocks: List[Dict]) -> List[Dict]:
        """Execute buy trade - add new stock to portfolio"""
        ticker = trade["ticker"]
        value = trade["value"]

        # Check if stock already exists
        if any(s["ticker"] == ticker for s in stocks):
            logging.warning(f"⚠️  BUY: {ticker} already exists in portfolio - skipping")
            return stocks

        # Fetch current price
        if "price" in trade and trade["price"] > 0:
            price = trade["price"]
            logging.info(f"   Using price from decision: ${price:.2f}")
        else:
            price = self.fetch_current_price(ticker)
            if not price:
                logging.error(f"❌ Could not determine price for {ticker} - skipping BUY")
                return stocks

        # Calculate shares
        shares = round(value / price, 2)

        # Fetch company name
        name = trade.get("name", "")
        if not name:
            name = self.fetch_company_name(ticker)

        # Create new stock entry
        new_stock = {
            "ticker": ticker,
            "name": name,
            "shares": shares,
            "prices": {self.current_date: price},
            "current_value": round(shares * price, 2),
            "weekly_pct": 0.0,  # First week, no change yet
            "total_pct": 0.0,  # Just entered, 0% return
        }

        stocks.append(new_stock)
        logging.info(f"✅ BUY: Added {ticker} - {shares:.2f} shares @ ${price:.2f} = ${value:,.2f}")

        return stocks

    def execute_trade_trim(self, trade: Dict, stocks: List[Dict]) -> List[Dict]:
        """Execute trim trade - reduce shares in existing position"""
        ticker = trade["ticker"]
        trim_value = trade["value"]  # Dollar amount to remove

        # Find stock
        stock = next((s for s in stocks if s["ticker"] == ticker), None)
        if not stock:
            logging.warning(f"⚠️  TRIM: {ticker} not found in portfolio - skipping")
            return stocks

        # Get current price
        current_prices = stock.get("prices", {})
        if self.current_date in current_prices:
            price = current_prices[self.current_date]
        else:
            price = self.fetch_current_price(ticker)
            if not price:
                logging.error(f"❌ Could not determine price for {ticker} - skipping TRIM")
                return stocks

        # Calculate shares to remove
        shares_to_remove = round(trim_value / price, 2)
        new_shares = round(stock["shares"] - shares_to_remove, 2)

        if new_shares < 0:
            logging.warning(f"⚠️  TRIM: Would result in negative shares for {ticker} - skipping")
            return stocks

        old_shares = stock["shares"]
        old_value = stock["current_value"]

        stock["shares"] = new_shares
        stock["current_value"] = round(new_shares * price, 2)

        logging.info(
            f"✅ TRIM: {ticker} - {old_shares:.2f} → {new_shares:.2f} shares (${old_value:,.0f} → ${stock['current_value']:,.0f})"
        )

        return stocks

    def execute_trade_add_to_existing(self, trade: Dict, stocks: List[Dict]) -> List[Dict]:
        """Execute add_to_existing trade - increase shares in existing position"""
        ticker = trade["ticker"]
        add_value = trade["value"]  # Dollar amount to add

        # Find stock
        stock = next((s for s in stocks if s["ticker"] == ticker), None)
        if not stock:
            logging.warning(f"⚠️  ADD_TO_EXISTING: {ticker} not found - converting to BUY")
            return self.execute_trade_buy(trade, stocks)

        # Get current price
        if "price" in trade and trade["price"] > 0:
            price = trade["price"]
        else:
            current_prices = stock.get("prices", {})
            if self.current_date in current_prices:
                price = current_prices[self.current_date]
            else:
                price = self.fetch_current_price(ticker)
                if not price:
                    logging.error(f"❌ Could not determine price for {ticker} - skipping ADD")
                    return stocks

        # Calculate shares to add
        shares_to_add = round(add_value / price, 2)
        new_shares = round(stock["shares"] + shares_to_add, 2)

        old_shares = stock["shares"]
        old_value = stock["current_value"]

        stock["shares"] = new_shares
        stock["current_value"] = round(new_shares * price, 2)

        # Update price history
        if "prices" not in stock:
            stock["prices"] = {}
        stock["prices"][self.current_date] = price

        logging.info(
            f"✅ ADD: {ticker} - {old_shares:.2f} → {new_shares:.2f} shares (${old_value:,.0f} → ${stock['current_value']:,.0f})"
        )

        return stocks

    def execute_rebalance(self) -> bool:
        """Execute all trades from decision_summary.json"""
        try:
            if not self.decision_data or not self.master_data:
                return False

            trades = self.decision_data["trades_executed"]
            stocks = self.master_data["stocks"].copy()

            logging.info(f"\n{'='*60}")
            logging.info(f"EXECUTING {len(trades)} TRADE(S)")
            logging.info(f"{'='*60}\n")

            # Execute each trade
            for i, trade in enumerate(trades, 1):
                action = trade.get("action", "").lower()
                ticker = trade.get("ticker", "N/A")

                logging.info(f"Trade {i}/{len(trades)}: {action.upper()} {ticker}")

                if action == "exit":
                    stocks = self.execute_trade_exit(trade, stocks)
                elif action == "buy":
                    stocks = self.execute_trade_buy(trade, stocks)
                elif action == "trim":
                    stocks = self.execute_trade_trim(trade, stocks)
                elif action == "add_to_existing":
                    stocks = self.execute_trade_add_to_existing(trade, stocks)
                else:
                    logging.warning(f"⚠️  Unknown action: {action} - skipping")

                logging.info("")  # Blank line between trades

            # Update master data
            self.master_data["stocks"] = stocks

            # Recalculate portfolio totals
            total_value = sum(s["current_value"] for s in stocks)
            self.master_data["portfolio_totals"]["current_value"] = round(total_value, 2)

            logging.info(f"{'='*60}")
            logging.info(f"REBALANCE SUMMARY")
            logging.info(f"{'='*60}")
            logging.info(f"Position count: {len(stocks)}")
            logging.info(f"Portfolio value: ${total_value:,.2f}")

            return True

        except Exception as e:
            logging.error(f"❌ Error executing rebalance: {str(e)}")
            return False

    def validate_portfolio(self) -> bool:
        """Validate portfolio meets all constraints"""
        try:
            if not self.master_data:
                return False

            stocks = self.master_data["stocks"]
            position_count = len(stocks)
            total_value = sum(s["current_value"] for s in stocks)

            logging.info(f"\n{'='*60}")
            logging.info(f"PORTFOLIO VALIDATION")
            logging.info(f"{'='*60}\n")

            # Check position count
            if position_count < MIN_POSITIONS or position_count > MAX_POSITIONS:
                logging.error(f"❌ Position count {position_count} outside range [{MIN_POSITIONS}, {MAX_POSITIONS}]")
                return False
            logging.info(f"✅ Position count: {position_count} (within {MIN_POSITIONS}-{MAX_POSITIONS} range)")

            # Check position sizes
            violations = []
            for stock in stocks:
                position_pct = stock["current_value"] / total_value if total_value > 0 else 0

                # Check 20% cap
                if position_pct > MAX_POSITION_PCT:
                    violations.append(f"{stock['ticker']}: {position_pct*100:.1f}% (exceeds 20% cap)")

                # Check $500 minimum
                if stock["current_value"] < MIN_POSITION_VALUE:
                    violations.append(f"{stock['ticker']}: ${stock['current_value']:.0f} (below $500 minimum)")

            if violations:
                logging.error(f"❌ Portfolio constraint violations:")
                for v in violations:
                    logging.error(f"   - {v}")
                return False

            logging.info(f"✅ All positions within size constraints")
            logging.info(f"✅ Portfolio validation passed\n")

            return True

        except Exception as e:
            logging.error(f"❌ Error validating portfolio: {str(e)}")
            return False

    def create_backup(self) -> Optional[Path]:
        """Create backup of master.json before modification"""
        try:
            ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = ARCHIVE_DIR / f"master-before-week{self.week_number}-rebalance-{timestamp}.json"

            with open(MASTER_JSON_PATH, "r", encoding="utf-8") as f:
                data = f.read()

            with open(backup_path, "w", encoding="utf-8") as f:
                f.write(data)

            logging.info(f"✅ Backup created: {backup_path.name}")
            return backup_path

        except Exception as e:
            logging.error(f"❌ Error creating backup: {str(e)}")
            return None

    def save_master_json(self) -> bool:
        """Save updated master.json"""
        try:
            if self.dry_run:
                logging.info("🔍 DRY RUN - Would save master.json (not saving)")
                return True

            # Atomic write with .tmp suffix
            tmp_path = MASTER_JSON_PATH.with_suffix(".json.tmp")

            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.master_data, f, indent=2)

            # Replace original
            tmp_path.replace(MASTER_JSON_PATH)

            logging.info(f"✅ master.json updated successfully")
            return True

        except Exception as e:
            logging.error(f"❌ Error saving master.json: {str(e)}")
            return False

    def run(self) -> bool:
        """Execute full rebalancing workflow"""
        logging.info(f"\n{'='*60}")
        logging.info(f"AUTOMATED PORTFOLIO REBALANCING - WEEK {self.week_number}")
        if self.dry_run:
            logging.info(f"MODE: DRY RUN (no changes will be saved)")
        logging.info(f"{'='*60}\n")

        # Step 1: Load data
        if not self.load_data():
            logging.warning("⚠️  Rebalancing not needed or data not available")
            return False

        # Step 2: Validate decision
        if not self.validate_decision():
            logging.info("✅ No rebalancing required")
            return True  # Not an error - just HOLD decision

        # Step 3: Create backup
        if not self.dry_run:
            backup = self.create_backup()
            if not backup:
                logging.error("❌ Failed to create backup - aborting")
                return False

        # Step 4: Execute trades
        if not self.execute_rebalance():
            logging.error("❌ Trade execution failed")
            return False

        # Step 5: Validate portfolio
        if not self.validate_portfolio():
            logging.error("❌ Portfolio validation failed - NOT saving changes")
            return False

        # Step 6: Save changes
        if not self.save_master_json():
            logging.error("❌ Failed to save master.json")
            return False

        logging.info(f"\n{'='*60}")
        logging.info(f"✅ REBALANCING COMPLETE")
        logging.info(f"{'='*60}\n")

        return True


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Automated portfolio rebalancing based on decision_summary.json")
    parser.add_argument("--week", type=int, required=True, help="Week number to process (e.g., 7)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate rebalancing without saving changes")

    args = parser.parse_args()

    # Validate API key
    if not FINNHUB_API_KEY:
        logging.error("❌ FINNHUB_API_KEY not set in environment variables")
        logging.error("Set with: $env:FINNHUB_API_KEY='your_key_here'")
        sys.exit(1)

    # Execute rebalancing
    rebalancer = PortfolioRebalancer(args.week, args.dry_run)
    success = rebalancer.run()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("\n\n❌ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logging.error(f"\n❌ Unexpected error: {str(e)}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
