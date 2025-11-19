#!/usr/bin/env python3
"""
Test script for Finnhub API - Fetch stock prices for 2 tickers
"""
import os
import sys
import time
import requests
from datetime import datetime

def test_finnhub_stock_price(symbol, api_key):
    """Fetch stock price from Finnhub API and display result."""
    print(f"\n{'='*60}")
    print(f"Testing Finnhub API for: {symbol}")
    print(f"{'='*60}")
    
    if not api_key:
        print("❌ FAILED: FINNHUB_API_KEY environment variable not set")
        print("   Set it with: $env:FINNHUB_API_KEY='your-key-here'")
        return False
    
    url = 'https://finnhub.io/api/v1/quote'
    params = {
        'symbol': symbol,
        'token': api_key
    }
    
    try:
        print(f"📡 Requesting: {url}")
        print(f"   Symbol: {symbol}")
        print(f"   API Key: {api_key[:8]}..." if len(api_key) > 8 else "   API Key: (too short)")
        
        response = requests.get(url, params=params, timeout=10)
        print(f"   HTTP Status: {response.status_code}")
        
        response.raise_for_status()
        data = response.json()
        
        print(f"\n📊 Raw API Response:")
        print(f"   {data}")
        
        # Finnhub returns: c (current), pc (previous close), t (timestamp), o (open), h (high), l (low)
        if 'c' in data and data.get('c') not in (None, 0):
            current_price = data.get('c')
            prev_close = data.get('pc')
            timestamp = data.get('t')
            
            # Convert timestamp to readable date
            try:
                date_str = datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S UTC') if timestamp else 'N/A'
            except:
                date_str = 'N/A'
            
            print(f"\n✅ SUCCESS: Price retrieved for {symbol}")
            print(f"   Current Price: ${current_price:.2f}")
            print(f"   Previous Close: ${prev_close:.2f}" if prev_close else "   Previous Close: N/A")
            print(f"   Timestamp: {date_str}")
            
            if prev_close and prev_close > 0:
                change_pct = ((current_price - prev_close) / prev_close) * 100
                print(f"   Change: {change_pct:+.2f}%")
            
            return True
        else:
            print(f"\n❌ FAILED: No valid price data returned")
            print(f"   Reason: Response contains no 'c' field or price is 0/null")
            print(f"   This could mean:")
            print(f"     - Invalid ticker symbol")
            print(f"     - Market closed and no data available")
            print(f"     - Symbol not supported by Finnhub")
            return False
            
    except requests.exceptions.HTTPError as e:
        print(f"\n❌ FAILED: HTTP Error")
        print(f"   Status Code: {response.status_code}")
        print(f"   Reason: {e}")
        if response.status_code == 401:
            print(f"   → Invalid API key")
        elif response.status_code == 429:
            print(f"   → Rate limit exceeded (5 requests/minute)")
        return False
        
    except requests.exceptions.Timeout:
        print(f"\n❌ FAILED: Request timeout")
        print(f"   Reason: Server did not respond within 10 seconds")
        return False
        
    except requests.exceptions.ConnectionError as e:
        print(f"\n❌ FAILED: Connection error")
        print(f"   Reason: {e}")
        print(f"   Check your internet connection")
        return False
        
    except Exception as e:
        print(f"\n❌ FAILED: Unexpected error")
        print(f"   Error type: {type(e).__name__}")
        print(f"   Message: {e}")
        return False


def main():
    print("\n" + "="*60)
    print("FINNHUB API TEST SCRIPT")
    print("="*60)
    
    # Get API key from environment
    api_key = os.getenv('FINNHUB_API_KEY')
    
    if not api_key:
        print("\n❌ ERROR: FINNHUB_API_KEY environment variable not set")
        print("\nTo set it in PowerShell:")
        print('   cd scripts')
        print('   $env:FINNHUB_API_KEY="your-api-key-here"')
        print('   python test_finnhub.py')
        print("\nGet a free API key at: https://finnhub.io/register")
        sys.exit(1)
    
    print(f"\n✓ FINNHUB_API_KEY: {api_key}")
    print(f"✓ Rate limit: 5 requests/minute (12 seconds between calls)")
    
    # Test two stock symbols
    test_symbols = ['AAPL', 'MSFT']
    
    results = []
    for i, symbol in enumerate(test_symbols, 1):
        success = test_finnhub_stock_price(symbol, api_key)
        results.append((symbol, success))
        
        # Rate limiting: wait 12 seconds between calls (5 req/min)
        if i < len(test_symbols):
            wait_time = 12
            print(f"\n⏳ Waiting {wait_time} seconds (rate limit)...")
            time.sleep(wait_time)
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    success_count = sum(1 for _, success in results if success)
    total_count = len(results)
    
    for symbol, success in results:
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"  {symbol}: {status}")
    
    print(f"\nTotal: {success_count}/{total_count} successful")
    
    if success_count == total_count:
        print("\n🎉 All tests passed! Finnhub API is working correctly.")
    else:
        print("\n⚠️ Some tests failed. Check error messages above.")
    
    print("="*60 + "\n")


if __name__ == '__main__':
    main()
