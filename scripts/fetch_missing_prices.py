"""
Fetch missing stock prices from Alpha Vantage API for W1 and W3
"""
import json
import requests
import time
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Paths
REPO_ROOT = Path(__file__).parent.parent
MASTER_DATA_FILE = REPO_ROOT / "master data" / "master.json"

def fetch_price_for_date(ticker, target_date, api_key):
    """Fetch stock price for a specific date from Alpha Vantage"""
    url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={ticker}&apikey={api_key}&outputsize=full"
    
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        result = response.json()
        
        if "Time Series (Daily)" in result:
            time_series = result["Time Series (Daily)"]
            
            # Try exact date first
            if target_date in time_series:
                return float(time_series[target_date]["4. close"])
            
            # If not found, find nearest previous trading day (up to 4 days back)
            date_obj = datetime.strptime(target_date, '%Y-%m-%d')
            for offset in range(1, 5):
                alt_date = (date_obj - timedelta(days=offset)).strftime('%Y-%m-%d')
                if alt_date in time_series:
                    print(f"    Note: Using {alt_date} (nearest trading day for {target_date})")
                    return float(time_series[alt_date]["4. close"])
            
            print(f"    ERROR: No data found near {target_date}")
            return None
        
        elif "Note" in result:
            print(f"    API LIMIT: {result['Note']}")
            return None
        elif "Error Message" in result:
            print(f"    ERROR: {result['Error Message']}")
            return None
        else:
            print(f"    ERROR: Unexpected response format")
            return None
            
    except Exception as e:
        print(f"    ERROR: {str(e)}")
        return None

def main():
    # Check for API key
    if len(sys.argv) < 2:
        print("Usage: python fetch_missing_prices.py <ALPHA_VANTAGE_API_KEY>")
        print("\nGet a free API key at: https://www.alphavantage.co/support/#api-key")
        sys.exit(1)
    
    api_key = sys.argv[1]
    
    # Load master data
    print("Loading master data...")
    with open(MASTER_DATA_FILE, 'r') as f:
        data = json.load(f)
    
    # Missing dates
    missing_dates = ['2025-10-16', '2025-10-30']
    tickers = [stock['ticker'] for stock in data['stocks']]
    
    print(f"\nFetching prices for {len(tickers)} stocks")
    print(f"Target dates: {', '.join(missing_dates)}")
    print(f"Tickers: {', '.join(tickers)}")
    print("\nNote: Free API tier allows 5 calls/minute. This will take ~2 minutes.\n")
    print("="*70)
    
    # Fetch prices
    fetched_prices = {ticker: {} for ticker in tickers}
    call_count = 0
    
    for ticker in tickers:
        call_count += 1
        print(f"\n[{call_count}/{len(tickers)}] Fetching {ticker}...")
        
        # Fetch all data for this ticker once
        url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={ticker}&apikey={api_key}&outputsize=full"
        
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            result = response.json()
            
            if "Time Series (Daily)" in result:
                time_series = result["Time Series (Daily)"]
                
                for target_date in missing_dates:
                    # Try exact date
                    if target_date in time_series:
                        price = float(time_series[target_date]["4. close"])
                        fetched_prices[ticker][target_date] = price
                        print(f"  ✓ {target_date}: ${price:.2f}")
                    else:
                        # Find nearest trading day
                        date_obj = datetime.strptime(target_date, '%Y-%m-%d')
                        found = False
                        for offset in range(1, 5):
                            alt_date = (date_obj - timedelta(days=offset)).strftime('%Y-%m-%d')
                            if alt_date in time_series:
                                price = float(time_series[alt_date]["4. close"])
                                fetched_prices[ticker][target_date] = price
                                print(f"  ✓ {target_date}: ${price:.2f} (from {alt_date})")
                                found = True
                                break
                        if not found:
                            print(f"  ✗ {target_date}: NOT FOUND")
            
            elif "Note" in result:
                print(f"  ⚠ API LIMIT REACHED: {result['Note']}")
                print("\n  Please wait 1 minute and try again, or upgrade your API key.")
                sys.exit(1)
            else:
                print(f"  ✗ ERROR: {result.get('Error Message', 'Unknown error')}")
        
        except Exception as e:
            print(f"  ✗ ERROR: {str(e)}")
        
        # Rate limiting: 5 calls/min for free tier = 12 seconds between calls
        if call_count < len(tickers):
            print("  Waiting 12 seconds (API rate limit)...")
            time.sleep(12)
    
    print("\n" + "="*70)
    print("FETCH COMPLETE - SUMMARY")
    print("="*70)
    
    # Summary
    success_count = 0
    for ticker in tickers:
        prices = fetched_prices[ticker]
        if len(prices) == len(missing_dates):
            success_count += 1
            print(f"✓ {ticker:6s} - Complete")
        else:
            print(f"✗ {ticker:6s} - Missing {len(missing_dates) - len(prices)} dates")
    
    print(f"\nSuccess: {success_count}/{len(tickers)} stocks have complete data")
    
    if success_count == 0:
        print("\nNo data fetched. Exiting without modifying master.json")
        sys.exit(1)
    
    # Update master data
    print("\n" + "="*70)
    print("UPDATING MASTER.JSON")
    print("="*70)
    
    for stock in data['stocks']:
        ticker = stock['ticker']
        if ticker in fetched_prices:
            for date, price in fetched_prices[ticker].items():
                stock['prices'][date] = price
                print(f"  Added {ticker} {date}: ${price:.2f}")
    
    # Sort prices by date for each stock
    for stock in data['stocks']:
        stock['prices'] = dict(sorted(stock['prices'].items()))
    
    # Backup original file
    backup_file = MASTER_DATA_FILE.parent / f"master_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(backup_file, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"\n✓ Backup created: {backup_file.name}")
    
    # Save updated master data
    with open(MASTER_DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"✓ Updated: {MASTER_DATA_FILE.name}")
    
    print("\n" + "="*70)
    print("SUCCESS! Master data updated with missing prices.")
    print("="*70)
    print("\nNext steps:")
    print("  1. Refresh the heatmap page to see W1 and W3 data")
    print("  2. If backup is not needed, you can delete it from 'master data/' folder")

if __name__ == "__main__":
    main()
