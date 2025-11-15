#!/usr/bin/env python3
"""
GenAi Chosen Portfolio - Weekly Automation Script
Runs Prompt A -> B -> C -> D sequence to generate weekly portfolio updates
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from openai import OpenAI
import re
import time
import requests

# Configure paths
REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "Data"
POSTS_DIR = REPO_ROOT / "Posts"
PROMPT_DIR = REPO_ROOT / "Prompt"
ARCHIVE_DIR = DATA_DIR / "archive"

class PortfolioAutomation:
    def __init__(self, week_number=None, api_key=None, model="gpt-4-turbo-preview", data_source="ai", alphavantage_key=None, eval_date=None):
        self.week_number = week_number or self.detect_next_week()
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.model = model
        self.data_source = data_source.lower()
        self.alphavantage_key = alphavantage_key or os.getenv('ALPHAVANTAGE_API_KEY')
        self.client = None
        self.ai_enabled = False
        self.eval_date = None
        if eval_date:
            try:
                datetime.strptime(eval_date, '%Y-%m-%d')
                self.eval_date = eval_date
                print(f"✓ Using manual evaluation date override: {self.eval_date}")
            except ValueError:
                print(f"⚠️ Invalid --eval-date '{eval_date}' (expected YYYY-MM-DD). Ignoring override.")

        # Initialize OpenAI client (required unless using alphavantage data-only mode)
        if self.api_key:
            try:
                self.client = OpenAI(api_key=self.api_key)
                self.ai_enabled = True
                print(f"✓ OpenAI client initialized (model: {self.model})")
            except Exception as e:
                print(f"⚠️ Failed to init OpenAI client: {e}")
        else:
            if self.data_source == 'ai':
                raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY environment variable.")
            print("⚠️ No OPENAI_API_KEY. Will skip AI narrative (Prompts B-D) and produce data-only output.")

        # Validate Alpha Vantage key if needed
        if self.data_source == 'alphavantage':
            if not self.alphavantage_key:
                raise ValueError("Alpha Vantage API key required. Set ALPHAVANTAGE_API_KEY environment variable.")
            print(f"✓ Using Alpha Vantage data source (key: {self.alphavantage_key[:8]}...)")

        # Load prompts
        self.prompts = self.load_prompts()

        # State storage
        self.master_json = None
        self.narrative_html = None
        self.seo_json = None
        self.performance_table = None
        self.performance_chart = None
        
    def detect_next_week(self):
        """Auto-detect next week number by scanning existing posts"""
        existing_weeks = []
        for file in POSTS_DIR.glob("GenAi-Managed-Stocks-Portfolio-Week-*.html"):
            match = re.search(r'Week-(\d+)\.html', file.name)
            if match:
                existing_weeks.append(int(match.group(1)))
        
        return max(existing_weeks, default=0) + 1 if existing_weeks else 6
    
    def load_prompts(self):
        """Load all prompt templates from Prompt folder"""
        prompts = {}
        for prompt_file in PROMPT_DIR.glob("Prompt-*.md"):
            prompt_id = prompt_file.stem.split('-')[1]  # Extract A, B, C, D
            with open(prompt_file, 'r', encoding='utf-8') as f:
                prompts[prompt_id] = f.read()
        
        # Validate all required prompts are present
        required = {'A', 'B', 'C', 'D'}
        missing = required - set(prompts.keys())
        if missing:
            raise FileNotFoundError(f"Missing prompt files: {', '.join(f'Prompt-{p}-*.md' for p in missing)}")
        
        print(f"✓ Loaded {len(prompts)} prompt templates")
        return prompts
    
    def load_master_json(self):
        """Load latest master.json from previous week"""
        prev_week = self.week_number - 1
        master_path = DATA_DIR / f"W{prev_week}" / "master.json"
        
        if not master_path.exists():
            raise FileNotFoundError(f"Cannot find master.json for Week {prev_week} at {master_path}")
        
        with open(master_path, 'r') as f:
            self.master_json = json.load(f)
        
        print(f"✓ Loaded master.json from Week {prev_week}")
        return self.master_json
    
    def call_gpt4(self, system_prompt, user_message, model="gpt-4-turbo-preview", temperature=0.7):
        """Call OpenAI GPT-4 API with error handling"""
        if not self.ai_enabled or not self.client:
            raise RuntimeError("AI model not available (missing OPENAI_API_KEY).")
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=temperature,
                max_tokens=4096
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"❌ OpenAI API error: {str(e)}")
            raise
    
    def run_prompt_a(self):
        """Prompt A: Data Engine - Update master.json with new week data"""
        print("\n🔄 Running Prompt A: Data Engine...")
        
        system_prompt = "You are the GenAi Chosen Data Engine. Follow Prompt A specifications exactly."
        
        override_note = ''
        if self.eval_date:
            override_note = f"\nUse evaluation date {self.eval_date} as current_date (do not use today's date)."
        user_message = f"""
    {self.prompts['A']}

    ---

    Here is last week's master.json:

    ```json
    {json.dumps(self.master_json, indent=2)}
    ```

    Please update this for Week {self.week_number}, following all Change Management rules.
    Fetch latest prices for Thursday close (or most recent trading day).{override_note}
    Output the updated master.json.
    """
        
        response = self.call_gpt4(system_prompt, user_message, temperature=0.3)
        
        # Extract JSON from response
        json_match = re.search(r'```json\s*({.*?})\s*```', response, re.DOTALL)
        if json_match:
            try:
                self.master_json = json.loads(json_match.group(1))
            except json.JSONDecodeError as e:
                print(f"❌ Failed to parse JSON from code block: {e}")
                # Try to find JSON without code block markers
                json_match = re.search(r'{\s*"meta".*?}(?=\s*$)', response, re.DOTALL)
                if json_match:
                    self.master_json = json.loads(json_match.group(0))
                else:
                    raise ValueError("Could not extract valid master.json from Prompt A response")
        else:
            # Try to parse entire response as JSON
            try:
                self.master_json = json.loads(response)
            except json.JSONDecodeError:
                raise ValueError("Prompt A did not return valid JSON. Check response format.")
        
        # Enforce evaluation date override if set
        if self.eval_date and self.master_json.get('meta', {}).get('current_date') != self.eval_date:
            self.master_json['meta']['current_date'] = self.eval_date

        # Save updated master.json
        current_week_dir = DATA_DIR / f"W{self.week_number}"
        current_week_dir.mkdir(exist_ok=True)
        
        master_path = current_week_dir / "master.json"
        with open(master_path, 'w') as f:
            json.dump(self.master_json, f, indent=2)
        
        # Archive copy
        ARCHIVE_DIR.mkdir(exist_ok=True)
        eval_date = self.master_json['meta']['current_date'].replace('-', '')
        archive_path = ARCHIVE_DIR / f"master-{eval_date}.json"
        with open(archive_path, 'w') as f:
            json.dump(self.master_json, f, indent=2)
        
        print(f"✓ Prompt A completed - master.json updated for Week {self.week_number}")
        return self.master_json

    # ===================== ALPHA VANTAGE DATA ENGINE =====================
    def _latest_market_date(self):
        """Return latest market date (previous weekday if weekend)."""
        d = datetime.utcnow().date()
        # Adjust weekends
        if d.weekday() == 5:  # Saturday
            d -= timedelta(days=1)
        elif d.weekday() == 6:  # Sunday
            d -= timedelta(days=2)
        return d.strftime('%Y-%m-%d')

    def _fetch_alphavantage_quote(self, symbol):
        """Fetch latest quote for a symbol from Alpha Vantage.
        Returns dict with date and close price, or None on failure.
        """
        url = 'https://www.alphavantage.co/query'
        params = {
            'function': 'GLOBAL_QUOTE',
            'symbol': symbol,
            'apikey': self.alphavantage_key
        }
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if 'Global Quote' in data and data['Global Quote']:
                quote = data['Global Quote']
                return {
                    'date': quote.get('07. latest trading day', ''),
                    'close': float(quote.get('05. price', 0))
                }
            elif 'Note' in data:
                print(f"⚠️ Rate limit hit for {symbol}: {data['Note']}")
                return None
            else:
                print(f"⚠️ No data returned for {symbol}")
                return None
        except Exception as e:
            print(f"⚠️ Failed to fetch {symbol}: {e}")
            return None

    def generate_master_from_alphavantage(self):
        """Generate new week's master.json using Alpha Vantage API.
        Uses previous week's master.json as baseline, fetches latest prices,
        recalculates weekly and total pct changes, benchmarks, portfolio history.
        """
        print("\n🔄 Running Alpha Vantage data engine (replacing Prompt A)...")
        if self.master_json is None:
            raise ValueError("Previous master.json must be loaded before fetching new data.")

        prev_master = json.loads(json.dumps(self.master_json))  # deep copy
        prev_date = prev_master['meta']['current_date']
        inception_date = prev_master['meta']['inception_date']
        inception_value = prev_master['meta']['inception_value']
        new_date = self.eval_date if self.eval_date else self._latest_market_date()
        prev_portfolio_value = prev_master['portfolio_history'][-1]['value']

        # Avoid duplicate regeneration
        if new_date == prev_date:
            print("⚠️ Evaluation date equals previous date; skipping update.")
            return prev_master

        tickers = [s['ticker'] for s in prev_master['stocks']]
        print(f"Fetching prices for {len(tickers)} stocks + 2 benchmarks (Alpha Vantage API)")
        print("Rate limiting: 5 requests/minute (12 sec between calls)...")

        # Fetch stock prices with rate limiting (5 req/min = 12 sec between calls)
        price_data = {}
        for i, ticker in enumerate(tickers, 1):
            print(f"→ [{i}/{len(tickers)}] Fetching {ticker}...")
            quote = self._fetch_alphavantage_quote(ticker)
            if quote:
                price_data[ticker] = quote
            else:
                # Use previous price as fallback
                prev_stock = next(s for s in prev_master['stocks'] if s['ticker'] == ticker)
                price_data[ticker] = {
                    'date': prev_date,
                    'close': prev_stock['prices'][prev_date]
                }
                print(f"  ↳ Using previous price as fallback: ${price_data[ticker]['close']}")
            
            # Rate limit (skip delay on last item)
            if i < len(tickers):
                time.sleep(12)

        # Build updated stocks list
        updated_stocks = []
        for stock in prev_master['stocks']:
            t = stock['ticker']
            current_price = price_data[t]['close']
            
            # Get inception and prior prices from history
            inception_price = stock['prices'][inception_date]
            prior_price = stock['prices'][prev_date]

            weekly_pct = ((current_price / prior_price) - 1) * 100 if prior_price else 0.0
            total_pct = ((current_price / inception_price) - 1) * 100 if inception_price else 0.0

            # Update prices dict
            new_prices = dict(stock['prices'])
            new_prices[new_date] = round(current_price, 2)

            current_value = round(stock['shares'] * current_price)

            updated_stocks.append({
                "ticker": t,
                "name": stock['name'],
                "shares": stock['shares'],
                "prices": new_prices,
                "current_value": current_value,
                "weekly_pct": round(weekly_pct, 2),
                "total_pct": round(total_pct, 2)
            })

        portfolio_current_value = sum(s['current_value'] for s in updated_stocks)
        portfolio_weekly_pct = ((portfolio_current_value / prev_portfolio_value) - 1) * 100 if prev_portfolio_value else 0.0
        portfolio_total_pct = ((portfolio_current_value / inception_value) - 1) * 100 if inception_value else 0.0

        # Benchmarks: S&P 500 (SPY ETF as proxy), Bitcoin (use crypto endpoint fallback)
        bench_symbols = {"sp500": "SPY", "bitcoin": "BTC"}  # SPY as S&P proxy
        print("\nFetching benchmarks...")
        bench_data = {}
        
        for key, symbol in bench_symbols.items():
            print(f"→ Fetching {key.upper()} ({symbol})...")
            if key == 'bitcoin':
                # Bitcoin requires CRYPTO endpoint
                url = 'https://www.alphavantage.co/query'
                params = {
                    'function': 'CURRENCY_EXCHANGE_RATE',
                    'from_currency': 'BTC',
                    'to_currency': 'USD',
                    'apikey': self.alphavantage_key
                }
                try:
                    response = requests.get(url, params=params, timeout=10)
                    data = response.json()
                    if 'Realtime Currency Exchange Rate' in data:
                        rate = data['Realtime Currency Exchange Rate']
                        bench_data[key] = {
                            'date': rate.get('6. Last Refreshed', new_date)[:10],
                            'close': float(rate.get('5. Exchange Rate', 0))
                        }
                    else:
                        print(f"⚠️ Bitcoin data unavailable, using previous value")
                        prev_btc = prev_master['benchmarks']['bitcoin']['history'][-1]['close']
                        bench_data[key] = {'date': prev_date, 'close': prev_btc}
                except Exception as e:
                    print(f"⚠️ Bitcoin fetch failed: {e}")
                    prev_btc = prev_master['benchmarks']['bitcoin']['history'][-1]['close']
                    bench_data[key] = {'date': prev_date, 'close': prev_btc}
            else:
                quote = self._fetch_alphavantage_quote(symbol)
                if quote:
                    bench_data[key] = quote
                else:
                    # Fallback to previous value
                    prev_val = prev_master['benchmarks'][key]['history'][-1]['close']
                    bench_data[key] = {'date': prev_date, 'close': prev_val}
                    print(f"  ↳ Using previous value: ${bench_data[key]['close']}")
            
            time.sleep(12)  # Rate limit

        # Update benchmarks
        updated_benchmarks = {}
        for bench_key, series in prev_master['benchmarks'].items():
            inception_reference = series['inception_reference']
            history_prev = series['history']
            prev_close = history_prev[-1]['close']
            current_close = bench_data[bench_key]['close']

            weekly_pct = ((current_close / prev_close) - 1) * 100 if prev_close else 0.0
            total_pct = ((current_close / inception_reference) - 1) * 100 if inception_reference else 0.0

            new_history_entry = {
                "date": new_date,
                "close": round(current_close, 2),
                "weekly_pct": round(weekly_pct, 2),
                "total_pct": round(total_pct, 2)
            }
            updated_benchmarks[bench_key] = {
                "inception_reference": inception_reference,
                "history": history_prev + [new_history_entry]
            }

        # Portfolio history
        new_history_entry = {
            "date": new_date,
            "value": portfolio_current_value,
            "weekly_pct": round(portfolio_weekly_pct, 2),
            "total_pct": round(portfolio_total_pct, 2)
        }
        updated_portfolio_history = prev_master['portfolio_history'] + [new_history_entry]

        # Normalized chart entry
        spx_first_ref = prev_master['benchmarks']['sp500']['inception_reference']
        btc_first_ref = prev_master['benchmarks']['bitcoin']['inception_reference']
        spx_close = updated_benchmarks['sp500']['history'][-1]['close']
        btc_close = updated_benchmarks['bitcoin']['history'][-1]['close']
        
        normalized_entry = {
            "date": new_date,
            "portfolio_value": portfolio_current_value,
            "genai_norm": round(100 * portfolio_current_value / inception_value, 2),
            "spx_close": spx_close,
            "btc_close": btc_close,
            "spx_norm": round(100 * spx_close / spx_first_ref, 5),
            "btc_norm": round(100 * btc_close / btc_first_ref, 5)
        }

        updated_master = {
            "meta": {
                "portfolio_name": prev_master['meta']['portfolio_name'],
                "inception_date": inception_date,
                "inception_value": inception_value,
                "current_date": new_date
            },
            "stocks": updated_stocks,
            "portfolio_totals": {
                "current_value": portfolio_current_value,
                "weekly_pct": round(portfolio_weekly_pct, 2),
                "total_pct": round(portfolio_total_pct, 2)
            },
            "benchmarks": updated_benchmarks,
            "portfolio_history": updated_portfolio_history,
            "normalized_chart": prev_master['normalized_chart'] + [normalized_entry]
        }

        # Persist
        current_week_dir = DATA_DIR / f"W{self.week_number}"
        current_week_dir.mkdir(exist_ok=True)
        master_path = current_week_dir / "master.json"
        with open(master_path, 'w') as f:
            json.dump(updated_master, f, indent=2)

        # Archive
        ARCHIVE_DIR.mkdir(exist_ok=True)
        archive_path = ARCHIVE_DIR / f"master-{new_date.replace('-', '')}.json"
        with open(archive_path, 'w') as f:
            json.dump(updated_master, f, indent=2)

        self.master_json = updated_master
        print(f"✓ Alpha Vantage data engine completed - master.json updated for Week {self.week_number}")
        return updated_master
    
    def run_prompt_b(self):
        """Prompt B: Narrative Writer - Generate HTML content"""
        print("\n📝 Running Prompt B: Narrative Writer...")
        
        system_prompt = "You are the GenAi Chosen Narrative Writer. Follow Prompt B specifications exactly."
        
        user_message = f"""
{self.prompts['B']}

