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
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import io
import base64

# Configure paths
REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "Data"
POSTS_DIR = REPO_ROOT / "Posts"
PROMPT_DIR = REPO_ROOT / "Prompt"
ARCHIVE_DIR = DATA_DIR / "archive"

# CSP policy template (per-run nonce, no unsafe-inline)
CSP_POLICY_TEMPLATE = (
    "default-src 'self'; "
    "script-src 'self' 'nonce-{nonce}'; "
    "style-src 'self'; "
    "img-src 'self' data: https:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'self'; "
    "base-uri 'self'; "
    "form-action 'self';"
)

class PortfolioAutomation:
    def __init__(self, week_number=None, api_key=None, model="gpt-4-turbo-preview", data_source="ai", alphavantage_key=None, eval_date=None, palette="default", minify_css=False):
        self.week_number = week_number or self.detect_next_week()
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.model = model
        self.data_source = data_source.lower()
        self.alphavantage_key = alphavantage_key or os.getenv('ALPHAVANTAGE_API_KEY')
        self.client = None
        self.ai_enabled = False
        self.eval_date = None
        self.palette = palette  # theme palette selector ("default", "alt", etc.)
        self.minify_css = minify_css
        self.nonce = 'qi123'
        self.stylesheet_name = 'styles.css'
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
        """Auto-detect next week number by scanning Data/ directory"""
        week_folders = sorted([int(d.name[1:]) for d in DATA_DIR.glob('W*') if d.is_dir() and d.name[1:].isdigit()])
        return (week_folders[-1] + 1) if week_folders else 1
    
    def load_prompts(self):
        """Load all prompt markdown files (A, B, C, D)"""
        prompts = {}
        for letter in ['A', 'B', 'C', 'D']:
            prompt_file = PROMPT_DIR / f"Prompt-{letter}-v5.4{letter}.md"
            if prompt_file.exists():
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    prompts[letter] = f.read()
            else:
                print(f"⚠️ Warning: {prompt_file.name} not found")
                prompts[letter] = f"# Prompt {letter} (placeholder)"
        return prompts
    
    def load_master_json(self):
        """Load previous week's master.json as baseline"""
        prev_week = self.week_number - 1
        if prev_week < 1:
            raise ValueError("Cannot load previous master.json for Week 1. Provide baseline manually.")
        
        prev_master_path = DATA_DIR / f"W{prev_week}" / "master.json"
        if not prev_master_path.exists():
            raise ValueError(f"Previous week's master.json not found: {prev_master_path}")
        
        with open(prev_master_path, 'r', encoding='utf-8') as f:
            self.master_json = json.load(f)
        
        print(f"✓ Loaded baseline from Week {prev_week}: {prev_master_path}")
        return self.master_json
    
    def call_gpt4(self, system_prompt, user_message, temperature=0.7):
        """Wrapper for OpenAI API calls with error handling"""
        if not self.client:
            raise ValueError("OpenAI client not initialized. Set OPENAI_API_KEY.")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"⚠️ GPT-4 API call failed: {e}")
            raise
    
    def _purge_and_minify_css(self):
        """CSS optimization (placeholder - not critical for MVP)"""
        print("⚠️ CSS minification not implemented (using original styles.css)")
        pass
    
    def run_prompt_a(self):
        """Prompt A: Data Engine - Update master.json with new week's data"""
        print("\n📊 Running Prompt A: Data Engine...")
        
        system_prompt = "You are the GenAi Chosen Data Engine. Follow Prompt A specifications exactly."
        
        user_message = f"""
{self.prompts['A']}

---

Here is last week's master.json:

```json
{json.dumps(self.master_json, indent=2)}
```

Generate the updated master.json for Week {self.week_number}.
"""
        
        response = self.call_gpt4(system_prompt, user_message)
        
        # Extract JSON from response
        json_match = re.search(r'```json\s*({.*?})\s*```', response, re.DOTALL)
        if json_match:
            self.master_json = json.loads(json_match.group(1))
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
        
        # Generate hero image then snippet share card immediately after data update
        try:
            self.generate_hero_image()
        except Exception as e:
            print(f"⚠️ Hero image generation failed: {e}")
        try:
            self.generate_snippet_card()
        except Exception as e:
            print(f"⚠️ Snippet card generation failed: {e}")
        
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
        # Generate hero image then snippet share card for alphavantage path
        try:
            self.generate_hero_image()
        except Exception as e:
            print(f"⚠️ Hero image generation failed: {e}")
        try:
            self.generate_snippet_card()
        except Exception as e:
            print(f"⚠️ Snippet card generation failed: {e}")
        return updated_master

    # ===================== SNIPPET CARD GENERATION (Pillow) =====================
    def _font(self, size: int):
        candidates = [
            Path("C:/Windows/Fonts/SegoeUI-Semibold.ttf"),
            Path("C:/Windows/Fonts/SegoeUI.ttf"),
            Path("C:/Windows/Fonts/Arial.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
        ]
        face = None
        for c in candidates:
            if c.exists():
                face = str(c)
                break
        try:
            return ImageFont.truetype(face or "Arial", size=size)
        except Exception:
            return ImageFont.load_default()

    def generate_snippet_card(self):
        """Create 1200x630 PNG snippet card using latest master_json metrics."""
        if not self.master_json:
            raise ValueError("master_json not loaded")
        width, height = 1200, 630
        padding = 72
        # Build radial purple gradient background
        base = Image.new('RGBA', (width, height), (10,10,10,255))
        grad = Image.new('L', (width, height))
        cx, cy = width*0.4, height*0.35
        maxd = (width**2 + height**2)**0.5
        pix = grad.load()
        for y in range(height):
            for x in range(width):
                d = ((x-cx)**2 + (y-cy)**2)**0.5
                v = max(0, 255 - int((d/maxd)*255))
                pix[x,y] = v
        grad = grad.filter(ImageFilter.GaussianBlur(160))
        overlay = Image.new('RGBA', (width, height), (58,0,104,255))
        overlay.putalpha(grad)
        img = Image.alpha_composite(base, overlay)

        # Metrics extraction
        ph = self.master_json.get('portfolio_history', [])
        spx = self.master_json.get('benchmarks', {}).get('sp500', {}).get('history', [])
        if ph and spx:
            lp = ph[-1]; ls = spx[-1]
            week_str = f"{lp.get('weekly_pct'):.2f}%" if lp.get('weekly_pct') is not None else "--"
            total_str = f"{lp.get('total_pct'):.2f}%" if lp.get('total_pct') is not None else "--"
            alpha_str = "--"
            if lp.get('total_pct') is not None and ls.get('total_pct') is not None:
                alpha_val = lp['total_pct'] - ls['total_pct']
                alpha_str = f"{alpha_val:.2f}%"
        else:
            week_str = total_str = alpha_str = "--"
        inception = self.master_json.get('meta', {}).get('inception_date')
        current_date = self.master_json.get('meta', {}).get('current_date')
        date_range = f"{inception} → {current_date}" if inception and current_date else ""

        d = ImageDraw.Draw(img)
        # Badge
        badge_text = f"Week {self.week_number}"; badge_font = self._font(36)
        bbox = d.textbbox((0,0), badge_text, font=badge_font)
        bw = bbox[2]-bbox[0]; bh = bbox[3]-bbox[1]
        pad_x, pad_y = 28, 14
        d.rounded_rectangle([padding, padding, padding + bw + pad_x*2, padding + bh + pad_y*2], radius=50, fill=(30,27,75,255))
        d.text((padding+pad_x, padding+pad_y), badge_text, font=badge_font, fill=(230,230,255,255))
        # Title
        title_font = self._font(74)
        title_text = f"AI Portfolio Weekly Performance"
        d.text((padding, padding+bh+pad_y*2+34), title_text, font=title_font, fill=(255,255,255,240))
        block_y = padding+bh+pad_y*2+34 + 110
        metric_font = self._font(34)
        label_font = self._font(14)
        def draw_metric(x,label,value,color=(255,255,255,230)):
            d.text((x, block_y), label.upper(), font=label_font, fill=(180,180,200,200))
            d.text((x, block_y+22), value, font=metric_font, fill=color)
        alpha_color = (74,222,128,255) if (not alpha_str.startswith('-') and alpha_str != '--') else (248,113,113,255)
        draw_metric(padding, 'Week Change', week_str)
        draw_metric(padding+420, 'Since Inception', total_str)
        draw_metric(padding+840, 'Alpha vs SPX', alpha_str, alpha_color)
        footer_font = self._font(26)
        if date_range:
            d.text((padding, height-padding-40), date_range, font=footer_font, fill=(190,190,190,230))
        d.text((width-padding-330, height-padding-40), 'quantuminvestor.net', font=footer_font, fill=(190,190,210,230))

        out_path = REPO_ROOT / 'Media' / f"W{self.week_number}-card.png"
        out_path.parent.mkdir(exist_ok=True)
        img.convert('RGB').save(out_path, format='PNG')
        print(f"✓ Snippet card generated: {out_path}")

    # ===================== HERO IMAGE GENERATION (Remote + Overlay) =====================
    def generate_hero_image(self, query: str = "futuristic finance data"):
        """Create 1200x800 WEBP hero image using remote provider or fallback gradient."""
        if not self.master_json:
            raise ValueError("master_json not loaded")
        width, height = 1200, 800
        padding = 64
        # --- Metrics extraction ---
        ph = self.master_json.get('portfolio_history', [])
        spx = self.master_json.get('benchmarks', {}).get('sp500', {}).get('history', [])
        if ph and spx:
            lp = ph[-1]; ls = spx[-1]
            week_str = f"{lp.get('weekly_pct'):.2f}%" if lp.get('weekly_pct') is not None else "--"
            total_str = f"{lp.get('total_pct'):.2f}%" if lp.get('total_pct') is not None else "--"
            alpha_str = "--"
            if lp.get('total_pct') is not None and ls.get('total_pct') is not None:
                alpha_val = lp['total_pct'] - ls['total_pct']
                alpha_str = f"{alpha_val:.2f}%"
        else:
            week_str = total_str = alpha_str = "--"
        inception = self.master_json.get('meta', {}).get('inception_date')
        current_date = self.master_json.get('meta', {}).get('current_date')
        date_range = f"{inception} → {current_date}" if inception and current_date else ""

        # --- Providers ---
        def fetch_pexels(q: str):
            key = os.getenv('PEXELS_API_KEY');
            if not key: return None
            try:
                resp = requests.get('https://api.pexels.com/v1/search', headers={'Authorization': key}, params={'query': q, 'orientation': 'landscape', 'per_page': 3}, timeout=10)
                if resp.status_code != 200: return None
                data = resp.json().get('photos', [])
                for p in data:
                    src = p.get('src', {}).get('large') or p.get('src', {}).get('original')
                    if src:
                        img_resp = requests.get(src, timeout=15)
                        if img_resp.status_code == 200:
                            return Image.open(io.BytesIO(img_resp.content)).convert('RGBA')
            except Exception:
                return None
            return None
        def fetch_pixabay(q: str):
            key = os.getenv('PIXABAY_API_KEY');
            if not key: return None
            try:
                resp = requests.get('https://pixabay.com/api/', params={'key': key, 'q': q, 'image_type': 'photo', 'orientation': 'horizontal', 'per_page': 3, 'safesearch': 'true'}, timeout=10)
                if resp.status_code != 200: return None
                hits = resp.json().get('hits', [])
                for h in hits:
                    src = h.get('largeImageURL') or h.get('webformatURL')
                    if src:
                        img_resp = requests.get(src, timeout=15)
                        if img_resp.status_code == 200:
                            return Image.open(io.BytesIO(img_resp.content)).convert('RGBA')
            except Exception:
                return None
            return None
        def fetch_lummi(q: str):
            # Placeholder for future API
            return None

        providers = [fetch_pexels, fetch_pixabay, fetch_lummi]
        remote = None
        for provider in providers:
            remote = provider(query)
            if remote:
                break

        # --- Fallback gradient ---
        if remote:
            r_ratio = remote.width / remote.height
            target_ratio = width / height
            if r_ratio > target_ratio:
                new_h = height
                new_w = int(r_ratio * new_h)
            else:
                new_w = width
                new_h = int(new_w / r_ratio)
            resized = remote.resize((new_w, new_h), Image.Resampling.LANCZOS)
            left = (new_w - width)//2; top = (new_h - height)//2
            img = resized.crop((left, top, left+width, top+height)).convert('RGBA')
            # Darken top region for text legibility
            mask = Image.new('L', (width, height), 0)
            dmask = ImageDraw.Draw(mask)
            dmask.rectangle([0,0,width,int(height*0.55)], fill=150)
            shadow = Image.new('RGBA', (width, height), (0,0,0,160)); shadow.putalpha(mask)
            img = Image.alpha_composite(img, shadow)
            source_note = 'remote'
        else:
            base = Image.new('RGBA', (width, height), (10,10,10,255))
            grad = Image.new('L', (width, height))
            cx, cy = width*0.5, height*0.4
            maxd = (width**2 + height**2)**0.5
            pix = grad.load()
            for y in range(height):
                for x in range(width):
                    d = ((x-cx)**2 + (y-cy)**2)**0.5
                    v = max(0, 255 - int((d/maxd)*255))
                    pix[x,y] = v
            grad = grad.filter(ImageFilter.GaussianBlur(200))
            overlay = Image.new('RGBA', (width, height), (72,0,120,255)); overlay.putalpha(grad)
            img = Image.alpha_composite(base, overlay)
            source_note = 'fallback-gradient'

        # --- Overlay text ---
        draw = ImageDraw.Draw(img)
        badge_text = f"Week {self.week_number}"; badge_font = self._font(40)
        b_w, b_h = draw.textbbox((0,0), badge_text, font=badge_font)[2:]
        bx_pad, by_pad = 30, 16
        draw.rounded_rectangle([padding, padding, padding+b_w+bx_pad*2, padding+b_h+by_pad*2], radius=60, fill=(30,27,75,230))
        draw.text((padding+bx_pad, padding+by_pad), badge_text, font=badge_font, fill=(235,235,255,255))
        title_font = self._font(78)
        title_text = "AI Portfolio Weekly Performance"
        draw.text((padding, padding+b_h+by_pad*2+42), title_text, font=title_font, fill=(255,255,255,240))
        base_y = padding+b_h+by_pad*2+42 + 120
        label_font = self._font(16); metric_font = self._font(36)
        def metric(x,label,val,color=(255,255,255,235)):
            draw.text((x, base_y), label.upper(), font=label_font, fill=(180,180,200,200))
            draw.text((x, base_y+26), val, font=metric_font, fill=color)
        alpha_color = (74,222,128,255) if (not alpha_str.startswith('-') and alpha_str != '--') else (248,113,113,255)
        metric(padding, 'Week Change', week_str)
        metric(padding+400, 'Since Inception', total_str)
        metric(padding+800, 'Alpha vs SPX', alpha_str, alpha_color)
        footer_font = self._font(26)
        if date_range:
            draw.text((padding, height-padding-44), date_range, font=footer_font, fill=(200,200,205,240))
        draw.text((width-padding-360, height-padding-44), 'quantuminvestor.net', font=footer_font, fill=(200,200,215,240))
        out_path = REPO_ROOT / 'Media' / f"W{self.week_number}.webp"
        out_path.parent.mkdir(exist_ok=True)
        img.convert('RGB').save(out_path, format='WEBP', quality=90)
        print(f"✓ Hero image generated: {out_path} ({source_note})")
    
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

    def _apply_standard_head(self, html: str) -> str:
        """Apply hardened CSP + nonce, stylesheet link, external scripts, JSON-LD."""
        seo = self.seo_json or self.generate_fallback_seo()
        canonical = seo.get('canonicalUrl')
        title = seo.get('title')
        meta_desc = seo.get('description')
        og_title = seo.get('ogTitle') or title
        og_desc = seo.get('ogDescription') or meta_desc
        og_image = seo.get('ogImage') or f"https://quantuminvestor.net/Media/W{self.week_number}.webp"
        og_url = seo.get('ogUrl') or canonical
        twitter_title = seo.get('twitterTitle') or og_title
        twitter_desc = seo.get('twitterDescription') or og_desc
        twitter_image = seo.get('twitterImage') or og_image
        twitter_card = seo.get('twitterCard') or 'summary_large_image'
        published_iso = self.master_json.get('meta', {}).get('current_date', datetime.utcnow().date().isoformat()) + 'T00:00:00Z'
        modified_iso = published_iso
        csp_policy = CSP_POLICY_TEMPLATE.format(nonce=self.nonce)
        # Derive keywords (fallback: generic terms + tickers)
        tickers = []
        try:
            tickers = [s.get('ticker') for s in self.master_json.get('stocks', []) if s.get('ticker')]
        except Exception:
            pass
        base_keywords = ["AI investing", "momentum stocks", "portfolio performance", "S&P 500", "Bitcoin"]
        if tickers:
            base_keywords.extend(tickers[:10])
        keywords_str = ", ".join(sorted(set(base_keywords)))

        blog_ld = {
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "headline": og_title,
            "description": og_desc,
            "image": og_image,
            "datePublished": published_iso,
            "dateModified": modified_iso,
            "dateCreated": self.master_json.get('meta', {}).get('inception_date', '2025-10-09'),
            "url": og_url,
            "mainEntityOfPage": {"@type": "WebPage", "@id": og_url},
            "author": {"@type": "Person", "name": "Michael Gavrilov"},
            "publisher": {"@type": "Organization", "name": "Quantum Investor Digest", "logo": {"@type": "ImageObject", "url": "https://quantuminvestor.net/Media/LogoB.webp"}},
            "articleSection": "AI Portfolio Weekly Review",
            "keywords": keywords_str
        }
        breadcrumbs_ld = {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://quantuminvestor.net/"},
                {"@type": "ListItem", "position": 2, "name": "Blog", "item": "https://quantuminvestor.net/Posts/posts.html"},
                {"@type": "ListItem", "position": 3, "name": f"Week {self.week_number}", "item": og_url}
            ]
        }

        head_markup = f"""<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>{title}</title>
    <meta name=\"description\" content=\"{meta_desc}\">
    <link rel=\"canonical\" href=\"{canonical}\">
    <meta name=\"author\" content=\"Michael Gavrilov\">
    <meta name=\"theme-color\" content=\"#000000\">
    <meta http-equiv=\"X-Content-Type-Options\" content=\"nosniff\">
    <meta http-equiv=\"X-Frame-Options\" content=\"SAMEORIGIN\">
    <meta http-equiv=\"Content-Security-Policy\" content=\"{csp_policy}\">
    <meta name=\"referrer\" content=\"strict-origin-when-cross-origin\">
    <meta property=\"og:type\" content=\"article\">
    <meta property=\"og:url\" content=\"{og_url}\">
    <meta property=\"og:title\" content=\"{og_title}\">
    <meta property=\"og:description\" content=\"{og_desc}\">
    <meta property=\"og:image\" content=\"{og_image}\">
    <meta property=\"article:published_time\" content=\"{published_iso}\">
    <meta property=\"article:modified_time\" content=\"{modified_iso}\">
    <meta name=\"twitter:card\" content=\"{twitter_card}\">
    <meta name=\"twitter:site\" content=\"@qid2025\">
    <meta name=\"twitter:title\" content=\"{twitter_title}\">
    <meta name=\"twitter:description\" content=\"{twitter_desc}\">
    <meta name=\"twitter:image\" content=\"{twitter_image}\">
    <link rel=\"icon\" href=\"../Media/favicon.ico\" type=\"image/x-icon\">
    <link rel=\"stylesheet\" href=\"../{self.stylesheet_name}\">
    <script src=\"../js/template-loader.js\" defer nonce=\"{self.nonce}\"></script>
    <script src=\"../js/mobile-menu.js\" defer nonce=\"{self.nonce}\"></script>
    <script src=\"../js/tldr.js\" defer nonce=\"{self.nonce}\"></script>
    <script type=\"application/ld+json\" nonce=\"{self.nonce}\">{json.dumps(blog_ld, separators=(',',':'))}</script>
    <script type=\"application/ld+json\" nonce=\"{self.nonce}\">{json.dumps(breadcrumbs_ld, separators=(',',':'))}</script>
</head>"""

        new_html = re.sub(r'<head>.*?</head>', head_markup, html, flags=re.DOTALL | re.IGNORECASE)
        if new_html == html:
            html_tag = re.search(r'<html[^>]*>', new_html, re.IGNORECASE)
            if html_tag:
                end = html_tag.end()
                new_html = new_html[:end] + head_markup + new_html[end:]
        palette_attr = f'data-theme="{self.palette}"'
        new_html = re.sub(r'<body(\s[^>]*)?>', lambda m: '<body ' + palette_attr + ('' if m.group(1) is None else m.group(1)) + '>', new_html, count=1)
        return new_html

    def harden_static_pages(self):
        """Apply dynamic nonce + strict CSP to root static pages (index, about, Disclosures)."""
        root_files = [
            REPO_ROOT / 'index.html',
            REPO_ROOT / 'about.html',
            REPO_ROOT / 'Disclosures.html'
        ]
        for fp in root_files:
            if not fp.exists():
                continue
            try:
                content = fp.read_text(encoding='utf-8')
                # Replace CSP meta
                csp_meta_pattern = re.compile(r'<meta http-equiv="Content-Security-Policy"[^>]+>', re.IGNORECASE)
                new_csp = f'<meta http-equiv="Content-Security-Policy" content="{CSP_POLICY_TEMPLATE.format(nonce=self.nonce)}">'
                content = csp_meta_pattern.sub(new_csp, content)
                # Add nonce to all eligible script tags (without one)
                def add_nonce(m):
                    tag = m.group(0)
                    if 'nonce=' in tag:
                        return tag
                    if 'type="application/ld+json"' in tag and 'nonce=' not in tag:
                        return tag.replace('<script', f'<script nonce="{self.nonce}"')
                    if 'defer' in tag or 'src=' in tag:
                        return tag.replace('<script', f'<script nonce="{self.nonce}"')
                    return tag
                content = re.sub(r'<script[^>]*>', add_nonce, content)
                fp.write_text(content, encoding='utf-8')
                print(f"✓ Hardened static page: {fp.name}")
            except Exception as e:
                print(f"⚠️ Failed hardening {fp.name}: {e}")

    def cleanup_existing_weekly_posts(self):
        """Remove inline margin styles (margin-bottom / margin-top) and apply utility classes mb-6 / mt-12."""
        posts_dir = REPO_ROOT / 'Posts'
        for fp in posts_dir.glob('GenAi-Managed-Stocks-Portfolio-Week-*.html'):
            try:
                original = fp.read_text(encoding='utf-8')
                updated = original
                # Remove specific inline margin styles
                updated = re.sub(r'\sstyle="margin-bottom:1.5rem;"', '', updated)
                updated = re.sub(r'\sstyle="margin-top:3rem;margin-bottom:1.5rem;"', '', updated)
                # Ensure mb-6 added where style removed for p and ul
                def add_mb6(match):
                    cls = match.group(1)
                    classes = cls.split()
                    if 'mb-6' not in classes:
                        classes.append('mb-6')
                    return 'class="' + ' '.join(classes) + '"'
                updated = re.sub(r'class="([^"]+)"(?![^>]*mb-6)(?=[^>]*>)(?=[^>]*(<p|<ul))', add_mb6, updated)
                # Headings: add mt-12 mb-6 if they had inline style removed or if pattern suggests they are section headers without spacing utilities
                def heading_utilities(m):
                    tag = m.group(1)
                    cls = m.group(2)
                    classes = cls.split()
                    if 'mt-12' not in classes:
                        classes.append('mt-12')
                    if 'mb-6' not in classes:
                        classes.append('mb-6')
                    return f'<{tag} class="' + ' '.join(classes) + '"'
                updated = re.sub(r'<(h2)\s+class="([^"]+)"', heading_utilities, updated)
                if updated != original:
                    fp.write_text(updated, encoding='utf-8')
                    print(f"✓ Cleaned inline styles: {fp.name}")
                else:
                    print(f"• No inline style changes needed: {fp.name}")
            except Exception as e:
                print(f"⚠️ Failed cleaning {fp.name}: {e}")
    
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

