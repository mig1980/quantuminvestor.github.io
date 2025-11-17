import json
import requests
import sys

API_KEY = "YLZ547W5E25PI43O"
tickers = ['PLTR', 'NEM', 'STX', 'GEV', 'WDC', 'GE', 'CVS', 'NRG', 'HWM', 'RCL']
target_dates = ['2025-10-16', '2025-10-30']

# Quick fetch without rate limiting (run multiple times if needed)
start_idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
end_idx = int(sys.argv[2]) if len(sys.argv) > 2 else len(tickers)

print(f"Fetching tickers {start_idx} to {end_idx-1}\n")

for ticker in tickers[start_idx:end_idx]:
    url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={ticker}&apikey={API_KEY}&outputsize=compact"
    response = requests.get(url, timeout=15)
    result = response.json()
    
    if "Time Series (Daily)" in result:
        time_series = result["Time Series (Daily)"]
        print(f'    "{ticker}": {{', end="")
        for date in target_dates:
            if date in time_series:
                price = float(time_series[date]["4. close"])
                print(f' "{date}": {price},', end="")
        print(" },")
    else:
        print(f'{ticker}: ERROR - {result.get("Note", result.get("Error Message", "Unknown"))}')