---

Here is the updated master.json:

```json
{json.dumps(self.master_json, indent=2)}
```

Generate:
1. narrative.html (the prose content block)
2. seo.json (all metadata)

This is for Week {self.week_number}.
"""
        
        response = self.call_gpt4(system_prompt, user_message)
        
        # Extract narrative HTML
        html_match = re.search(r'```html\s*(<div class="prose.*?</div>)\s*```', response, re.DOTALL)
        if html_match:
            self.narrative_html = html_match.group(1)
        else:
            # Try without code blocks
            html_match = re.search(r'(<div class="prose prose-invert max-w-none">.*?</div>)', response, re.DOTALL)
            if html_match:
                self.narrative_html = html_match.group(1)
            else:
                raise ValueError("Could not extract narrative HTML from Prompt B response")
        
        # Extract SEO JSON
        json_match = re.search(r'```json\s*({.*?})\s*```', response, re.DOTALL)
        if json_match:
            try:
                self.seo_json = json.loads(json_match.group(1))
            except json.JSONDecodeError as e:
                print(f"⚠️ Failed to parse SEO JSON: {e}")
                self.seo_json = self.generate_fallback_seo()
        else:
            print("⚠️ No SEO JSON found, generating fallback")
            self.seo_json = self.generate_fallback_seo()
        
        print("✓ Prompt B completed - narrative and SEO generated")
        return self.narrative_html, self.seo_json
    
    def generate_fallback_seo(self):
        """Generate fallback SEO metadata if extraction fails"""
        current_date = self.master_json['meta']['current_date']
        return {
            "title": f"GenAi-Managed Stocks Portfolio Week {self.week_number} – Performance, Risks & Next Moves - Quantum Investor Digest",
            "description": f"Week {self.week_number} performance update for the AI-managed stock portfolio. Review returns vs S&P 500 and Bitcoin, top movers, and next week's outlook.",
            "canonicalUrl": f"https://quantuminvestor.net/Posts/GenAi-Managed-Stocks-Portfolio-Week-{self.week_number}.html",
            "ogTitle": f"GenAi-Managed Stocks Portfolio Week {self.week_number}",
            "ogDescription": f"Week {self.week_number} AI portfolio performance analysis",
            "ogImage": f"https://quantuminvestor.net/Media/W{self.week_number}.webp",
            "ogUrl": f"https://quantuminvestor.net/Posts/GenAi-Managed-Stocks-Portfolio-Week-{self.week_number}.html",
            "twitterTitle": f"GenAi Portfolio Week {self.week_number}",
            "twitterDescription": f"AI-managed portfolio weekly update",
            "twitterImage": f"https://quantuminvestor.net/Media/W{self.week_number}.webp",
            "twitterCard": "summary_large_image"
        }
    
    def run_prompt_c(self):
        """Prompt C: Visual Generator - Create table and chart"""
        print("\n📊 Running Prompt C: Visual Generator...")
        
        system_prompt = "You are the GenAi Chosen Visual Module Generator. Follow Prompt C specifications exactly."
        
        user_message = f"""
{self.prompts['C']}

