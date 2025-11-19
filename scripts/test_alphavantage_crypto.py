#!/usr/bin/env python3
"""
Test script for Alpha Vantage Crypto API - Fetch BTC and ETH prices
"""
import os
import sys
import time
import requests
from datetime import datetime

def test_alphavantage_crypto_price(symbol, api_key, to_currency='USD'):
    """Fetch crypto price from Alpha Vantage API and display result."""
    print(f"\n{'='*60}")
    print(f"Testing Alpha Vantage Crypto API for: {symbol}")
    print(f"{'='*60}")
    
    if not api_key:
        print("❌ FAILED: ALPHAVANTAGE_API_KEY environment variable not set")
        print("   Set it with: $env:ALPHAVANTAGE_API_KEY='your-key-here'")
        return False
    
    url = 'https://www.alphavantage.co/query'
    params = {
        'function': 'CURRENCY_EXCHANGE_RATE',
        'from_currency': symbol,
        'to_currency': to_currency,
        'apikey': api_key
    }
    
    try:
        print(f"📡 Requesting: {url}")
        print(f"   Function: CURRENCY_EXCHANGE_RATE")
        print(f"   From Currency: {symbol}")
        print(f"   To Currency: {to_currency}")
        print(f"   API Key: {api_key[:8]}..." if len(api_key) > 8 else "   API Key: (too short)")
        
        response = requests.get(url, params=params, timeout=10)
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
        
        # Alpha Vantage crypto returns "Realtime Currency Exchange Rate"
        if 'Realtime Currency Exchange Rate' in data:
            rate_data = data['Realtime Currency Exchange Rate']
            
            # Extract key fields
            from_code = rate_data.get('1. From_Currency Code', 'N/A')
            from_name = rate_data.get('2. From_Currency Name', 'N/A')
            to_code = rate_data.get('3. To_Currency Code', 'N/A')
            to_name = rate_data.get('4. To_Currency Name', 'N/A')
            exchange_rate = rate_data.get('5. Exchange Rate')
            last_refreshed = rate_data.get('6. Last Refreshed', 'N/A')
            timezone = rate_data.get('7. Time Zone', 'N/A')
            bid_price = rate_data.get('8. Bid Price')
            ask_price = rate_data.get('9. Ask Price')
            
            print(f"\n✅ SUCCESS: Crypto price retrieved for {symbol}")
            print(f"   From: {from_name} ({from_code})")
            print(f"   To: {to_name} ({to_code})")
            print(f"   Exchange Rate: ${float(exchange_rate):,.2f}" if exchange_rate else "   Exchange Rate: N/A")
            print(f"   Bid Price: ${float(bid_price):,.2f}" if bid_price else "   Bid Price: N/A")
            print(f"   Ask Price: ${float(ask_price):,.2f}" if ask_price else "   Ask Price: N/A")
            print(f"   Last Refreshed: {last_refreshed}")
            print(f"   Timezone: {timezone}")
            
            if bid_price and ask_price:
                try:
                    spread = float(ask_price) - float(bid_price)
                    spread_pct = (spread / float(bid_price)) * 100
                    print(f"   Bid-Ask Spread: ${spread:,.2f} ({spread_pct:.3f}%)")
                except:
                    pass
            
            return True
        else:
            print(f"\n❌ FAILED: No valid crypto data returned")
            print(f"   Reason: Response contains no 'Realtime Currency Exchange Rate'")
            print(f"   This could mean:")
            print(f"     - Invalid cryptocurrency symbol")
            print(f"     - API key invalid or expired")
            print(f"     - Service temporarily unavailable")
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
    print("ALPHA VANTAGE CRYPTO API TEST SCRIPT")
    print("="*60)
    
    # Get API key from environment
    api_key = os.getenv('ALPHAVANTAGE_API_KEY')
    
    if not api_key:
        print("\n❌ ERROR: ALPHAVANTAGE_API_KEY environment variable not set")
        print("\nTo set it in PowerShell:")
        print('   cd scripts')
        print('   $env:ALPHAVANTAGE_API_KEY="your-api-key-here"')
        print('   python test_alphavantage_crypto.py')
        print("\nGet a free API key at: https://www.alphavantage.co/support/#api-key")
        sys.exit(1)
    
    print(f"\n✓ ALPHAVANTAGE_API_KEY: {api_key}")
    print(f"✓ Free tier: 5 requests/minute, 500 requests/day")
    print(f"✓ Rate limit: 12 seconds between calls")
    
    # Test two crypto symbols
    test_symbols = ['BTC', 'ETH']
    
    results = []
    for i, symbol in enumerate(test_symbols, 1):
        success = test_alphavantage_crypto_price(symbol, api_key, to_currency='USD')
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
        print("\n🎉 All tests passed! Alpha Vantage Crypto API is working correctly.")
    else:
        print("\n⚠️ Some tests failed. Check error messages above.")
    
    print("="*60 + "\n")


if __name__ == '__main__':
    main()
