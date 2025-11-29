"""
Rebalance Execution Script
Helps execute portfolio rebalancing by calculating share quantities and updating master.json

Usage:
    python execute_rebalance.py

Process:
    1. Prompts for positions to exit and dollar amounts
    2. Prompts for positions to buy and dollar allocations
    3. Fetches current market prices from Finnhub
    4. Calculates exact share quantities
    5. Updates master.json with new holdings structure
    6. Creates backup before updating
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

# Configure paths
SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parent
MASTER_JSON_PATH = WORKSPACE_ROOT / "master data" / "master.json"
ARCHIVE_DIR = WORKSPACE_ROOT / "master data" / "archive"

# Finnhub API configuration
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
FINNHUB_BASE_URL = "https://finnhub.io/api/v1"


def load_master_json() -> dict:
    """Load current master.json"""
    if not MASTER_JSON_PATH.exists():
        print(f"❌ Error: master.json not found at {MASTER_JSON_PATH}")
        sys.exit(1)

    with open(MASTER_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def backup_master_json():
    """Create timestamped backup of master.json"""
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = ARCHIVE_DIR / f"master-before-rebalance-{timestamp}.json"

    with open(MASTER_JSON_PATH, "r", encoding="utf-8") as f:
        data = f.read()

    with open(backup_path, "w", encoding="utf-8") as f:
        f.write(data)

    print(f"✅ Backup created: {backup_path.name}")
    return backup_path


def fetch_current_price(ticker: str) -> Optional[float]:
    """Fetch current price from Finnhub API"""
    if not FINNHUB_API_KEY:
        print("⚠️  Warning: FINNHUB_API_KEY not set in environment variables")
        return None

    try:
        url = f"{FINNHUB_BASE_URL}/quote"
        params = {"symbol": ticker, "token": FINNHUB_API_KEY}
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        current_price = data.get("c")  # Current price
        if current_price and current_price > 0:
            return round(current_price, 2)
        else:
            print(f"⚠️  Warning: Invalid price for {ticker}")
            return None
    except Exception as e:
        print(f"⚠️  Error fetching price for {ticker}: {str(e)}")
        return None


def get_stock_full_name(ticker: str) -> str:
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
                return result.get("description", ticker)

        return ticker
    except Exception as e:
        print(f"⚠️  Could not fetch name for {ticker}: {str(e)}")
        return ticker


def prompt_exits(current_stocks: List[dict]) -> List[Dict[str, Any]]:
    """Prompt user for positions to exit"""
    print("\n" + "=" * 60)
    print("STEP 1: POSITIONS TO EXIT")
    print("=" * 60)
    print("\nCurrent holdings:")
    for i, holding in enumerate(current_stocks, 1):
        print(f"  {i}. {holding['ticker']:6s} - {holding['name'][:40]:40s} (${holding['current_value']:,.0f})")

    print("\nEnter tickers to exit (comma-separated) or 'none':")
    exits_input = input(">> ").strip().upper()

    if exits_input.lower() == "none":
        return []

    exit_tickers = [t.strip() for t in exits_input.split(",")]
    exits = []

    for ticker in exit_tickers:
        # Find stock in current holdings
        stock: Optional[dict] = next((s for s in current_stocks if s["ticker"] == ticker), None)
        if not stock:
            print(f"⚠️  Warning: {ticker} not found in current holdings - skipping")
            continue

        print(f"\n{ticker} - Current value: ${stock['current_value']:,.2f}")
        exit_price_input = input(f"  Exit price for {ticker} (press Enter to fetch current): ").strip()

        exit_price: float
        if not exit_price_input:
            fetched_price = fetch_current_price(ticker)
            if fetched_price:
                exit_price = fetched_price
                print(f"  Fetched price: ${exit_price:.2f}")
            else:
                print(f"  ❌ Could not fetch price for {ticker}")
                continue
        else:
            exit_price = float(exit_price_input)

        exit_value = stock["shares"] * exit_price

        exits.append({"ticker": ticker, "shares": stock["shares"], "exit_price": exit_price, "exit_value": exit_value})

        print(f"  Exit: {stock['shares']:.2f} shares @ ${exit_price:.2f} = ${exit_value:,.2f}")

    total_cash = sum(e["exit_value"] for e in exits)
    print(f"\n💰 Total cash from exits: ${total_cash:,.2f}")

    return exits


def prompt_entries(available_cash: float) -> List[Dict[str, Any]]:
    """Prompt user for new positions to buy"""
    print("\n" + "=" * 60)
    print("STEP 2: NEW POSITIONS TO BUY")
    print("=" * 60)
    print(f"\nAvailable capital: ${available_cash:,.2f}")

    print("\nEnter tickers to buy (comma-separated):")
    entries_input = input(">> ").strip().upper()

    entry_tickers = [t.strip() for t in entries_input.split(",")]
    entries = []
    total_allocated: float = 0.0

    for ticker in entry_tickers:
        print(f"\n{ticker}")

        # Fetch current price
        entry_price_input = input(f"  Entry price for {ticker} (press Enter to fetch current): ").strip()

        entry_price: float
        if not entry_price_input:
            fetched_price = fetch_current_price(ticker)
            if fetched_price:
                entry_price = fetched_price
                print(f"  Fetched price: ${entry_price:.2f}")
            else:
                print(f"  ❌ Could not fetch price for {ticker} - skipping")
                continue
        else:
            entry_price = float(entry_price_input)

        # Get allocation amount
        remaining = available_cash - total_allocated
        print(f"  Remaining capital: ${remaining:,.2f}")
        allocation_input = input(f"  Dollar allocation for {ticker}: $").strip()

        if not allocation_input:
            print(f"  ⚠️  Skipping {ticker} - no allocation specified")
            continue

        allocation: float = float(allocation_input)

        if allocation > remaining:
            print(f"  ⚠️  Warning: Allocation ${allocation:,.2f} exceeds remaining ${remaining:,.2f}")
            proceed = input("  Continue anyway? (y/n): ").strip().lower()
            if proceed != "y":
                continue

        shares = allocation / entry_price

        # Fetch company name
        name = get_stock_full_name(ticker)

        entries.append(
            {
                "ticker": ticker,
                "name": name,
                "shares": round(shares, 2),
                "entry_price": entry_price,
                "entry_value": allocation,
            }
        )

        total_allocated += allocation

        print(f"  Buy: {shares:.2f} shares @ ${entry_price:.2f} = ${allocation:,.2f}")

    print(f"\n💵 Total capital deployed: ${total_allocated:,.2f}")

    if total_allocated < available_cash:
        unused = available_cash - total_allocated
        print(f"💰 Unused capital (will remain as cash): ${unused:,.2f}")

    return entries


def update_master_json(master: dict, exits: List[dict], entries: List[dict]) -> dict:
    """Update master.json with rebalance execution"""

    # Get current date for new entries
    current_date = master["meta"]["current_date"]

    # Remove exited positions
    exit_tickers = [e["ticker"] for e in exits]
    master["stocks"] = [s for s in master["stocks"] if s["ticker"] not in exit_tickers]

    print(f"\n🗑️  Removed {len(exits)} position(s): {', '.join(exit_tickers)}")

    # Add new positions
    for entry in entries:
        new_stock = {
            "ticker": entry["ticker"],
            "name": entry["name"],
            "shares": entry["shares"],
            "prices": {current_date: entry["entry_price"]},
            "current_value": round(entry["shares"] * entry["entry_price"], 2),
            "weekly_pct": 0.0,  # First week, no change yet
            "total_pct": 0.0,  # Just entered, 0% return
        }
        master["stocks"].append(new_stock)
        print(f"➕ Added {entry['ticker']} - {entry['shares']:.2f} shares @ ${entry['entry_price']:.2f}")

    # Recalculate portfolio totals
    total_value = sum(s["current_value"] for s in master["stocks"])

    # Preserve weekly/total performance (these don't change with rebalance)
    master["portfolio_totals"]["current_value"] = round(total_value, 2)

    print(f"\n📊 Updated portfolio value: ${total_value:,.2f}")
    print(f"📊 Position count: {len(master['stocks'])}")

    return master


def save_master_json(master: dict):
    """Save updated master.json"""
    with open(MASTER_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(master, f, indent=2)

    print(f"\n✅ master.json updated successfully!")


def display_summary(exits: List[dict], entries: List[dict]):
    """Display execution summary"""
    print("\n" + "=" * 60)
    print("REBALANCE EXECUTION SUMMARY")
    print("=" * 60)

    if exits:
        print("\n🔴 EXITS:")
        for exit in exits:
            print(
                f"  • {exit['ticker']}: Sold {exit['shares']:.2f} shares @ ${exit['exit_price']:.2f} = ${exit['exit_value']:,.2f}"
            )
        total_exit = sum(e["exit_value"] for e in exits)
        print(f"  💰 Total proceeds: ${total_exit:,.2f}")

    if entries:
        print("\n🟢 ENTRIES:")
        for entry in entries:
            print(
                f"  • {entry['ticker']}: Bought {entry['shares']:.2f} shares @ ${entry['entry_price']:.2f} = ${entry['entry_value']:,.2f}"
            )
        total_entry = sum(e["entry_value"] for e in entries)
        print(f"  💵 Total deployed: ${total_entry:,.2f}")

    if exits and entries:
        net_cash = sum(e["exit_value"] for e in exits) - sum(e["entry_value"] for e in entries)
        if net_cash > 0:
            print(f"\n💰 Net cash generated: ${net_cash:,.2f}")
        elif net_cash < 0:
            print(f"\n💸 Net cash used: ${abs(net_cash):,.2f}")
        else:
            print(f"\n⚖️  Fully deployed (no excess cash)")


def main():
    """Main execution flow"""
    print("=" * 60)
    print("PORTFOLIO REBALANCE EXECUTION")
    print("=" * 60)

    # Check API key
    if not FINNHUB_API_KEY:
        print("\n⚠️  WARNING: FINNHUB_API_KEY not found in environment variables")
        print("You will need to enter prices manually.")
        proceed = input("\nContinue? (y/n): ").strip().lower()
        if proceed != "y":
            print("Exiting...")
            sys.exit(0)

    # Load current master.json
    print("\n📂 Loading master.json...")
    master = load_master_json()
    print(f"✅ Loaded: {len(master['stocks'])} current positions")
    print(f"   Portfolio value: ${master['portfolio_totals']['current_value']:,.2f}")

    # Backup
    backup_master_json()

    # Get exits
    exits = prompt_exits(master["stocks"])

    if not exits:
        print("\n⚠️  No exits specified")
        available_cash = 0
    else:
        available_cash = sum(e["exit_value"] for e in exits)

    # Get entries
    if available_cash > 0 or not exits:
        if available_cash == 0:
            print("\n💵 No cash from exits. Enter allocation amount manually if buying new positions.")
        entries = prompt_entries(available_cash)
    else:
        entries = []

    if not exits and not entries:
        print("\n⚠️  No rebalance actions specified. Exiting without changes.")
        sys.exit(0)

    # Display summary
    display_summary(exits, entries)

    # Confirm
    print("\n" + "=" * 60)
    confirm = input("Proceed with master.json update? (yes/no): ").strip().lower()

    if confirm != "yes":
        print("❌ Update cancelled. No changes made.")
        sys.exit(0)

    # Update master.json
    print("\n📝 Updating master.json...")
    updated_master = update_master_json(master, exits, entries)

    # Save
    save_master_json(updated_master)

    print("\n" + "=" * 60)
    print("✅ REBALANCE COMPLETE")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Verify master.json structure")
    print("  2. Run portfolio_automation.py for next week's data fetch")
    print("  3. New positions will be tracked starting next week")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
