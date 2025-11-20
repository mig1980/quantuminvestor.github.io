#!/usr/bin/env python3
"""
Test script for Alpha Vantage API - Fetch stock prices for 2 tickers
"""
import os
import sys
import time
import requests
from datetime import datetime

def test_alphavantage_stock_price(symbol, api_key):
    """Fetch stock price from Alpha Vantage API and display result."""
    print(f"\n{'='*60}")
    print(f"Testing Alpha Vantage API for: {symbol}")
    print(f"{'='*60}")
    
    if not api_key:
        print("❌ FAILED: ALPHAVANTAGE_API_KEY environment variable not set")
        print("   Set it with: $env:ALPHAVANTAGE_API_KEY='your-key-here'")
        return False
    
    url = 'https://www.alphavantage.co/query'
    params = {
        'function': 'GLOBAL_QUOTE',
        'symbol': symbol,
        'apikey': api_key
    }
    
    try:
        print(f"📡 Requesting: {url}")
        print(f"   Function: GLOBAL_QUOTE")
        print(f"   Symbol: {symbol}")
        print(f"   API Key: {api_key[:8]}..." if len(api_key) > 8 else "   API Key: (too short)")
        
        response = requests.get(url, params=params, timeout=60)
        print(f"   HTTP Status: {response.status_code}")
        
        response.raise_for_status()
        data = response.json()
        
        print(f"\n📊 Raw API Response:")
        print(f"   {data}")
        
        # Check for rate limit message
        if 'Note' in data:
            print(f"\n❌ FAILED: Rate limit exceeded")
            print(f"   Message: {data['Note']}")
            print(f"   Alpha Vantage free tier: 5 requests per minute, 500 per day")
            return False
        
        # Check for error message
        if 'Error Message' in data:
            print(f"\n❌ FAILED: API Error")
            print(f"   Message: {data['Error Message']}")
            return False
        
        # Alpha Vantage returns Global Quote with various fields
        if 'Global Quote' in data and data['Global Quote']:
            quote = data['Global Quote']
            
            # Extract key fields (Alpha Vantage uses numeric keys)
            symbol_ret = quote.get('01. symbol', 'N/A')
            price = quote.get('05. price')
            volume = quote.get('06. volume')
            latest_day = quote.get('07. latest trading day', 'N/A')
            prev_close = quote.get('08. previous close')
            change = quote.get('09. change')
            change_pct = quote.get('10. change percent', '').replace('%', '')
            
            print(f"\n✅ SUCCESS: Price retrieved for {symbol}")
            print(f"   Symbol: {symbol_ret}")
            print(f"   Current Price: ${float(price):.2f}" if price else "   Current Price: N/A")
            print(f"   Latest Trading Day: {latest_day}")
            print(f"   Previous Close: ${float(prev_close):.2f}" if prev_close else "   Previous Close: N/A")
            print(f"   Change: ${float(change):.2f}" if change else "   Change: N/A")
            print(f"   Change %: {change_pct}%" if change_pct else "   Change %: N/A")
            print(f"   Volume: {int(float(volume)):,}" if volume else "   Volume: N/A")
            
            return True
        else:
            print(f"\n❌ FAILED: No valid price data returned")
            print(f"   Reason: Response contains no 'Global Quote' or is empty")
            print(f"   This could mean:")
            print(f"     - Invalid ticker symbol")
            print(f"     - Market closed and no data available")
            print(f"     - API key invalid or expired")
            return False
            
    except requests.exceptions.HTTPError as e:
        print(f"\n❌ FAILED: HTTP Error")
        print(f"   Status Code: {response.status_code}")
        print(f"   Reason: {e}")
        if response.status_code == 401:
            print(f"   → Invalid API key")
        elif response.status_code == 429:
            print(f"   → Rate limit exceeded")
        return False
        
    except requests.exceptions.Timeout:
        print(f"\n❌ FAILED: Request timeout")
        print(f"   Reason: Server did not respond within 60 seconds")
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
    print("ALPHA VANTAGE API TEST SCRIPT")
    print("="*60)
    
    # Get API key from environment
    api_key = os.getenv('ALPHAVANTAGE_API_KEY')
    
    if not api_key:
        print("\n❌ ERROR: ALPHAVANTAGE_API_KEY environment variable not set")
        print("\nTo set it in PowerShell:")
        print('   cd scripts')
        print('   $env:ALPHAVANTAGE_API_KEY="your-api-key-here"')
        print('   python test_alphavantage.py')
        print("\nGet a free API key at: https://www.alphavantage.co/support/#api-key")
        sys.exit(1)
    
    print(f"\n✓ ALPHAVANTAGE_API_KEY: {api_key}")
    print(f"✓ Free tier: 5 requests/minute, 500 requests/day")
    print(f"✓ Rate limit: 12 seconds between calls")
    
    # Test two stock symbols
    test_symbols = ['AAPL', 'MSFT']
    
    results = []
    for i, symbol in enumerate(test_symbols, 1):
        success = test_alphavantage_stock_price(symbol, api_key)
        results.append((symbol, success))
        
        # Rate limiting: 5 req/min = 12 seconds between calls
        if i < len(test_symbols):
            wait_time = 12
            print(f"\n⏳ Waiting {wait_time} seconds (rate limit: 5 req/min)...")
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
        print("\n🎉 All tests passed! Alpha Vantage API is working correctly.")
    else:
        print("\n⚠️ Some tests failed. Check error messages above.")
    
    print("="*60 + "\n")


if __name__ == '__main__':
    main()