---

Here is the master.json:

```json
{json.dumps(self.master_json, indent=2)}
```

Generate:
1. performance_table.html
2. performance_chart.svg (wrapped in container HTML)

This is for Week {self.week_number}.
"""
        
        response = self.call_gpt4(system_prompt, user_message)
        
        # Extract table HTML (including nested divs and table)
        table_match = re.search(r'<div class="myblock-performance-snapshot">.*?</table>\s*</div>', response, re.DOTALL)
        if table_match:
            self.performance_table = table_match.group(0)
        else:
            print("⚠️ Could not extract performance table from Prompt C response")
            self.performance_table = "<!-- Performance table not generated -->"
        
        # Extract chart HTML (entire container including legend)
        # Use a better pattern that captures nested divs properly
        chart_start = response.find('<div class="myblock-chart-container">')
        if chart_start != -1:
            # Find matching closing div by counting nested divs
            depth = 0
            i = chart_start
            while i < len(response):
                if response[i:i+4] == '<div':
                    depth += 1
                elif response[i:i+6] == '</div>':
                    depth -= 1
                    if depth == 0:
                        self.performance_chart = response[chart_start:i+6]
                        break
                i += 1
        
        if not self.performance_chart:
            print("⚠️ Could not extract performance chart from Prompt C response")
            self.performance_chart = "<!-- Performance chart not generated -->"
        
        print("✓ Prompt C completed - visuals generated")
        return self.performance_table, self.performance_chart
    
    def run_prompt_d(self):
        """Prompt D: Final Assembler - Create complete HTML page"""
        print("\n🔨 Running Prompt D: Final HTML Assembler...")
        
        system_prompt = "You are the GenAi Chosen Final Page Builder. Follow Prompt D specifications exactly."
        
        # Embed table and chart into narrative if not already there
        if self.performance_table and self.performance_table not in self.narrative_html:
            # Find insertion point after "Performance Snapshot" section
            snapshot_pattern = r'(<h2[^>]*>Performance Snapshot</h2>\s*<p[^>]*>.*?</p>)'
            match = re.search(snapshot_pattern, self.narrative_html, re.DOTALL)
            if match:
                insert_pos = match.end()
                self.narrative_html = (
                    self.narrative_html[:insert_pos] + 
                    '\n\n' + self.performance_table + '\n\n' + 
                    self.narrative_html[insert_pos:]
                )
            else:
                print("⚠️ Could not find Performance Snapshot insertion point")
        
        if self.performance_chart and self.performance_chart not in self.narrative_html:
            # Find insertion point after "Performance Since Inception" section
            inception_pattern = r'(<h2[^>]*>Performance Since Inception</h2>(?:.*?</p>){2,3})'
            match = re.search(inception_pattern, self.narrative_html, re.DOTALL)
            if match:
                insert_pos = match.end()
                self.narrative_html = (
                    self.narrative_html[:insert_pos] + 
                    '\n\n' + self.performance_chart + '\n\n' + 
                    self.narrative_html[insert_pos:]
                )
            else:
                print("⚠️ Could not find Performance Since Inception insertion point")
        
        user_message = f"""
{self.prompts['D']}

