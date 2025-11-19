#!/usr/bin/env python3
"""
Test script for Marketstack API - Fetch stock prices for 2 tickers
"""
import os
import sys
import time
import requests
from datetime import datetime

def test_marketstack_stock_price(symbol, api_key):
    """Fetch stock price from Marketstack API and display result."""
    print(f"\n{'='*60}")
    print(f"Testing Marketstack API for: {symbol}")
    print(f"{'='*60}")
    
    if not api_key:
        print("❌ FAILED: MARKETSTACK_API_KEY environment variable not set")
        print("   Set it with: $env:MARKETSTACK_API_KEY='your-key-here'")
        return False
    
    url = 'http://api.marketstack.com/v1/eod/latest'
    params = {
        'access_key': api_key,
        'symbols': symbol
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
        
        # Marketstack returns data array with date, close, open, high, low, volume
        if 'data' in data and data['data'] and len(data['data']) > 0:
            quote = data['data'][0]
            close_price = quote.get('close')
            date_str = quote.get('date', 'N/A')
            open_price = quote.get('open')
            high_price = quote.get('high')
            low_price = quote.get('low')
            volume = quote.get('volume')
            
            # Parse date for better display
            try:
                if date_str != 'N/A':
                    date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    date_display = date_obj.strftime('%Y-%m-%d')
                else:
                    date_display = 'N/A'
            except:
                date_display = date_str
            
            print(f"\n✅ SUCCESS: Price retrieved for {symbol}")
            print(f"   Close Price: ${close_price:.2f}" if close_price else "   Close Price: N/A")
            print(f"   Date: {date_display}")
            print(f"   Open: ${open_price:.2f}" if open_price else "   Open: N/A")
            print(f"   High: ${high_price:.2f}" if high_price else "   High: N/A")
            print(f"   Low: ${low_price:.2f}" if low_price else "   Low: N/A")
            print(f"   Volume: {volume:,}" if volume else "   Volume: N/A")
            
            if open_price and close_price and open_price > 0:
                change_pct = ((close_price - open_price) / open_price) * 100
                print(f"   Daily Change: {change_pct:+.2f}%")
            
            return True
        else:
            print(f"\n❌ FAILED: No valid price data returned")
            print(f"   Reason: Response contains no 'data' array or is empty")
            print(f"   This could mean:")
            print(f"     - Invalid ticker symbol")
            print(f"     - Symbol not supported by Marketstack")
            print(f"     - No recent EOD (End of Day) data available")
            return False
            
    except requests.exceptions.HTTPError as e:
        print(f"\n❌ FAILED: HTTP Error")
        print(f"   Status Code: {response.status_code}")
        print(f"   Reason: {e}")
        if response.status_code == 401:
            print(f"   → Invalid API key or subscription required")
        elif response.status_code == 429:
            print(f"   → Rate limit exceeded")
        elif response.status_code == 403:
            print(f"   → Access denied (check API plan/permissions)")
        try:
            error_data = response.json()
            if 'error' in error_data:
                print(f"   → API Error: {error_data['error'].get('message', 'Unknown')}")
        except:
            pass
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
    print("MARKETSTACK API TEST SCRIPT")
    print("="*60)
    
    # Get API key from environment
    api_key = os.getenv('MARKETSTACK_API_KEY')
    
    if not api_key:
        print("\n❌ ERROR: MARKETSTACK_API_KEY environment variable not set")
        print("\nTo set it in PowerShell:")
        print('   cd scripts')
        print('   $env:MARKETSTACK_API_KEY="your-api-key-here"')
        print('   python test_marketstack.py')
        print("\nGet a free API key at: https://marketstack.com/signup/free")
        sys.exit(1)
    
    print(f"\n✓ MARKETSTACK_API_KEY: {api_key}")
    print(f"✓ Free tier: 100 requests/month")
    print(f"✓ Note: Marketstack provides EOD (End of Day) data only on free tier")
    
    # Test two stock symbols
    test_symbols = ['AAPL', 'MSFT']
    
    results = []
    for i, symbol in enumerate(test_symbols, 1):
        success = test_marketstack_stock_price(symbol, api_key)
        results.append((symbol, success))
        
        # Rate limiting: wait 2 seconds between calls (conservative)
        if i < len(test_symbols):
            wait_time = 2
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
        print("\n🎉 All tests passed! Marketstack API is working correctly.")
    else:
        print("\n⚠️ Some tests failed. Check error messages above.")
    
    print("="*60 + "\n")


if __name__ == '__main__':
    main()