Generate the complete HTML file for Week {self.week_number}.
"""
        
        response = self.call_gpt4(system_prompt, user_message, temperature=0.2)
        
        # Extract final HTML
        html_match = re.search(r'<!DOCTYPE html>.*</html>', response, re.DOTALL | re.IGNORECASE)
        final_html = html_match.group(0) if html_match else response

        # ================= STANDARD META HEAD REPLACEMENT =================
        try:
            final_html = self._apply_standard_head(final_html)
        except Exception as e:
            print(f"⚠️ Standard head template failed: {e}")

        # ================= TLDR STRUCTURAL INJECTION (simplified, external script populates) =================
        try:
            # Remove accidental duplicate TLDR blocks leaving only first occurrence
            occurrences = [m.start() for m in re.finditer(r'id="tldrStrip"', final_html)]
            if len(occurrences) > 1:
                # Keep first, strip others
                final_html = re.sub(r'<!-- TLDR STRIP.*?<div id="tldrStrip"[\s\S]*?</div>\s*', '', final_html, count=len(occurrences)-1, flags=re.IGNORECASE)
            if 'id="tldrStrip"' not in final_html:
                tldr_markup = (
                    '\n<!-- TLDR STRIP (populated by external tldr.js) -->\n'
                    '<div id="tldrStrip" class="tldr-strip mb-10" aria-label="Weekly summary strip">\n'
                    '  <div class="tldr-metric"><span>Week Change</span><span id="tldrWeek">--</span></div>\n'
                    '  <div class="tldr-metric"><span>Since Inception</span><span id="tldrTotal">--</span></div>\n'
                    '  <div class="tldr-metric"><span>Alpha vs SPX (Total)</span><span id="tldrAlpha">--</span></div>\n'
                    '</div>\n'
                )
                prose_pos = final_html.find('<div class="prose')
                if prose_pos != -1:
                    final_html = final_html[:prose_pos] + tldr_markup + final_html[prose_pos:]
        except Exception as e:
            print(f"⚠️ TLDR structural injection failed: {e}")
        
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
        
        # ================= PERFORMANCE OPTIMIZATION =================
        try:
            final_html = self._optimize_performance(final_html)
        except Exception as e:
            print(f"⚠️ Performance optimization failed: {e}")

        # Save to Posts folder
        output_path = POSTS_DIR / f"GenAi-Managed-Stocks-Portfolio-Week-{self.week_number}.html"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_html)
        
        print(f"✓ Prompt D completed - {output_path.name} created ({len(final_html)} bytes)")
        return final_html

    def _optimize_performance(self, html: str) -> str:
        """Post-process HTML for performance: hero fetchpriority, lazy load images, remove redundant inline styles."""
        # Mark first hero image as high priority
        html = re.sub(r'<img([^>]*?\bsrc=\"[^\"]*W\d+\.webp\"[^>]*)>',
                      lambda m: ('<img' + (m.group(1)
                        .replace('loading="lazy"', '')
                        .replace('decoding="async"', '')
                        + ' fetchpriority="high" decoding="async"') + '>'), html, count=1)
        # Ensure remaining images (not hero) have lazy loading if not already
        def add_lazy(match):
            tag = match.group(0)
            if 'fetchpriority="high"' in tag:
                return tag
            if 'loading=' not in tag:
                tag = tag[:-1] + ' loading="lazy" decoding="async">'
            return tag
        html = re.sub(r'<img[^>]*>', add_lazy, html)
        # Remove any leftover <style> blocks that only define key-metric (now centralized)
        html = re.sub(r'<style>[^<]*?\.key-metric[^<]*?</style>', '', html, flags=re.DOTALL)
        return html
    
    def update_index_pages(self):
        """Update posts.html with dynamically generated listing from Posts/ directory"""
        print("\n🔗 Regenerating posts.html listing...")
        self._regenerate_posts_listing()
        print("✓ posts.html regenerated with current weekly posts")
    
    def _regenerate_posts_listing(self):
        """Scan Posts/ directory and rebuild posts.html with standardized head and cards"""
        # Collect all weekly post metadata
        post_files = sorted(
            POSTS_DIR.glob("GenAi-Managed-Stocks-Portfolio-Week-*.html"),
            key=lambda p: int(re.search(r'Week-(\d+)', p.name).group(1)),
            reverse=True
        )
        
        posts_meta = []
        for post_file in post_files:
            week_match = re.search(r'Week-(\d+)', post_file.name)
            if not week_match:
                continue
            week_num = int(week_match.group(1))
            
            # Parse published date and title from existing post file
            with open(post_file, 'r', encoding='utf-8') as f:
                content = f.read()
                date_match = re.search(r'<time[^>]*datetime="([^"]+)"', content)
                title_match = re.search(r'<title>([^<]+)</title>', content)
                desc_match = re.search(r'<meta name="description" content="([^"]+)"', content)
                
                pub_date = date_match.group(1).split('T')[0] if date_match else f"2025-10-{9+week_num:02d}"
                title = f"GenAi-Managed Stocks Portfolio Week {week_num}"
                desc = desc_match.group(1) if desc_match else f"Week {week_num} AI portfolio performance update."
                
                # Determine hero image
                hero_img = f"../Media/W{week_num}.webp" if (REPO_ROOT / f"Media/W{week_num}.webp").exists() else "../Media/Hero.webp"
                
                posts_meta.append({
                    'week': week_num,
                    'url': f"https://quantuminvestor.net/Posts/GenAi-Managed-Stocks-Portfolio-Week-{week_num}.html",
                    'relative_url': f"GenAi-Managed-Stocks-Portfolio-Week-{week_num}.html",
                    'title': title,
                    'description': desc,
                    'date': pub_date,
                    'hero': hero_img
                })
        
        # Build JSON-LD ItemList
        item_list_items = [
            {
                "@type": "ListItem",
                "position": idx + 1,
                "url": post['url'],
                "name": post['title'],
                "datePublished": post['date']
            }
            for idx, post in enumerate(posts_meta)
        ]
        
        item_list_json = {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": "All Posts - Quantum Investor Digest",
            "description": "Browse all weekly AI-managed stock portfolio performance updates and GenAI investing insights.",
            "url": "https://quantuminvestor.net/Posts/posts.html",
            "mainEntity": {
                "@type": "ItemList",
                "itemListElement": item_list_items
            }
        }
        
        breadcrumb_json = {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://quantuminvestor.net/"},
                {"@type": "ListItem", "position": 2, "name": "Blog", "item": "https://quantuminvestor.net/Posts/posts.html"}
            ]
        }
        
        # Build HTML cards
        cards_html = []
        for idx, post in enumerate(posts_meta):
            # Format date for display
            date_obj = datetime.strptime(post['date'], '%Y-%m-%d')
            date_display = date_obj.strftime('%B %d, %Y')
            
            # Only first card gets fetchpriority
            loading_attr = 'fetchpriority="high"' if idx == 0 else 'loading="lazy"'
            
            card_html = f'''                <a href="{post['relative_url']}" class="group">
                    <div class="space-y-3">
                        <div class="relative h-48 rounded-lg overflow-hidden border border-gray-800 group-hover:border-purple-500/50 transition-colors">
                            <img src="{post['hero']}" alt="Week {post['week']} AI portfolio performance" class="w-full h-full object-cover" width="600" height="400" sizes="(max-width: 768px) 100vw, (max-width: 1024px) 50vw, 33vw" {loading_attr} decoding="async">
                        </div>
                        <div>
                            <h3 class="font-medium group-hover:text-purple-400 transition-colors">{post['title']}</h3>
                            <p class="text-gray-400 text-sm mt-2 line-clamp-2">{post['description']}</p>
                            <div class="flex items-center gap-1 mt-3 text-xs text-gray-500">
                                <time datetime="{post['date']}">{date_display}</time>
                            </div>
                        </div>
                    </div>
                </a>'''
            cards_html.append(card_html)
        
        # Get newest hero for OG image
        og_image = f"https://quantuminvestor.net/Media/W{posts_meta[0]['week']}.webp" if posts_meta else "https://quantuminvestor.net/Media/Hero.webp"
        
        # Generate complete posts.html with nonce CSP
        csp_policy = CSP_POLICY_TEMPLATE.format(nonce=self.nonce)
        posts_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>All Posts - Quantum Investor Digest</title>
    <meta name="description" content="Browse all Quantum Investor Digest posts covering AI-managed stock portfolios, weekly performance updates, and GenAI investing insights.">
    <meta name="author" content="Michael Gavrilov">
    <meta name="theme-color" content="#000000">
    <meta http-equiv="X-Content-Type-Options" content="nosniff">
    <meta http-equiv="X-Frame-Options" content="SAMEORIGIN">
    <meta http-equiv="Content-Security-Policy" content="{csp_policy}">
    <meta name="referrer" content="strict-origin-when-cross-origin">
    <link rel="canonical" href="https://quantuminvestor.net/Posts/posts.html">
    <link rel="icon" href="../Media/favicon.ico" type="image/x-icon">
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://quantuminvestor.net/Posts/posts.html">
    <meta property="og:title" content="All Posts - Quantum Investor Digest">
    <meta property="og:description" content="Browse all Quantum Investor Digest posts covering AI-managed stock portfolios and weekly performance insights.">
    <meta property="og:image" content="{og_image}">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:site" content="@qid2025">
    <meta name="twitter:title" content="All Posts - Quantum Investor Digest">
    <meta name="twitter:description" content="Browse all AI portfolio weekly performance updates and GenAI investing insights.">
    <meta name="twitter:image" content="{og_image}">
    <link rel="stylesheet" href="../{self.stylesheet_name}">
    <script src="../js/template-loader.js" defer nonce="{self.nonce}"></script>
    <script src="../js/mobile-menu.js" defer nonce="{self.nonce}"></script>
    <script src="../js/tldr.js" defer nonce="{self.nonce}"></script>
    <script type="application/ld+json" nonce="{self.nonce}">
{json.dumps(item_list_json, indent=2)}
    </script>
    <script type="application/ld+json" nonce="{self.nonce}">
{json.dumps(breadcrumb_json, indent=2)}
    </script>
</head>
<body data-theme="{self.palette}">
    <!-- Header -->
    <div data-template="header" data-root-path="../"></div>

    <main class="container mx-auto px-4 py-12">
        <section class="mb-12">
            <h1 class="text-4xl font-bold mb-8">All Posts</h1>

            <div class="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
{chr(10).join(cards_html)}
            </div>
        </section>
    </main>

    <!-- Footer -->
    <div data-template="footer" data-root-path="../"></div>
</body>
</html>'''
        
        output_path = POSTS_DIR / "posts.html"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(posts_html)
        
        print(f"✓ Generated posts.html with {len(posts_meta)} weekly posts")
    
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
            print(f"  - Media/W{self.week_number}-card.png (snippet card)")
            print(f"  - Media/W{self.week_number}.webp (hero image)")
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
    parser.add_argument('--palette', type=str, default='default',
                        help='Palette theme to apply (default, alt). Injects data-theme attribute and enables alt CSS variables.')

    args = parser.parse_args()

    week_number = None if args.week == 'auto' else int(args.week)

    automation = PortfolioAutomation(
        week_number=week_number,
        api_key=args.api_key,
        model=args.model,
        data_source=args.data_source,
        alphavantage_key=args.alphavantage_key,
        eval_date=args.eval_date,
        palette=args.palette
    )
    automation.run()

if __name__ == '__main__':
    main()