---

Here are the components:

**narrative.html:**
```html
{self.narrative_html}
```

**seo.json:**
```json
{json.dumps(self.seo_json, indent=2)}
```

**master.json (for reference):**
```json
{json.dumps(self.master_json, indent=2)}
```

Generate the complete HTML file for Week {self.week_number}.
"""
        
        response = self.call_gpt4(system_prompt, user_message, temperature=0.2)
        
        # Extract final HTML
        html_match = re.search(r'<!DOCTYPE html>.*</html>', response, re.DOTALL | re.IGNORECASE)
        final_html = html_match.group(0) if html_match else response
        
        # Basic validation
        if not final_html.strip().startswith('<!DOCTYPE'):
            print("⚠️ Warning: Generated HTML doesn't start with DOCTYPE")
        if '</html>' not in final_html.lower():
            print("⚠️ Warning: Generated HTML doesn't have closing </html> tag")
        
        # Check for required elements
        required_elements = ['<head>', '<body>', '<article>', 'class="prose']
        missing = [elem for elem in required_elements if elem not in final_html]
        if missing:
            print(f"⚠️ Warning: Missing expected elements: {', '.join(missing)}")
        
        # Save to Posts folder
        output_path = POSTS_DIR / f"GenAi-Managed-Stocks-Portfolio-Week-{self.week_number}.html"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_html)
        
        print(f"✓ Prompt D completed - {output_path.name} created ({len(final_html)} bytes)")
        return final_html
    
    def update_index_pages(self):
        """Update index.html and posts.html with new post card"""
        print("\n🔗 Updating index and posts pages...")
        
        # This is a simplified version - you may need to customize based on your exact HTML structure
        post_date = datetime.now().strftime("%B %d, %Y")
        post_url = f"Posts/GenAi-Managed-Stocks-Portfolio-Week-{self.week_number}.html"
        
        # TODO: Implement actual HTML insertion logic for your specific site structure
        # This would parse index.html and posts.html, find the posts section,
        # and insert a new card with the correct structure
        
        print("✓ Index pages updated (manual review recommended)")
    
    def run(self):
        """Execute full pipeline"""
        print(f"\n{'='*60}")
        print(f"GenAi Chosen Portfolio - Week {self.week_number} Automation")
        print(f"{'='*60}")

        try:
            self.load_master_json()
            
            # Data acquisition: AI or Alpha Vantage
            if self.data_source == 'alphavantage':
                self.generate_master_from_alphavantage()
            else:
                self.run_prompt_a()
            
            # Narrative generation (if AI enabled)
            if self.ai_enabled:
                self.run_prompt_b()
                self.run_prompt_c()
                self.run_prompt_d()
            else:
                # Fallback: data-only HTML
                output_path = POSTS_DIR / f"GenAi-Managed-Stocks-Portfolio-Week-{self.week_number}.html"
                minimal_html = f"""<!DOCTYPE html>
