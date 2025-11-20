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
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential
import re
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import io
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Configure paths
REPO_ROOT = Path(__file__).parent.parent
MASTER_DATA_DIR = REPO_ROOT / "master data"  # Single source of truth: consolidated master.json
ARCHIVE_DIR = MASTER_DATA_DIR / "archive"    # Timestamped backups
DATA_DIR = REPO_ROOT / "Data"                # Legacy snapshots (backward compatibility only)
POSTS_DIR = REPO_ROOT / "Posts"
PROMPT_DIR = REPO_ROOT / "Prompt"

# CSP policy template (blog-friendly: allows CDNs, inline styles, analytics)
CSP_POLICY_TEMPLATE = (
    "default-src 'self'; "
    "script-src 'self' 'nonce-{nonce}' 'unsafe-inline' https://www.googletagmanager.com https://www.google-analytics.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://unpkg.com; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
    "img-src 'self' data: https: http:; "
    "font-src 'self' data: https://fonts.gstatic.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
    "connect-src 'self' https://www.google-analytics.com https://stats.g.doubleclick.net; "
    "frame-src 'self' https://www.youtube.com https://player.vimeo.com; "
    "frame-ancestors 'self'; "
    "base-uri 'self'; "
    "form-action 'self';"
)

class PortfolioAutomation:
    def __init__(self, week_number=None, github_token=None, model="openai/gpt-5", 
                 data_source="ai", alphavantage_key=None, marketstack_key=None, 
                 finnhub_key=None, eval_date=None, palette="default"):
        # Configuration
        self.week_number = week_number or self.detect_next_week()
        self.model = model
        self.data_source = data_source.lower()
        self.palette = palette
        self.nonce = 'qi123'
        self.stylesheet_name = 'styles.css'
        
        # API keys
        self.github_token = github_token or os.getenv('GH_TOKEN')
        self.alphavantage_key = alphavantage_key or os.getenv('ALPHAVANTAGE_API_KEY')
        self.marketstack_key = marketstack_key or os.getenv('MARKETSTACK_API_KEY')
        self.finnhub_key = finnhub_key or os.getenv('FINNHUB_API_KEY')
        
        # AI client state
        self.client = None
        self.ai_enabled = False
        self.ai_provider = 'GitHub Models'
        
        # Evaluation date
        self.eval_date = None
        
        # Configure HTTP session with retry logic
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        
        if eval_date:
            try:
                datetime.strptime(eval_date, '%Y-%m-%d')
                self.eval_date = eval_date
                logging.info(f"Using manual evaluation date override: {self.eval_date}")
            except ValueError:
                logging.warning(f"Invalid --eval-date '{eval_date}' (expected YYYY-MM-DD). Ignoring override.")

        # Initialize GitHub Models client
        if self.github_token:
            try:
                self.client = ChatCompletionsClient(
                    endpoint="https://models.github.ai/inference",
                    credential=AzureKeyCredential(self.github_token)
                )
                self.ai_enabled = True
                logging.info(f"✓ GitHub Models initialized ({self.model})")
            except Exception as e:
                logging.error(f"✗ GitHub Models failed: {e}")
        
        # Validate configuration
        if self.data_source == 'ai' and not self.ai_enabled:
            raise ValueError("AI mode requires GH_TOKEN. Use --data-source=alphavantage for data-only mode.")
        if self.data_source == 'alphavantage' and not self.alphavantage_key:
            raise ValueError("Alpha Vantage mode requires ALPHAVANTAGE_API_KEY environment variable.")
        
        # Log data source status
        if self.data_source == 'alphavantage':
            logging.info(f"✓ Alpha Vantage enabled (key: {self.alphavantage_key[:8]}...)")
        if self.finnhub_key:
            logging.info(f"✓ Finnhub fallback enabled (key: {self.finnhub_key[:8]}...)")
        if not self.ai_enabled:
            logging.warning("⚠ Data-only mode: AI narrative disabled")

        # Finnhub rate limiting: 5 requests/minute = 1 request per 12 seconds
        self.last_finnhub_call = 0  # timestamp of last Finnhub API call
        self.finnhub_min_interval = 12  # seconds between Finnhub calls

        # Load prompts
        self.prompts = self.load_prompts()

        # State storage
        self.master_json = None
        self.existing_weeks = None  # Cached week count from master.json
        self.narrative_html = None
        self.seo_json = None
        self.performance_table = None
        self.performance_chart = None
        
        # Execution report tracking
        self.report = {
            'steps': [],
            'start_time': datetime.now(),
            'week_number': self.week_number,
            'success': False
        }
    
    def detect_next_week(self):
        """Auto-detect next week number from master data file"""
        # If already loaded via load_master_json(), reuse cached value
        if self.existing_weeks is not None:
            return self.existing_weeks + 1
        
        master_path = MASTER_DATA_DIR / "master.json"
        if not master_path.exists():
            raise ValueError(f"Master data file not found: {master_path}")
        
        try:
            with open(master_path, 'r', encoding='utf-8') as f:
                master = json.load(f)
                existing_weeks = len(master.get('portfolio_history', [])) - 1  # Subtract inception
                return existing_weeks + 1  # Add 1 for next week
        except Exception as e:
            raise ValueError(f"Could not read master data: {e}")
    
    def add_step(self, name, status, description, details=None):
        """Add a step to the execution report"""
        step = {
            'name': name,
            'status': status,  # 'success', 'warning', 'error', 'skipped'
            'description': description,
            'timestamp': datetime.now().isoformat()
        }
        if details:
            step['details'] = details
        self.report['steps'].append(step)
    
    def print_report(self):
        """Print formatted execution report"""
        end_time = datetime.now()
        duration = (end_time - self.report['start_time']).total_seconds()
        
        logging.info("="*80)
        logging.info(f" AUTOMATION EXECUTION REPORT - Week {self.report['week_number']}")
        logging.info("="*80)
        logging.info(f"Started:  {self.report['start_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        logging.info(f"Finished: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logging.info(f"Duration: {duration:.1f} seconds")
        logging.info(f"Status:   {'✅ SUCCESS' if self.report['success'] else '❌ FAILED'}")
        logging.info("-"*80)
        logging.info("EXECUTION STEPS:")
        logging.info("-"*80)
        
        for i, step in enumerate(self.report['steps'], 1):
            status_icon = {
                'success': '✅',
                'warning': '⚠️',
                'error': '❌',
                'skipped': '⊘'
            }.get(step['status'], '•')
            
            logging.info(f"{i}. {status_icon} {step['name']}")
            logging.info(f"   Status: {step['status'].upper()}")
            logging.info(f"   {step['description']}")
            if 'details' in step:
                for key, value in step['details'].items():
                    logging.info(f"   {key}: {value}")
        
        logging.info("="*80)
        
        # Summary counts
        success_count = sum(1 for s in self.report['steps'] if s['status'] == 'success')
        warning_count = sum(1 for s in self.report['steps'] if s['status'] == 'warning')
        error_count = sum(1 for s in self.report['steps'] if s['status'] == 'error')
        
        logging.info(f"SUMMARY: {success_count} succeeded, {warning_count} warnings, {error_count} errors")
        logging.info("="*80)
    
    def load_prompts(self):
        """Load all prompt markdown files (A, B, C, D)"""
        prompts = {}
        missing = []
        for letter in ['A', 'B', 'C', 'D']:
            prompt_file = PROMPT_DIR / f"Prompt-{letter}-v5.4{letter}.md"
            if prompt_file.exists():
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    prompts[letter] = f.read()
            else:
                logging.warning(f"{prompt_file.name} not found")
                prompts[letter] = f"# Prompt {letter} (placeholder)"
                missing.append(letter)
        
        if missing:
            self.add_step("Load Prompts", "warning", 
                         f"Loaded prompts but {len(missing)} file(s) missing",
                         {'missing_prompts': ', '.join([f"Prompt-{l}" for l in missing])})
        else:
            self.add_step("Load Prompts", "success", 
                         "All 4 prompt files loaded successfully")
        
        return prompts
    
    def load_master_json(self):
        """Load consolidated master.json (single source of truth)"""
        master_path = MASTER_DATA_DIR / "master.json"
        if not master_path.exists():
            self.add_step("Load Master Data", "error", 
                         f"Master data file not found at {master_path}")
            raise ValueError(f"Master data file not found: {master_path}")
        
        try:
            with open(master_path, 'r', encoding='utf-8') as f:
                self.master_json = json.load(f)
            
            self.existing_weeks = len(self.master_json.get('portfolio_history', [])) - 1  # Subtract inception
            logging.info(f"Loaded consolidated master.json ({self.existing_weeks} weeks + inception): {master_path}")
            
            self.add_step("Load Master Data", "success", 
                         f"Loaded master.json with {self.existing_weeks} completed weeks",
                         {'file_path': str(master_path)})
            
            return self.master_json
        except json.JSONDecodeError as e:
            self.add_step("Load Master Data", "error", 
                         f"Invalid JSON format in master.json: {str(e)}")
            raise
        except Exception as e:
            self.add_step("Load Master Data", "error", 
                         f"Failed to load master.json: {str(e)}")
            raise
    
    def call_ai(self, system_prompt, user_message, temperature=0.7):
        """Call GitHub Models AI API"""
        if not self.client:
            raise ValueError("AI client not initialized. Set GH_TOKEN environment variable.")
        
        try:
            response = self.client.complete(
                messages=[
                    SystemMessage(system_prompt),
                    UserMessage(user_message)
                ],
                model=self.model,
                temperature=temperature
            )
            logging.info(f"✓ AI response received ({self.model})")
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f"✗ AI call failed: {e}")
            raise
    
    def _purge_and_minify_css(self):
        """CSS optimization (placeholder - not critical for MVP)"""
        logging.warning("CSS minification not implemented (using original styles.css)")
        pass
    
    def run_prompt_a(self):
        """Prompt A: Data Engine - Update master.json with new week's data"""
        logging.info("Running Prompt A: Data Engine...")
        
        try:
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
            
            response = self.call_ai(system_prompt, user_message)
            
            # Extract JSON from response
            json_match = re.search(r'```json\s*({.*?})\s*```', response, re.DOTALL)
            if json_match:
                self.master_json = json.loads(json_match.group(1))
            else:
                # Try to parse entire response as JSON
                try:
                    self.master_json = json.loads(response)
                except json.JSONDecodeError:
                    self.add_step("Prompt A - Data Engine", "error", 
                                 "AI response did not contain valid JSON format")
                    raise ValueError("Prompt A did not return valid JSON. Check response format.")
            
            # Enforce evaluation date override if set
            if self.eval_date and self.master_json.get('meta', {}).get('current_date') != self.eval_date:
                self.master_json['meta']['current_date'] = self.eval_date

            # Save to consolidated master data (primary location) - atomic write
            MASTER_DATA_DIR.mkdir(exist_ok=True)
            master_path = MASTER_DATA_DIR / "master.json"
            temp_path = master_path.with_suffix('.tmp')
            try:
                with open(temp_path, 'w') as f:
                    json.dump(self.master_json, f, indent=2)
                temp_path.replace(master_path)  # Atomic on POSIX, near-atomic on Windows
            except Exception as e:
                if temp_path.exists():
                    temp_path.unlink()
                raise
            
            # Archive timestamped backup
            ARCHIVE_DIR.mkdir(exist_ok=True)
            eval_date = self.master_json['meta']['current_date'].replace('-', '')
            archive_path = ARCHIVE_DIR / f"master-{eval_date}.json"
            with open(archive_path, 'w') as f:
                json.dump(self.master_json, f, indent=2)
            
            # Optional: Legacy week snapshot (backward compatibility)
            current_week_dir = DATA_DIR / f"W{self.week_number}"
            current_week_dir.mkdir(exist_ok=True)
            legacy_path = current_week_dir / "master.json"
            with open(legacy_path, 'w') as f:
                json.dump(self.master_json, f, indent=2)
            
            logging.info(f"Prompt A completed for Week {self.week_number}")
            logging.info(f"  → Primary: {master_path}")
            logging.info(f"  → Archive: {archive_path}")
            logging.info(f"  → Legacy:  {legacy_path} (optional)")
            
            self.add_step("Prompt A - Data Engine", "success", 
                         f"Updated master.json with Week {self.week_number} data",
                         {'primary_file': str(master_path), 'archive_file': str(archive_path)})
            
            # Generate media assets
            self._generate_media_assets()
            
            return self.master_json
            
        except Exception as e:
            self.add_step("Prompt A - Data Engine", "error", 
                         f"Prompt A execution failed: {str(e)}")
            raise
    
    def _generate_media_assets(self):
        """Generate hero image with error handling."""
        try:
            self.generate_hero_image()
        except Exception as e:
            logging.error(f"Hero image generation failed: {e}")
            self.add_step("Generate Hero Image", "error", 
                         f"Failed to generate hero image: {str(e)}")

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
        Returns dict with date, close price, and source, or None on failure.
        """
        url = 'https://www.alphavantage.co/query'
        params = {
            'function': 'GLOBAL_QUOTE',
            'symbol': symbol,
            'apikey': self.alphavantage_key
        }
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if 'Global Quote' in data and data['Global Quote']:
                quote = data['Global Quote']
                # Validate date format
                date_str = quote.get('07. latest trading day', '')
                try:
                    datetime.strptime(date_str, '%Y-%m-%d')
                    date_clean = date_str
                except ValueError:
                    date_clean = self._latest_market_date()
                    logging.warning(f"Invalid date format from Alpha Vantage for {symbol}, using fallback: {date_clean}")
                
                return {
                    'date': date_clean,
                    'close': float(quote.get('05. price', 0)),
                    'source': 'Alpha Vantage'
                }
            elif 'Note' in data:
                logging.warning(f"Rate limit hit for {symbol}: {data['Note']}")
                return None
            else:
                logging.warning(f"No data returned for {symbol}")
                return None
        except Exception as e:
            logging.warning(f"Failed to fetch {symbol}: {e}")
            return None

    def _fetch_alphavantage_crypto(self, symbol, to_currency='USD'):
        """Fetch crypto price from Alpha Vantage crypto endpoint.
        Returns dict with date, close price, and source, or None on failure.
        """
        url = 'https://www.alphavantage.co/query'
        params = {
            'function': 'CURRENCY_EXCHANGE_RATE',
            'from_currency': symbol,
            'to_currency': to_currency,
            'apikey': self.alphavantage_key
        }
        try:
            response = self.session.get(url, params=params, timeout=10)
            data = response.json()
            if 'Realtime Currency Exchange Rate' in data:
                rate = data['Realtime Currency Exchange Rate']
                # Validate date format
                date_str = rate.get('6. Last Refreshed', '')
                try:
                    date_obj = datetime.strptime(date_str[:10], '%Y-%m-%d')
                    date_clean = date_obj.strftime('%Y-%m-%d')
                except (ValueError, IndexError):
                    date_clean = self._latest_market_date()
                    logging.warning(f"Invalid date format from Alpha Vantage crypto for {symbol}, using fallback: {date_clean}")
                
                return {
                    'date': date_clean,
                    'close': float(rate.get('5. Exchange Rate', 0)),
                    'source': 'Alpha Vantage (Crypto)'
                }
            else:
                logging.warning(f"No crypto data returned for {symbol}")
                return None
        except Exception as e:
            logging.warning(f"Failed to fetch crypto {symbol}: {e}")
            return None

    def _fetch_marketstack_quote(self, symbol):
        """Fetch latest quote for a symbol from Marketstack.
        Returns dict with date, close price, and source, or None on failure.
        """
        if not self.marketstack_key:
            return None
        
        url = 'http://api.marketstack.com/v1/eod/latest'
        params = {
            'access_key': self.marketstack_key,
            'symbols': symbol
        }
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if 'data' in data and data['data'] and len(data['data']) > 0:
                quote = data['data'][0]
                # Validate date format
                date_str = quote.get('date', '')
                try:
                    # Validate it's a proper date and extract YYYY-MM-DD
                    date_obj = datetime.strptime(date_str[:10], '%Y-%m-%d')
                    date_clean = date_obj.strftime('%Y-%m-%d')
                except (ValueError, IndexError):
                    # Fallback to current market date
                    date_clean = self._latest_market_date()
                    logging.warning(f"Invalid date format from Marketstack for {symbol}, using fallback: {date_clean}")
                
                return {
                    'date': date_clean,
                    'close': float(quote.get('close', 0)),
                    'source': 'Marketstack'
                }
            else:
                logging.warning(f"No data returned from Marketstack for {symbol}")
                return None
        except Exception as e:
            logging.warning(f"Failed to fetch {symbol} from Marketstack: {e}")
            return None

    # ===================== FINNHUB DATA FETCHERS =====================
    def _fetch_finnhub_quote(self, symbol):
        """Fetch latest quote for a stock/ETF from Finnhub.
        Returns dict with date, close price, and source, or None on failure.
        """
        if not self.finnhub_key:
            return None
        
        # Rate limit: 5 req/min = 12 seconds between calls
        elapsed = time.time() - self.last_finnhub_call
        if elapsed < self.finnhub_min_interval:
            wait_time = self.finnhub_min_interval - elapsed
            logging.debug(f"Finnhub rate limit: waiting {wait_time:.1f}s before request")
            time.sleep(wait_time)
        
        url = 'https://finnhub.io/api/v1/quote'
        params = {
            'symbol': symbol,
            'token': self.finnhub_key
        }
        try:
            self.last_finnhub_call = time.time()  # Update timestamp before request
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            # Finnhub returns fields: c (current), pc (prev close), t (timestamp)
            if 'c' in data and data.get('c') not in (None, 0):
                ts = data.get('t')
                try:
                    date_clean = datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d') if ts else self._latest_market_date()
                except Exception:
                    date_clean = self._latest_market_date()
                return {
                    'date': date_clean,
                    'close': float(data.get('c', 0)),
                    'source': 'Finnhub'
                }
            else:
                logging.warning(f"Finnhub returned no usable quote for {symbol}")
                return None
        except Exception as e:
            logging.warning(f"Finnhub fetch failed for {symbol}: {e}")
            return None

    def _fetch_finnhub_crypto(self, symbol):
        """Fetch latest crypto price (BTC) from Finnhub (using BINANCE:BTCUSDT)."""
        if not self.finnhub_key:
            return None
        
        # Rate limit: 5 req/min = 12 seconds between calls
        elapsed = time.time() - self.last_finnhub_call
        if elapsed < self.finnhub_min_interval:
            wait_time = self.finnhub_min_interval - elapsed
            logging.debug(f"Finnhub rate limit: waiting {wait_time:.1f}s before crypto request")
            time.sleep(wait_time)
        
        # Map generic 'BTC' symbol to Finnhub crypto symbol
        finnhub_symbol = 'BINANCE:BTCUSDT' if symbol.upper() == 'BTC' else symbol
        url = 'https://finnhub.io/api/v1/quote'
        params = {
            'symbol': finnhub_symbol,
            'token': self.finnhub_key
        }
        try:
            self.last_finnhub_call = time.time()  # Update timestamp before request
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            if 'c' in data and data.get('c') not in (None, 0):
                ts = data.get('t')
                try:
                    date_clean = datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d') if ts else self._latest_market_date()
                except Exception:
                    date_clean = self._latest_market_date()
                return {
                    'date': date_clean,
                    'close': float(data.get('c', 0)),
                    'source': 'Finnhub (Crypto)'
                }
            else:
                logging.warning(f"Finnhub returned no usable crypto quote for {symbol}")
                return None
        except Exception as e:
            logging.warning(f"Finnhub crypto fetch failed for {symbol}: {e}")
            return None

    def generate_master_from_alphavantage(self):
        """Generate new week's master.json using Alpha Vantage API.
        Uses previous week's master.json as baseline, fetches latest prices,
        recalculates weekly and total pct changes, benchmarks, portfolio history.
        """
        logging.info("Running Alpha Vantage data engine (replacing Prompt A)...")
        if self.master_json is None:
            raise ValueError("Previous master.json must be loaded before fetching new data.")

        prev_date = self.master_json['meta']['current_date']
        inception_date = self.master_json['meta']['inception_date']
        inception_value = self.master_json['meta']['inception_value']
        new_date = self.eval_date if self.eval_date else self._latest_market_date()
        prev_portfolio_value = self.master_json['portfolio_history'][-1]['value']

        # Avoid duplicate regeneration
        if new_date == prev_date:
            error_msg = f"Evaluation date {new_date} equals previous date. Cannot generate duplicate weekly update."
            logging.error(error_msg)
            raise ValueError(error_msg)

        tickers = [s['ticker'] for s in self.master_json['stocks']]
        logging.info(f"Fetching prices for {len(tickers)} stocks + 2 benchmarks (Alpha Vantage API)")
        logging.info("Rate limiting: 5 requests/minute (12 sec between calls)...")

        # Fetch stock prices with rate limiting (5 req/min = 12 sec between calls for Alpha Vantage)
        price_data = {}
        price_sources = {}  # Track source for each symbol
        for i, ticker in enumerate(tickers, 1):
            logging.info(f"→ [{i}/{len(tickers)}] Fetching {ticker}...")
            used_alphavantage = False
            
            quote = self._fetch_alphavantage_quote(ticker)
            if quote:
                used_alphavantage = True
            else:
                # Retry with delay
                logging.info(f"  ⟳ Retry attempt for {ticker}...")
                time.sleep(5)
                quote = self._fetch_alphavantage_quote(ticker)
                if quote:
                    used_alphavantage = True
            
            # Finnhub fallback (before Marketstack)
            if not quote and self.finnhub_key:
                logging.info(f"  ⟳ Trying Finnhub for {ticker}...")
                quote = self._fetch_finnhub_quote(ticker)
                if quote:
                    used_alphavantage = False
                    logging.info(f"  → Finnhub price acquired for {ticker}: {quote['close']}")

            if not quote and self.marketstack_key:
                # Fallback to Marketstack
                logging.info(f"  ⟳ Trying Marketstack for {ticker}...")
                quote = self._fetch_marketstack_quote(ticker)
                if quote:
                    used_alphavantage = False  # Track that we used Marketstack
            
            if quote:
                price_data[ticker] = quote
                price_sources[ticker] = quote.get('source', 'Unknown')
            else:
                # Critical failure - cannot proceed without current prices
                raise ValueError(f"Failed to fetch price for {ticker} from all sources. Cannot generate accurate portfolio data.")
            
            # Rate limiting (skip on last item)
            if i < len(tickers):
                if used_alphavantage:
                    time.sleep(12)  # Alpha Vantage: 5 req/min
                elif quote and quote.get('source') == 'Marketstack':
                    time.sleep(2)   # Marketstack: lighter rate limit

        # Build updated stocks list
        updated_stocks = []
        for stock in self.master_json['stocks']:
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

        # Benchmarks: Fetch based on configuration from master.json
        logging.info("Fetching benchmarks...")
        bench_data = {}
        bench_sources = {}  # Track source for each benchmark
        
        # Extract benchmark config from master.json
        bench_config = self.master_json.get('benchmarks', {})
        
        for bench_key in bench_config.keys():
            # Derive symbol and type from benchmark key or use defaults
            # Expected: sp500 -> SPY (stock), bitcoin -> BTC (crypto)
            if bench_key == 'sp500':
                symbol = 'SPY'
                bench_type = 'stock'
            elif bench_key == 'bitcoin':
                symbol = 'BTC'
                bench_type = 'crypto'
            else:
                # Future-proof: try to derive from key name
                symbol = bench_key.upper()
                bench_type = 'stock'  # Default to stock
            
            logging.info(f"Fetching {bench_key.upper()} ({symbol}, type: {bench_type})...")
            
            if bench_type == 'crypto':
                # Alpha Vantage first
                quote = self._fetch_alphavantage_crypto(symbol, to_currency='USD')
                # Finnhub fallback
                if not quote and self.finnhub_key:
                    logging.info(f"Trying Finnhub crypto for {bench_key.upper()}...")
                    quote = self._fetch_finnhub_crypto(symbol)
                if not quote:
                    raise ValueError(f"Failed to fetch {bench_key.upper()} ({symbol}) crypto price from Alpha Vantage/Finnhub.")
            else:
                # Use regular stock quote with fallback
                quote = self._fetch_alphavantage_quote(symbol)
                if not quote and self.finnhub_key:
                    logging.info(f"Trying Finnhub for benchmark {bench_key.upper()}...")
                    quote = self._fetch_finnhub_quote(symbol)
                if not quote and self.marketstack_key:
                    logging.info(f"Trying Marketstack for {bench_key.upper()}...")
                    quote = self._fetch_marketstack_quote(symbol)
                
                if not quote:
                    raise ValueError(f"Failed to fetch {bench_key.upper()} ({symbol}) price from all sources. Cannot generate accurate portfolio data.")
            
            bench_data[bench_key] = quote
            bench_sources[bench_key] = quote.get('source', 'Unknown')
            
            # Rate limiting based on source
            if quote.get('source') == 'Marketstack':
                time.sleep(2)   # Marketstack: 2 sec delay
            else:
                time.sleep(12)  # Alpha Vantage: 12 sec delay

        # Update benchmarks
        updated_benchmarks = {}
        for bench_key, series in self.master_json['benchmarks'].items():
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
        updated_portfolio_history = self.master_json['portfolio_history'] + [new_history_entry]

        # Normalized chart entry
        spx_first_ref = self.master_json['benchmarks']['sp500']['inception_reference']
        btc_first_ref = self.master_json['benchmarks']['bitcoin']['inception_reference']
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
                "portfolio_name": self.master_json['meta']['portfolio_name'],
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
            "normalized_chart": self.master_json['normalized_chart'] + [normalized_entry]
        }

        # Save to consolidated master data (primary location) - atomic write
        MASTER_DATA_DIR.mkdir(exist_ok=True)
        master_path = MASTER_DATA_DIR / "master.json"
        temp_path = master_path.with_suffix('.tmp')
        try:
            with open(temp_path, 'w') as f:
                json.dump(updated_master, f, indent=2)
            temp_path.replace(master_path)  # Atomic on POSIX, near-atomic on Windows
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise

        # Archive timestamped backup
        ARCHIVE_DIR.mkdir(exist_ok=True)
        archive_path = ARCHIVE_DIR / f"master-{new_date.replace('-', '')}.json"
        with open(archive_path, 'w') as f:
            json.dump(updated_master, f, indent=2)

        # Optional: Legacy week snapshot (backward compatibility)
        current_week_dir = DATA_DIR / f"W{self.week_number}"
        current_week_dir.mkdir(exist_ok=True)
        legacy_path = current_week_dir / "master.json"
        with open(legacy_path, 'w') as f:
            json.dump(updated_master, f, indent=2)

        self.master_json = updated_master
        
        # Build detailed price report
        price_report = {}
        for ticker in tickers:
            price_report[ticker] = {
                'price': f"${price_data[ticker]['close']:.2f}",
                'date': price_data[ticker]['date'],
                'source': price_sources.get(ticker, 'Unknown')
            }
        price_report['SPX (S&P 500)'] = {
            'price': f"${bench_data['sp500']['close']:.2f}",
            'date': bench_data['sp500']['date'],
            'source': bench_sources.get('sp500', 'Unknown')
        }
        price_report['BTC (Bitcoin)'] = {
            'price': f"${bench_data['bitcoin']['close']:.2f}",
            'date': bench_data['bitcoin']['date'],
            'source': bench_sources.get('bitcoin', 'Unknown')
        }
        
        self.add_step("Fetch Market Prices", "success",
                     f"Fetched prices for {len(tickers)} stocks + 2 benchmarks",
                     {'prices': price_report})
        
        logging.info(f"Alpha Vantage data engine completed for Week {self.week_number}")
        logging.info(f"  → Primary: {master_path}")
        logging.info(f"  → Archive: {archive_path}")
        logging.info(f"  → Legacy:  {legacy_path} (optional)")
        
        # Generate media assets
        self._generate_media_assets()
        return updated_master

    # ===================== HERO IMAGE GENERATION (Remote + Overlay) =====================
    def _font(self, size: int):
        candidates = [
            Path("C:/Windows/Fonts/SegoeUI-Semibold.ttf"),
            Path("C:/Windows/Fonts/SegoeUI.ttf"),
            Path("C:/Windows/Fonts/Arial.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
        ]
        face = next((str(c) for c in candidates if c.exists()), "Arial")
        try:
            return ImageFont.truetype(face, size=size)
        except Exception:
            return ImageFont.load_default()

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
                resp = self.session.get('https://api.pexels.com/v1/search', headers={'Authorization': key}, params={'query': q, 'orientation': 'landscape', 'per_page': 3}, timeout=10)
                if resp.status_code != 200: return None
                data = resp.json().get('photos', [])
                for p in data:
                    src = p.get('src', {}).get('large') or p.get('src', {}).get('original')
                    if src:
                        img_resp = self.session.get(src, timeout=15)
                        if img_resp.status_code == 200:
                            return Image.open(io.BytesIO(img_resp.content)).convert('RGBA')
            except Exception:
                return None
            return None
        def fetch_pixabay(q: str):
            key = os.getenv('PIXABAY_API_KEY');
            if not key: return None
            try:
                resp = self.session.get('https://pixabay.com/api/', params={'key': key, 'q': q, 'image_type': 'photo', 'orientation': 'horizontal', 'per_page': 3, 'safesearch': 'true'}, timeout=10)
                if resp.status_code != 200: return None
                hits = resp.json().get('hits', [])
                for h in hits:
                    src = h.get('largeImageURL') or h.get('webformatURL')
                    if src:
                        img_resp = self.session.get(src, timeout=15)
                        if img_resp.status_code == 200:
                            return Image.open(io.BytesIO(img_resp.content)).convert('RGBA')
            except Exception:
                return None
            return None
        def fetch_lummi(q: str):
            # Placeholder for future API
            return None

        providers = [
            ('Pexels', fetch_pexels),
            ('Pixabay', fetch_pixabay),
            ('Lummi', fetch_lummi)
        ]
        remote = None
        image_source = None
        for source_name, provider in providers:
            remote = provider(query)
            if remote:
                image_source = source_name
                logging.info(f"Using image from {source_name}")
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
            source_note = image_source or 'remote'
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
        try:
            out_path = REPO_ROOT / 'Media' / f"W{self.week_number}.webp"
            out_path.parent.mkdir(exist_ok=True)
            img.convert('RGB').save(out_path, format='WEBP', quality=90)
            logging.info(f"Hero image generated: {out_path} ({source_note})")
            self.add_step("Generate Hero Image", "success", 
                         f"Created 1200x800 hero image ({source_note})",
                         {'output_file': str(out_path), 'image_source': source_note})
        except Exception as e:
            self.add_step("Generate Hero Image", "error", 
                         f"Failed to save hero image: {str(e)}")
            raise
    
    def run_prompt_b(self):
        """Prompt B: Narrative Writer - Generate HTML content"""
        logging.info("Running Prompt B: Narrative Writer...")
        
        try:
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
            
            response = self.call_ai(system_prompt, user_message)
            
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
                    self.add_step("Prompt B - Narrative Writer", "error", 
                                 "Could not extract narrative HTML from AI response")
                    raise ValueError("Could not extract narrative HTML from Prompt B response")
            
            # Extract SEO JSON
            seo_status = "success"
            json_match = re.search(r'```json\s*({.*?})\s*```', response, re.DOTALL)
            if json_match:
                try:
                    self.seo_json = json.loads(json_match.group(1))
                except json.JSONDecodeError as e:
                    logging.warning(f"Failed to parse SEO JSON: {e}")
                    self.seo_json = self.generate_fallback_seo()
                    seo_status = "warning"
            else:
                logging.warning("No SEO JSON found, generating fallback")
                self.seo_json = self.generate_fallback_seo()
                seo_status = "warning"
            
            logging.info("Prompt B completed - narrative and SEO generated")
            
            self.add_step("Prompt B - Narrative Writer", seo_status, 
                         "Generated narrative HTML and SEO metadata",
                         {'narrative_length': f"{len(self.narrative_html)} chars",
                          'seo_metadata': 'extracted' if seo_status == 'success' else 'fallback used'})
            
            return self.narrative_html, self.seo_json
            
        except Exception as e:
            self.add_step("Prompt B - Narrative Writer", "error", 
                         f"Prompt B execution failed: {str(e)}")
            raise
    
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
        
        # AI provider metadata
        ai_model_info = f"{self.ai_provider}: {self.model}" if self.ai_provider else "Data-only mode"
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
  <meta name=\"author\" content=\"Michael Gavrilov\">
  <meta name=\"generator\" content=\"Portfolio Automation - {ai_model_info}\">
  <meta name=\"theme-color\" content=\"#000000\">
  <meta http-equiv=\"Content-Security-Policy\" content=\"{csp_policy}\">
  <meta name=\"referrer\" content=\"strict-origin-when-cross-origin\">
  <link rel=\"canonical\" href=\"{canonical}\">
  <link rel=\"icon\" href=\"../Media/favicon.ico\" type=\"image/x-icon\">
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
  <link rel=\"stylesheet\" href=\"../{self.stylesheet_name}\">
  <script src=\"../js/template-loader.js\" defer nonce=\"{self.nonce}\"></script>
  <script src=\"../js/mobile-menu.js\" defer nonce=\"{self.nonce}\"></script>
  <script src=\"../js/tldr.js\" defer nonce=\"{self.nonce}\"></script>
    <!-- Component styles moved to global stylesheet -->
    <script type=\"application/ld+json\">{json.dumps(blog_ld, separators=(',',':'))}</script>
    <script type=\"application/ld+json\">{json.dumps(breadcrumbs_ld, separators=(',',':'))}</script>
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
                logging.warning(f"Static file not found: {fp}")
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
                logging.info(f"Hardened static page: {fp.name}")
            except Exception as e:
                logging.warning(f"Failed hardening {fp.name}: {e}")
    
    def run_prompt_c(self):
        """Prompt C: Visual Generator - Create table and chart"""
        logging.info("Running Prompt C: Visual Generator...")
        
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
        
        try:
            response = self.call_ai(system_prompt, user_message)
            
            table_status = "success"
            chart_status = "success"
            
            # Extract table HTML (including nested divs and table)
            table_match = re.search(r'<div class="myblock-performance-snapshot">.*?</table>\s*</div>', response, re.DOTALL)
            if table_match:
                self.performance_table = table_match.group(0)
            else:
                logging.warning("Could not extract performance table from Prompt C response")
                self.performance_table = "<!-- Performance table not generated -->"
                table_status = "warning"
            
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
                logging.warning("Could not extract performance chart from Prompt C response")
                self.performance_chart = "<!-- Performance chart not generated -->"
                chart_status = "warning"
            
            logging.info("Prompt C completed - visuals generated")
            
            overall_status = "success" if table_status == "success" and chart_status == "success" else "warning"
            self.add_step("Prompt C - Visual Generator", overall_status, 
                         "Generated performance table and chart",
                         {'table': table_status, 'chart': chart_status})
            
        except Exception as e:
            self.add_step("Prompt C - Visual Generator", "error", 
                         f"Prompt C execution failed: {str(e)}")
            raise
    
    def run_prompt_d(self):
        """Prompt D: Final Assembler - Create complete HTML page"""
        logging.info("Running Prompt D: Final HTML Assembler...")
        
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
                logging.warning("Could not find Performance Snapshot insertion point")
        
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
                logging.warning("Could not find Performance Since Inception insertion point")
        
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
        
        response = self.call_ai(system_prompt, user_message, temperature=0.2)
        
        # Extract final HTML
        html_match = re.search(r'<!DOCTYPE html>.*</html>', response, re.DOTALL | re.IGNORECASE)
        final_html = html_match.group(0) if html_match else response

        # ================= STANDARD META HEAD REPLACEMENT =================
        try:
            final_html = self._apply_standard_head(final_html)
        except Exception as e:
            logging.warning(f"Standard head template failed: {e}")

        # ================= TLDR STRUCTURAL INJECTION (simplified, external script populates) =================
        try:
            # Remove accidental duplicate TLDR blocks leaving only first occurrence
            occurrences = [m.start() for m in re.finditer(r'id="tldrStrip"', final_html)]
            if len(occurrences) > 1:
                # Keep first, strip others
                final_html = re.sub(r'<!-- TLDR STRIP.*?<div id="tldrStrip"[\s\S]*?</div>\s*', '', final_html, count=len(occurrences)-1, flags=re.IGNORECASE)
            if 'id="tldrStrip"' not in final_html:
                tldr_markup = (
                    '\n            <!-- TLDR STRIP (Sandbox Style) -->\n'
                    '            <div id="tldrStrip" class="tldr-strip mb-10" aria-label="Weekly summary strip">\n'
                    '              <div class="tldr-metric"><span>Week Change</span><span id="tldrWeek">--</span></div>\n'
                    '              <div class="tldr-metric"><span>Since Inception</span><span id="tldrTotal">--</span></div>\n'
                    '              <div class="tldr-metric"><span>Alpha vs SPX (Total)</span><span id="tldrAlpha">--</span></div>\n'
                    '            </div>\n'
                )
                prose_pos = final_html.find('<div class="prose')
                if prose_pos != -1:
                    final_html = final_html[:prose_pos] + tldr_markup + final_html[prose_pos:]
        except Exception as e:
            logging.warning(f"TLDR structural injection failed: {e}")
        
        # Basic validation
        if not final_html.strip().startswith('<!DOCTYPE'):
            logging.warning("Generated HTML doesn't start with DOCTYPE")
        if '</html>' not in final_html.lower():
            logging.warning("Generated HTML doesn't have closing </html> tag")
        
        # Check for required elements
        required_elements = ['<head>', '<body>', '<article>', 'class="prose']
        missing = [elem for elem in required_elements if elem not in final_html]
        if missing:
            logging.warning(f"Missing expected elements: {', '.join(missing)}")
        
        # ================= PERFORMANCE OPTIMIZATION =================
        try:
            final_html = self._optimize_performance(final_html)
        except Exception as e:
            logging.warning(f"Performance optimization failed: {e}")

        # Save to Posts folder
        try:
            output_path = POSTS_DIR / f"GenAi-Managed-Stocks-Portfolio-Week-{self.week_number}.html"
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(final_html)
            
            logging.info(f"Prompt D completed - {output_path.name} created ({len(final_html)} bytes)")
            
            # Validation warnings
            warnings = []
            if not final_html.strip().startswith('<!DOCTYPE'):
                warnings.append("missing DOCTYPE")
            if '</html>' not in final_html.lower():
                warnings.append("missing </html>")
            required_elements = ['<head>', '<body>', '<article>', 'class="prose']
            missing = [elem for elem in required_elements if elem not in final_html]
            if missing:
                warnings.extend(missing)
            
            status = "warning" if warnings else "success"
            details = {'output_file': str(output_path), 'file_size': f"{len(final_html)} bytes"}
            if warnings:
                details['validation_warnings'] = ', '.join(warnings)
            
            self.add_step("Prompt D - Final Assembler", status, 
                         "Generated complete HTML page for Week post",
                         details)
            
            return final_html
            
        except Exception as e:
            self.add_step("Prompt D - Final Assembler", "error", 
                         f"Failed to save final HTML: {str(e)}")
            raise

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
        logging.info("Regenerating posts.html listing...")
        self._regenerate_posts_listing()
        logging.info("posts.html regenerated with current weekly posts")
    
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
        
        logging.info(f"Generated posts.html with {len(posts_meta)} weekly posts")
    
    def run(self):
        """Execute full pipeline"""
        logging.info("="*60)
        logging.info(f"GenAi Chosen Portfolio - Week {self.week_number} Automation")
        logging.info("="*60)

        try:
            self.load_master_json()
            
            # Data acquisition: AI or Alpha Vantage (MUST succeed or abort)
            if self.data_source == 'alphavantage':
                updated_master = self.generate_master_from_alphavantage()
                if not updated_master:
                    raise ValueError("Alpha Vantage data engine failed to generate updated master.json")
            else:
                updated_master = self.run_prompt_a()
                if not updated_master:
                    raise ValueError("Prompt A (AI data engine) failed to generate updated master.json")
            
            # Narrative generation (only proceeds if data acquisition succeeded)
            if self.ai_enabled:
                # All-or-nothing: generate content first, write file only if successful
                self.run_prompt_b()
                if not self.narrative_html:
                    raise ValueError("Prompt B failed to generate narrative HTML")
                self.run_prompt_c()
                if not self.performance_table or not self.performance_chart:
                    raise ValueError("Prompt C failed to generate visuals")
                self.run_prompt_d()
                # If we reached here, all prompts succeeded and file was written
            else:
                # No AI available - fail fast, don't create incomplete output
                error_msg = "AI client not initialized. Cannot generate weekly post without GitHub token."
                self.add_step("Generate Weekly Post", "error", error_msg)
                raise ValueError(error_msg)

            try:
                self.update_index_pages()
                self.add_step("Update Index Pages", "success", 
                             "Regenerated posts.html with updated listing")
            except Exception as e:
                self.add_step("Update Index Pages", "warning", 
                             f"Failed to update index pages: {str(e)}")

            # Mark overall success
            self.report['success'] = True
            
            logging.info("="*60)
            logging.info(f"✅ SUCCESS! Week {self.week_number} generated")
            logging.info("="*60)
            logging.info("Generated files:")
            logging.info("  PRIMARY:")
            logging.info(f"    • master data/master.json (consolidated, Week {self.week_number} appended)")
            logging.info(f"    • Posts/GenAi-Managed-Stocks-Portfolio-Week-{self.week_number}.html")
            logging.info("  ASSETS:")
            logging.info(f"    • Media/W{self.week_number}.webp (hero image)")
            logging.info("  BACKUPS:")
            logging.info(f"    • master data/archive/master-{self.master_json['meta']['current_date'].replace('-', '')}.json")
            logging.info(f"    • Data/W{self.week_number}/master.json (legacy compatibility)")
            if not self.ai_enabled:
                logging.info("  NOTE: Data-only mode (enable GH_TOKEN for full narrative)")
            
            # Print detailed execution report
            self.print_report()
            
        except Exception as e:
            self.report['success'] = False
            logging.error(f"ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # Print report even on failure
            self.print_report()
            sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='Automate weekly portfolio update')
    parser.add_argument('--week', type=str, default='auto', 
                       help='Week number (default: auto-detect next week)')
    parser.add_argument('--github-token', type=str, 
                       help='GitHub Personal Access Token (default: read from GH_TOKEN env var)')
    parser.add_argument('--model', type=str, default='openai/gpt-5',
                       help='AI model to use (default: openai/gpt-5 via GitHub Models)')
    parser.add_argument('--data-source', type=str, choices=['ai', 'alphavantage'], default='ai',
                       help='Data source: ai (Prompt A via AI) or alphavantage (Alpha Vantage API)')
    parser.add_argument('--alphavantage-key', type=str,
                       help='Alpha Vantage API key (default: read from ALPHAVANTAGE_API_KEY env var)')
    parser.add_argument('--marketstack-key', type=str,
                       help='Marketstack API key (default: read from MARKETSTACK_API_KEY env var)')
    parser.add_argument('--finnhub-key', type=str,
                       help='Finnhub API key (default: read from FINNHUB_API_KEY env var)')
    parser.add_argument('--eval-date', type=str,
                        help='Manual override for evaluation date (YYYY-MM-DD). Uses this as current_date for week update.')
    parser.add_argument('--palette', type=str, default='default',
                        help='Palette theme to apply (default, alt). Injects data-theme attribute and enables alt CSS variables.')

    args = parser.parse_args()

    week_number = None if args.week == 'auto' else int(args.week)

    automation = PortfolioAutomation(
        week_number=week_number,
        github_token=args.github_token,
        model=args.model,
        data_source=args.data_source,
        alphavantage_key=args.alphavantage_key,
        marketstack_key=args.marketstack_key,
        finnhub_key=args.finnhub_key,
        eval_date=args.eval_date,
        palette=args.palette
    )
    automation.run()

if __name__ == '__main__':
    main()