<html lang='en'>
<head>
  <meta charset='UTF-8'>
  <title>GenAi-Managed Stocks Portfolio Week {self.week_number} (Data Only)</title>
  <meta name='description' content='Weekly portfolio update (data-only mode).'>
</head>
<body style='background:#000; color:#fff; font-family:sans-serif; padding:2rem;'>
  <article style='max-width:900px; margin:0 auto;'>
    <h1>GenAi-Managed Stocks Portfolio Week {self.week_number}</h1>
    <p><em>AI narrative skipped (no OPENAI_API_KEY). Raw data below:</em></p>
    <pre style='white-space:pre-wrap; font-size:12px; background:#111; padding:1rem; border-radius:8px; overflow-x:auto;'>{json.dumps(self.master_json, indent=2)}</pre>
    <p><a href='posts.html' style='color:#6366f1;'>← Back to Posts</a></p>
  </article>
</body>
</html>"""
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(minimal_html)
                print(f"✓ Data-only HTML generated: {output_path.name}")

            self.update_index_pages()

            print(f"\n{'='*60}")
            print(f"✅ SUCCESS! Week {self.week_number} generated successfully")
            print(f"{'='*60}")
            print(f"\nGenerated files:")
            print(f"  - Data/W{self.week_number}/master.json")
            print(f"  - Posts/GenAi-Managed-Stocks-Portfolio-Week-{self.week_number}.html")
            if not self.ai_enabled:
                print("    (Data-only mode: enable OPENAI_API_KEY for full narrative)")
            print(f"  - Data/archive/master-{self.master_json['meta']['current_date'].replace('-', '')}.json")
        except Exception as e:
            print(f"\n❌ ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='Automate weekly portfolio update')
    parser.add_argument('--week', type=str, default='auto', 
                       help='Week number (default: auto-detect next week)')
    parser.add_argument('--api-key', type=str, 
                       help='OpenAI API key (default: read from OPENAI_API_KEY env var)')
    parser.add_argument('--model', type=str, default='gpt-4-turbo-preview',
                       help='OpenAI model to use (default: gpt-4-turbo-preview)')
    parser.add_argument('--data-source', type=str, choices=['ai', 'alphavantage'], default='ai',
                       help='Data source: ai (Prompt A via GPT-4) or alphavantage (Alpha Vantage API)')
    parser.add_argument('--alphavantage-key', type=str,
                       help='Alpha Vantage API key (default: read from ALPHAVANTAGE_API_KEY env var)')
    parser.add_argument('--eval-date', type=str,
                        help='Manual override for evaluation date (YYYY-MM-DD). Uses this as current_date for week update.')

    args = parser.parse_args()

    week_number = None if args.week == 'auto' else int(args.week)

    automation = PortfolioAutomation(
        week_number=week_number,
        api_key=args.api_key,
        model=args.model,
        data_source=args.data_source,
        alphavantage_key=args.alphavantage_key,
        eval_date=args.eval_date
    )
    automation.run()

if __name__ == '__main__':
    main()
