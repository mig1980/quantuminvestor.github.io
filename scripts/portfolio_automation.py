#!/usr/bin/env python3
"""
GenAi Chosen Portfolio - Weekly Automation Script

Workflow:
1. Fetch prices from APIs (Alpha Vantage, Marketstack, Finnhub)
2. Calculate all metrics (stocks, portfolio, benchmarks, normalized chart)
3. Generate visual components (performance table and chart) using Python
4. Optional: Validate calculations (Prompt A)
5. Generate narrative content (Prompt B)
6. Assemble final HTML page (Prompt D)

Note: Prompt C eliminated - visual generation now handled by deterministic Python code

Error Handling Strategy:
- FATAL ERRORS (raise ValueError): Missing data, failed calculations, critical API failures
  → These abort the entire pipeline as the script cannot proceed
- NON-FATAL ERRORS (return dict): Optional validation (Prompt A)
  → Returns {'status': 'pass|fail|error', 'report': str} to allow graceful degradation
- TRANSIENT ERRORS (retry with backoff): Network timeouts, rate limits
  → Handled in call_ai() and API fetch methods with exponential backoff
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
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
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
    def __init__(self, week_number=None, github_token=None, model="gpt-4.1", 
                 data_source="ai", alphavantage_key=None, marketstack_key=None, 
                 finnhub_key=None, eval_date=None, palette="default"):
        # Configuration
        self.existing_weeks = None  # Initialize before detect_next_week() call
        self.week_number = week_number or self.detect_next_week()
        self.model = model
        self.data_source = data_source.lower()
        self.palette = palette
        self.nonce = 'qi123'
        self.stylesheet_name = 'styles.css'
        
        # API keys
        self.azure_api_key = os.getenv('AZURE_OPENAI_API_KEY')
        self.alphavantage_key = alphavantage_key or os.getenv('ALPHAVANTAGE_API_KEY')
        self.marketstack_key = marketstack_key or os.getenv('MARKETSTACK_API_KEY')
        self.finnhub_key = finnhub_key or os.getenv('FINNHUB_API_KEY')
        
        # AI client state
        self.client = None
        self.ai_enabled = False
        self.ai_provider = 'Azure OpenAI'
        
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

        # Initialize Azure OpenAI client
        if self.azure_api_key:
            try:
                self.client = OpenAI(
                    base_url="https://MyPortfolio.openai.azure.com/openai/v1/",
                    api_key=self.azure_api_key
                )
                self.ai_enabled = True
                logging.info(f"✓ Azure OpenAI initialized (deployment: {self.model})")
            except Exception as e:
                logging.error(f"✗ Azure OpenAI failed: {e}")
        
        # Validate configuration
        if self.data_source == 'ai' and not self.ai_enabled:
            raise ValueError("AI mode requires AZURE_OPENAI_API_KEY. Use --data-source=alphavantage for data-only mode.")
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

        # Execution report tracking (initialize before load_prompts)
        self.report = {
            'steps': [],
            'start_time': datetime.now(),
            'week_number': self.week_number,
            'success': False
        }

        # Load prompts
        self.prompts = self.load_prompts()

        # State storage
        self.master_json = None
        self.narrative_html = None
        self.seo_json = None
        self.performance_table = None
        self.performance_chart = None
        self.visuals_json = None
    
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
        """Load prompt markdown files (A, B, D - Prompt C eliminated)"""
        prompts = {}
        missing = []
        # Prompt C eliminated - visual generation now handled by automation script
        for letter in ['A', 'B', 'D']:
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
                         "All 3 prompt files loaded successfully (A, B, D)")
        
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
    
    def call_ai(self, system_prompt, user_message, temperature=0.7, max_retries=3):
        """Call Azure OpenAI API with retry logic and automatic fallback
        
        Uses Azure OpenAI deployment with support for temperature control.
        """
        if not self.client:
            raise ValueError("AI client not initialized. Set AZURE_OPENAI_API_KEY environment variable.")
        
        current_model = self.model
        last_error = None
        
        # Retry loop for transient network errors
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=current_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    temperature=temperature
                )
                logging.info(f"✓ AI response received ({current_model})")
                return response.choices[0].message.content
                
            except Exception as e:
                last_error = e
                error_msg = str(e)
                
                # Check for rate limit (429) - respect Retry-After header
                if 'rate' in error_msg.lower() or '429' in error_msg:
                    retry_after = 60  # Default wait time
                    logging.warning(f"✗ Rate limit reached. Waiting {retry_after}s...")
                    time.sleep(retry_after)
                    continue
                
                # Check for transient network errors - retry
                is_transient = any(keyword in error_msg.lower() for keyword in [
                    'connection', 'timeout', 'remote end closed', 'broken pipe',
                    'connection reset', 'remotedisconnected'
                ])
                
                if is_transient and attempt < max_retries - 1:
                    # Retry with backoff
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    logging.warning(f"✗ Network error (attempt {attempt + 1}/{max_retries}): {error_msg}")
                    logging.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                
                # Final failure - provide diagnostics and raise
                if attempt == max_retries - 1:
                    msg_len = len(system_prompt) + len(user_message)
                    logging.error(f"✗ AI call failed after {max_retries} attempts")
                    logging.error(f"  Model: {current_model}")
                    logging.error(f"  Message length: {msg_len:,} chars (~{msg_len//4:,} tokens)")
                    logging.error(f"  Error: {e}")
                else:
                    logging.error(f"✗ AI call failed: {e}")
                raise
        
        # If we somehow exit the loop without returning or raising
        raise last_error if last_error else RuntimeError("AI call failed for unknown reason")
    
    def _purge_and_minify_css(self):
        """CSS optimization (placeholder - not critical for MVP)"""
        logging.warning("CSS minification not implemented (using original styles.css)")
        pass
    
    def run_prompt_a_validator(self):
        """Prompt A: Data Validator - Validate calculations already performed by automation.
        
        This is optional QA step. The automation script has already:
        - Fetched prices and added to master.json
        - Calculated all metrics (stocks, portfolio, benchmarks, normalized chart)
        - Saved updated master.json
        
        Prompt A validates the calculations are correct.
        Saves validation report to Data/W{n}/validation_report.txt
        
        Returns:
            Dict with 'status' (pass/fail/unclear/error) and 'report' (str).
            NOTE: Returns dict instead of raising exceptions because validation
            is non-fatal. Calculations are already complete - this is optional QA.
        """
        logging.info("Running Prompt A: Data Validator...")
        
        try:
            if not self.master_json:
                raise ValueError("master.json must be loaded before running Prompt A validator")
            
            system_prompt = "You are the GenAi Chosen Data Validator. Follow Prompt A specifications exactly."
            
            user_message = f"""
{self.prompts['A']}

---

Here is master.json with Week {self.week_number} data and calculations complete:

```json
{json.dumps(self.master_json, indent=2)}
```

Validate all calculations are mathematically correct.
Return a validation report (PASS or FAIL with details).
"""
            
            response = self.call_ai(system_prompt, user_message, temperature=0.3)
            
            # Save validation report to week's data folder
            week_dir = DATA_DIR / f"W{self.week_number}"
            week_dir.mkdir(exist_ok=True)
            validation_path = week_dir / "validation_report.txt"
            
            with open(validation_path, 'w', encoding='utf-8') as f:
                f.write(f"Prompt A Validation Report - Week {self.week_number}\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 80 + "\n\n")
                f.write(response)
            
            logging.info(f"Validation report saved to: {validation_path}")
            
            # Check if validation passed
            validation_passed = '✅' in response or 'PASS' in response.upper()
            validation_failed = '❌' in response or 'FAIL' in response.upper()
            
            if validation_passed and not validation_failed:
                logging.info(f"✅ Prompt A Validation: PASS - Week {self.week_number} calculations verified")
                self.add_step("Prompt A - Data Validator", "success", 
                             f"All Week {self.week_number} calculations validated",
                             {'validation_report': response[:500], 'report_file': str(validation_path)})
                return {'status': 'pass', 'report': response}
            
            elif validation_failed:
                logging.warning(f"❌ Prompt A Validation: FAIL - Found calculation errors in Week {self.week_number}")
                logging.warning(f"Validation report:\n{response}")
                self.add_step("Prompt A - Data Validator", "warning", 
                             f"Validation found errors in Week {self.week_number} calculations",
                             {'validation_report': response[:500], 'report_file': str(validation_path)})
                return {'status': 'fail', 'report': response}
            
            else:
                # Ambiguous response
                logging.warning("Prompt A validation response unclear")
                self.add_step("Prompt A - Data Validator", "warning", 
                             "Validation response format unclear",
                             {'validation_report': response[:500], 'report_file': str(validation_path)})
                return {'status': 'unclear', 'report': response}
            
        except Exception as e:
            self.add_step("Prompt A - Data Validator", "error", 
                         f"Prompt A validation failed: {str(e)}")
            # Validation failure is non-fatal - calculations already done
            logging.warning(f"Prompt A validator failed: {e}. Continuing with generated data.")
            return {'status': 'error', 'report': str(e)}
    
    def _generate_media_assets(self):
        """Hero image generation disabled - manually add W{n}.webp to Media folder."""
        expected_path = REPO_ROOT / 'Media' / f"W{self.week_number}.webp"
        if expected_path.exists():
            logging.info(f"✓ Hero image found: {expected_path}")
            self.add_step("Check Hero Image", "success",
                         f"Hero image exists for Week {self.week_number}",
                         {'image_path': str(expected_path)})
        else:
            logging.warning(f"⚠ Hero image not found: {expected_path}")
            logging.warning(f"  Please manually add W{self.week_number}.webp to Media/ folder")
            self.add_step("Check Hero Image", "warning",
                         f"Hero image missing - add W{self.week_number}.webp to Media/ folder manually",
                         {'expected_path': str(expected_path)})

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
            response = self.session.get(url, params=params, timeout=60)
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
            response = self.session.get(url, params=params, timeout=60)
            response.raise_for_status()
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
            response = self.session.get(url, params=params, timeout=60)
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
            response = self.session.get(url, params=params, timeout=60)
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
            response = self.session.get(url, params=params, timeout=60)
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
        
        Raises:
            ValueError: If master.json not loaded or if duplicate date detected.
        """
        logging.info("Running Alpha Vantage data engine...")
        if self.master_json is None:
            raise ValueError("master.json must be loaded before fetching new data")

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
            # Expected: sp500 -> ^SPX (S&P 500 Index), bitcoin -> BTC (crypto)
            if bench_key == 'sp500':
                symbol = '^SPX'  # S&P 500 Index symbol for Marketstack
                bench_type = 'index'
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
            elif bench_key == 'sp500':
                # Use Marketstack ONLY for S&P 500 Index (^SPX)
                if not self.marketstack_key:
                    raise ValueError("MARKETSTACK_API_KEY required for S&P 500 Index retrieval")
                logging.info(f"Fetching S&P 500 from Marketstack using {symbol}...")
                quote = self._fetch_marketstack_quote(symbol)
                if not quote:
                    raise ValueError(f"Failed to fetch S&P 500 ({symbol}) from Marketstack. Cannot generate accurate portfolio data.")
            else:
                # Other benchmarks: use regular fallback chain
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
            "spx_norm": round(100 * spx_close / spx_first_ref, 2),
            "btc_norm": round(100 * btc_close / btc_first_ref, 2)
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
        
        self.add_step("Calculate Portfolio Metrics", "success",
                     f"Fetched prices and calculated metrics for Week {self.week_number}",
                     {'prices': price_report})
        
        logging.info(f"Alpha Vantage data engine completed for Week {self.week_number}")
        logging.info(f"  → Primary: {master_path}")
        logging.info(f"  → Archive: {archive_path}")
        logging.info(f"  → Legacy:  {legacy_path} (optional)")
        
        # Generate media assets
        self._generate_media_assets()
        return updated_master
    
    def _extract_narrative_summary(self):
        """Extract only essential data for Prompt B to reduce token usage"""
        if not self.master_json:
            return {}
        
        # Get latest entries only
        ph = self.master_json.get('portfolio_history', [])
        latest_portfolio = ph[-1] if ph else {}
        prev_portfolio = ph[-2] if len(ph) > 1 else {}
        
        sp500_hist = self.master_json.get('benchmarks', {}).get('sp500', {}).get('history', [])
        latest_sp500 = sp500_hist[-1] if sp500_hist else {}
        prev_sp500 = sp500_hist[-2] if len(sp500_hist) > 1 else {}
        
        btc_hist = self.master_json.get('benchmarks', {}).get('bitcoin', {}).get('history', [])
        latest_btc = btc_hist[-1] if btc_hist else {}
        prev_btc = btc_hist[-2] if len(btc_hist) > 1 else {}
        
        # Extract current stocks with only current week data
        stocks_summary = []
        for stock in self.master_json.get('stocks', []):
            stocks_summary.append({
                'ticker': stock.get('ticker'),
                'name': stock.get('name'),
                'shares': stock.get('shares'),
                'current_value': stock.get('current_value'),
                'weekly_pct': stock.get('weekly_pct'),
                'total_pct': stock.get('total_pct')
            })
        
        return {
            'meta': self.master_json.get('meta', {}),
            'stocks': stocks_summary,
            'portfolio_current': {
                'date': latest_portfolio.get('date'),
                'value': latest_portfolio.get('value'),
                'weekly_pct': latest_portfolio.get('weekly_pct'),
                'total_pct': latest_portfolio.get('total_pct')
            },
            'portfolio_previous': {
                'date': prev_portfolio.get('date'),
                'value': prev_portfolio.get('value'),
                'weekly_pct': prev_portfolio.get('weekly_pct'),
                'total_pct': prev_portfolio.get('total_pct')
            },
            'sp500_current': {
                'date': latest_sp500.get('date'),
                'close': latest_sp500.get('close'),
                'weekly_pct': latest_sp500.get('weekly_pct'),
                'total_pct': latest_sp500.get('total_pct')
            },
            'sp500_previous': {
                'date': prev_sp500.get('date'),
                'close': prev_sp500.get('close'),
                'weekly_pct': prev_sp500.get('weekly_pct'),
                'total_pct': prev_sp500.get('total_pct')
            },
            'bitcoin_current': {
                'date': latest_btc.get('date'),
                'close': latest_btc.get('close'),
                'weekly_pct': latest_btc.get('weekly_pct'),
                'total_pct': latest_btc.get('total_pct')
            },
            'bitcoin_previous': {
                'date': prev_btc.get('date'),
                'close': prev_btc.get('close'),
                'weekly_pct': prev_btc.get('weekly_pct'),
                'total_pct': prev_btc.get('total_pct')
            },
            'week_number': self.week_number
        }
    
    def run_prompt_b(self):
        """Prompt B: Narrative Writer - Generate HTML content"""
        logging.info("Running Prompt B: Narrative Writer...")
        
        try:
            system_prompt = "You are the GenAi Chosen Narrative Writer. Follow Prompt B specifications exactly."
            
            # Extract only essential data to stay under token limit
            narrative_data = self._extract_narrative_summary()
            
            # Compact JSON to reduce size
            data_json = json.dumps(narrative_data, separators=(',', ':'))
            
            user_message = f"""
{self.prompts['B']}

---

Here is the summary data for Week {self.week_number}:

```json
{data_json}
```

Generate:
1. narrative.html (the prose content block)
2. seo.json (all metadata)

This is for Week {self.week_number}.
"""
            
            # Log request size for debugging
            estimated_tokens = (len(system_prompt) + len(user_message)) // 4
            logging.info(f"Estimated request size: ~{estimated_tokens} tokens")
            
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
        # Always use the generated hero image (W{n}.webp) for Open Graph and Twitter Cards
        hero_image_url = f"https://quantuminvestor.net/Media/W{self.week_number}.webp"
        return {
            "title": f"GenAi-Managed Stocks Portfolio Week {self.week_number} – Performance, Risks & Next Moves - Quantum Investor Digest",
            "description": f"Week {self.week_number} performance update for the AI-managed stock portfolio. Review returns vs S&P 500 and Bitcoin, top movers, and next week's outlook.",
            "canonicalUrl": f"https://quantuminvestor.net/Posts/GenAi-Managed-Stocks-Portfolio-Week-{self.week_number}.html",
            "ogTitle": f"GenAi-Managed Stocks Portfolio Week {self.week_number}",
            "ogDescription": f"Week {self.week_number} AI portfolio performance analysis",
            "ogImage": hero_image_url,
            "ogUrl": f"https://quantuminvestor.net/Posts/GenAi-Managed-Stocks-Portfolio-Week-{self.week_number}.html",
            "twitterTitle": f"GenAi Portfolio Week {self.week_number}",
            "twitterDescription": f"AI-managed portfolio weekly update",
            "twitterImage": hero_image_url,
            "twitterCard": "summary_large_image"
        }

    def _apply_standard_head(self, html: str) -> str:
        """Apply hardened CSP + nonce, stylesheet link, external scripts, JSON-LD."""
        seo = self.seo_json or self.generate_fallback_seo()
        
        # ALWAYS use the generated hero image for Open Graph and Twitter Card meta tags (override AI-generated URLs)
        hero_image_url = f"https://quantuminvestor.net/Media/W{self.week_number}.webp"
        
        canonical = seo.get('canonicalUrl')
        title = seo.get('title')
        meta_desc = seo.get('description')
        og_title = seo.get('ogTitle') or title
        og_desc = seo.get('ogDescription') or meta_desc
        og_image = hero_image_url  # Force hero image, ignore SEO JSON
        og_url = seo.get('ogUrl') or canonical
        twitter_title = seo.get('twitterTitle') or og_title
        twitter_desc = seo.get('twitterDescription') or og_desc
        twitter_image = hero_image_url  # Force hero image, ignore SEO JSON
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
  <style>
/* Performance table styles */
.myblock-performance-snapshot {{
  margin: 20px 0;
  font-family: inherit;
  overflow-x: visible;
}}
.myblock-portfolio-table {{
  width: 100%;
  border-collapse: collapse;
  background: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  border-radius: 8px;
  overflow: hidden;
  table-layout: fixed;
  contain: layout style;
}}
.myblock-portfolio-table thead tr {{
  background: #8B7AB8;
  color: white;
  font-weight: bold;
}}
.myblock-portfolio-table th {{
  padding: 16px 12px;
  text-align: left;
  border: 1px solid #E5E5E5;
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
  font-family: inherit;
}}
.myblock-portfolio-table th:not(:first-child) {{
  text-align: right;
}}
.myblock-portfolio-table td {{
  padding: 14px 12px;
  border: 1px solid #E5E5E5;
  font-size: 14px;
  white-space: nowrap;
  font-family: inherit;
}}
.myblock-portfolio-table .asset-name {{
  font-weight: 600;
  text-align: left;
  white-space: normal;
  min-width: 120px;
}}
.myblock-portfolio-table td:not(.asset-name) {{
  text-align: right;
}}
.myblock-portfolio-table tbody tr:nth-child(even) {{
  background: #F9F9FB;
}}
.myblock-portfolio-table .positive {{
  color: #2E7D32;
  font-weight: 600;
}}
.myblock-portfolio-table .negative {{
  color: #C62828;
  font-weight: 600;
}}
.myblock-portfolio-table tbody tr {{
  transition: background-color 0.2s ease;
}}
.myblock-portfolio-table tbody tr:hover {{
  background: #F8F5FF;
}}
@media (max-width: 900px) {{
  .myblock-portfolio-table th,
  .myblock-portfolio-table td {{
    padding: 10px 8px;
    font-size: 12px;
  }}
  .myblock-portfolio-table th {{
    font-size: 11px;
  }}
  .myblock-portfolio-table .asset-name {{
    min-width: 100px;
    font-size: 12px;
  }}
}}
@media (max-width: 768px) {{
  .myblock-portfolio-table th,
  .myblock-portfolio-table td {{
    padding: 6px 4px;
    font-size: 11px;
  }}
  .myblock-portfolio-table th {{
    font-size: 10px;
    line-height: 1.2;
  }}
  .myblock-portfolio-table .asset-name {{
    min-width: 70px;
    font-size: 11px;
  }}
}}
@media (max-width: 480px) {{
  .myblock-portfolio-table th,
  .myblock-portfolio-table td {{
    padding: 5px 3px;
    font-size: 10px;
  }}
  .myblock-portfolio-table th {{
    font-size: 9px;
    line-height: 1.2;
  }}
  .myblock-portfolio-table .asset-name {{
    min-width: 60px;
    font-size: 10px;
  }}
}}

/* Performance chart styles */
.myblock-chart-container {{
  width: 100%;
  max-width: 1000px;
  margin: 30px auto;
  padding: 20px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  font-family: inherit;
  overflow: hidden;
  box-sizing: border-box;
}}
.myblock-chart-title {{
  font-size: 20px;
  font-weight: 600;
  color: #2C3E50;
  margin-bottom: 20px;
  text-align: center;
}}
.myblock-chart-wrapper {{
  position: relative;
  width: 100%;
  height: 400px;
  margin-bottom: 20px;
  overflow: hidden;
}}
.myblock-chart-svg {{
  width: 100%;
  height: 100%;
  display: block;
}}
.myblock-chart-grid-line {{
  stroke: #E8E8E8;
  stroke-width: 1;
  stroke-dasharray: 4,4;
}}
.myblock-chart-axis {{
  stroke: #2C3E50;
  stroke-width: 2;
}}
.myblock-chart-label {{
  font-size: 12px;
  fill: #666;
  font-family: inherit;
}}
.myblock-chart-line-genai {{
  fill: none;
  stroke: #8B7AB8;
  stroke-width: 3;
  stroke-linecap: round;
  stroke-linejoin: round;
}}
.myblock-chart-line-sp500 {{
  fill: none;
  stroke: #2E7D32;
  stroke-width: 2.5;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-dasharray: 6,4;
}}
.myblock-chart-line-bitcoin {{
  fill: none;
  stroke: #C62828;
  stroke-width: 2.5;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-dasharray: 2,2;
}}
.myblock-chart-dot {{
  r: 5;
}}
.myblock-chart-dot-genai {{
  fill: #8B7AB8;
  stroke: #fff;
  stroke-width: 2;
}}
.myblock-chart-dot-sp500 {{
  fill: #2E7D32;
  stroke: #fff;
  stroke-width: 2;
}}
.myblock-chart-dot-bitcoin {{
  fill: #C62828;
  stroke: #fff;
  stroke-width: 2;
}}
.myblock-chart-legend {{
  display: flex;
  justify-content: center;
  gap: 30px;
  margin-top: 20px;
  flex-wrap: wrap;
}}
.myblock-chart-legend-item {{
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #2C3E50;
}}
.myblock-chart-legend-line {{
  width: 30px;
  height: 3px;
  border-radius: 2px;
}}
.myblock-legend-genai {{
  background: #8B7AB8;
}}
.myblock-legend-sp500 {{
  background: #2E7D32;
}}
.myblock-legend-bitcoin {{
  background: #C62828;
}}
@media screen and (max-width: 768px) {{
  .myblock-chart-container {{
    padding: 15px;
  }}
  .myblock-chart-wrapper {{
    height: 300px;
  }}
  .myblock-chart-title {{
    font-size: 18px;
  }}
  .myblock-chart-label {{
    font-size: 10px;
  }}
  .myblock-chart-legend {{
    gap: 15px;
  }}
  .myblock-chart-legend-item {{
    font-size: 12px;
  }}
}}
</style>
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
    
    def _extract_visual_data(self):
        """Extract only data needed for visuals (table + chart) to reduce tokens"""
        if not self.master_json:
            return {}
        
        # Get latest 3 entries for table (inception, previous, current)
        ph = self.master_json.get('portfolio_history', [])
        inception = ph[0] if ph else {}
        previous = ph[-2] if len(ph) > 1 else {}
        current = ph[-1] if ph else {}
        
        sp500_hist = self.master_json.get('benchmarks', {}).get('sp500', {}).get('history', [])
        sp500_inception = sp500_hist[0] if sp500_hist else {}
        sp500_previous = sp500_hist[-2] if len(sp500_hist) > 1 else {}
        sp500_current = sp500_hist[-1] if sp500_hist else {}
        
        btc_hist = self.master_json.get('benchmarks', {}).get('bitcoin', {}).get('history', [])
        btc_inception = btc_hist[0] if btc_hist else {}
        btc_previous = btc_hist[-2] if len(btc_hist) > 1 else {}
        btc_current = btc_hist[-1] if btc_hist else {}
        
        # Get normalized chart data (all entries needed for chart)
        normalized = self.master_json.get('normalized_chart', [])
        
        return {
            'meta': self.master_json.get('meta', {}),
            'portfolio_history': [inception, previous, current],
            'benchmarks': {
                'sp500': {
                    'inception_reference': self.master_json.get('benchmarks', {}).get('sp500', {}).get('inception_reference'),
                    'history': [sp500_inception, sp500_previous, sp500_current]
                },
                'bitcoin': {
                    'inception_reference': self.master_json.get('benchmarks', {}).get('bitcoin', {}).get('inception_reference'),
                    'history': [btc_inception, btc_previous, btc_current]
                }
            },
            'normalized_chart': normalized,
            'week_number': self.week_number
        }
    
    def generate_visuals(self):
        """Generate performance table and chart directly (no AI needed).
        
        Replaces Prompt C functionality with deterministic Python generation.
        
        Raises:
            ValueError: If master.json not loaded or insufficient data.
        """
        logging.info("Generating visual components...")
        
        try:
            # Generate table and chart using Python
            self.generate_performance_table()
            self.generate_performance_chart()
            self.generate_visuals_json()
            
            logging.info("Visual generation completed")
            
        except Exception as e:
            self.add_step("Generate Visuals", "error",
                         f"Visual generation failed: {str(e)}")
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
            # Find insertion point after "Performance Since Inception" h2 and 3 paragraphs
            # Primary pattern: exactly 3 paragraphs (Prompt B requirement)
            inception_pattern = r'(<h2[^>]*>Performance Since Inception</h2>\s*(?:<p[^>]*>.*?</p>\s*){3})'
            match = re.search(inception_pattern, self.narrative_html, re.DOTALL)
            if match:
                insert_pos = match.end()
                self.narrative_html = (
                    self.narrative_html[:insert_pos] + 
                    '\n\n' + self.performance_chart + '\n\n' + 
                    self.narrative_html[insert_pos:]
                )
                logging.info("Chart embedded after 3 paragraphs (standard pattern)")
            else:
                logging.warning("Could not find 3 paragraphs after 'Performance Since Inception' - trying fallback")
                # Fallback pattern (2-4 paragraphs for flexibility)
                inception_pattern_fallback = r'(<h2[^>]*>Performance Since Inception</h2>\s*(?:<p[^>]*>.*?</p>\s*){2,4})'
                match = re.search(inception_pattern_fallback, self.narrative_html, re.DOTALL)
                if match:
                    insert_pos = match.end()
                    self.narrative_html = (
                        self.narrative_html[:insert_pos] + 
                        '\n\n' + self.performance_chart + '\n\n' + 
                        self.narrative_html[insert_pos:]
                    )
                    logging.info("Chart embedded using fallback pattern (2-4 paragraphs)")
                else:
                    logging.error("CRITICAL: Could not find Performance Since Inception section for chart embedding")
                    logging.error("This may result in chart not appearing in final HTML")
        
        # Extract minimal metadata for Prompt D (doesn't need full data)
        minimal_meta = {
            'week_number': self.week_number,
            'current_date': self.master_json.get('meta', {}).get('current_date'),
            'inception_date': self.master_json.get('meta', {}).get('inception_date')
        }
        
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

**metadata:**
```json
{json.dumps(minimal_meta, indent=2)}
```

Generate the complete HTML file for Week {self.week_number}.
"""
        
        response = self.call_ai(system_prompt, user_message)
        
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
    
    def generate_performance_table(self):
        """Generate performance_table.html from master.json data.
        
        Creates a snapshot table showing inception, previous week, and current week
        values for portfolio, S&P 500, and Bitcoin.
        """
        logging.info("Generating performance table...")
        
        try:
            if not self.master_json:
                raise ValueError("master.json must be loaded before generating visuals")
            
            # Extract data from master.json
            meta = self.master_json.get('meta', {})
            inception_date = meta.get('inception_date', '2025-10-09')
            current_date = meta.get('current_date', '')
            
            portfolio_history = self.master_json.get('portfolio_history', [])
            sp500_history = self.master_json.get('benchmarks', {}).get('sp500', {}).get('history', [])
            btc_history = self.master_json.get('benchmarks', {}).get('bitcoin', {}).get('history', [])
            
            if len(portfolio_history) < 2:
                raise ValueError("Need at least 2 weeks of data to generate table")
            
            # Get inception, previous, and current entries
            portfolio_inception = portfolio_history[0]
            portfolio_previous = portfolio_history[-2]
            portfolio_current = portfolio_history[-1]
            
            sp500_inception = sp500_history[0]
            sp500_previous = sp500_history[-2]
            sp500_current = sp500_history[-1]
            
            btc_inception = btc_history[0]
            btc_previous = btc_history[-2]
            btc_current = btc_history[-1]
            
            # Format dates
            prev_date = portfolio_previous.get('date', '')
            curr_date = portfolio_current.get('date', '')
            
            # Parse dates for display
            from datetime import datetime
            prev_date_obj = datetime.strptime(prev_date, '%Y-%m-%d')
            curr_date_obj = datetime.strptime(curr_date, '%Y-%m-%d')
            
            prev_display = prev_date_obj.strftime('%b %-d' if prev_date_obj.day < 10 else '%b %d').replace(' 0', ' ')
            curr_display = curr_date_obj.strftime('%b %-d' if curr_date_obj.day < 10 else '%b %d').replace(' 0', ' ')
            year = curr_date_obj.year
            
            # Format values
            def format_value(val, prefix=''):
                return f"{prefix}{val:,}"
            
            def format_pct(val):
                sign = '+' if val >= 0 else ''
                return f"{sign}{val:.2f}%"
            
            def pct_class(val):
                return 'positive' if val >= 0 else 'negative'
            
            # Build HTML
            table_html = f'''<div class="myblock-performance-snapshot">
  <table class="myblock-portfolio-table" aria-label="Portfolio performance comparison">
    <caption>Portfolio vs Benchmarks Performance (Oct 9 – {curr_display}, {year})</caption>
    <thead>
      <tr>
        <th scope="col">Asset</th>
        <th scope="col">Oct 9, {year}</th>
        <th scope="col">{prev_display}, {year}</th>
        <th scope="col">{curr_display}, {year}</th>
        <th scope="col">Weekly<br>Change</th>
        <th scope="col">Total<br>Return</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td class="asset-name">GenAi Chosen ($)</td>
        <td>{format_value(portfolio_inception['value'])}</td>
        <td>{format_value(portfolio_previous['value'])}</td>
        <td>{format_value(portfolio_current['value'])}</td>
        <td class="{pct_class(portfolio_current['weekly_pct'])}">{format_pct(portfolio_current['weekly_pct'])}</td>
        <td class="{pct_class(portfolio_current['total_pct'])}">{format_pct(portfolio_current['total_pct'])}</td>
      </tr>
      <tr>
        <td class="asset-name">S&amp;P 500 (Index)</td>
        <td>{format_value(round(sp500_inception['close']))}</td>
        <td>{format_value(round(sp500_previous['close']))}</td>
        <td>{format_value(round(sp500_current['close']))}</td>
        <td class="{pct_class(sp500_current['weekly_pct'])}">{format_pct(sp500_current['weekly_pct'])}</td>
        <td class="{pct_class(sp500_current['total_pct'])}">{format_pct(sp500_current['total_pct'])}</td>
      </tr>
      <tr>
        <td class="asset-name">Bitcoin ($)</td>
        <td>{format_value(round(btc_inception['close']))}</td>
        <td>{format_value(round(btc_previous['close']))}</td>
        <td>{format_value(round(btc_current['close']))}</td>
        <td class="{pct_class(btc_current['weekly_pct'])}">{format_pct(btc_current['weekly_pct'])}</td>
        <td class="{pct_class(btc_current['total_pct'])}">{format_pct(btc_current['total_pct'])}</td>
      </tr>
    </tbody>
  </table>
</div>'''
            
            self.performance_table = table_html
            
            # Save to file for archival/debugging
            output_path = DATA_DIR / f"W{self.week_number}" / "performance_table.html"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(table_html)
            
            logging.info(f"Performance table generated: {output_path}")
            self.add_step("Generate Performance Table", "success",
                         "Generated performance snapshot table",
                         {'output_file': str(output_path)})
            
            return table_html
            
        except Exception as e:
            self.add_step("Generate Performance Table", "error",
                         f"Failed to generate performance table: {str(e)}")
            raise
    
    def generate_performance_chart(self):
        """Generate performance_chart.svg from master.json data.
        
        Creates a normalized line chart showing portfolio, S&P 500, and Bitcoin
        performance since inception (all normalized to 100 at start).
        """
        logging.info("Generating performance chart...")
        
        try:
            if not self.master_json:
                raise ValueError("master.json must be loaded before generating visuals")
            
            # Extract normalized chart data
            normalized_data = self.master_json.get('normalized_chart', [])
            if len(normalized_data) < 2:
                raise ValueError("Need at least 2 data points to generate chart")
            
            # SVG dimensions and padding - Match Week 5 exactly
            width = 900
            height = 400
            pad_left = 80
            pad_right = 50
            pad_top = 50
            pad_bottom = 50
            chart_width = width - pad_left - pad_right
            chart_height = height - pad_top - pad_bottom
            
            # FIXED Y-AXIS SCALE: 80 to 120 (normalized baseline 100)
            # This matches Week 5 standard where all assets start at 100
            y_min = 80
            y_max = 120
            
            # Fixed Y-axis labels matching Week 5
            y_labels = [120, 110, 100, 90, 80]
            
            # Coordinate conversion functions - Week 5 standard
            # Y-axis mapping: 80 -> y=350, 100 -> y=200, 120 -> y=50
            # Formula: y = 200 - (normalized_value - 100) * 7.5
            def x_coord(index):
                if len(normalized_data) == 1:
                    return pad_left
                return pad_left + (index / (len(normalized_data) - 1)) * chart_width
            
            def y_coord(value):
                # Week 5 formula: y = 200 - (value - 100) * 7.5
                return 200.0 - (value - 100.0) * 7.5
            
            # Generate polyline points - Week 5 format (1 decimal place)
            genai_points = []
            spx_points = []
            btc_points = []
            
            for i, entry in enumerate(normalized_data):
                x = x_coord(i)
                genai_y = y_coord(entry.get('genai_norm', 100))
                spx_y = y_coord(entry.get('spx_norm', 100))
                btc_y = y_coord(entry.get('btc_norm', 100))
                genai_points.append(f"{x:.1f},{genai_y:.1f}")
                spx_points.append(f"{x:.1f},{spx_y:.1f}")
                btc_points.append(f"{x:.1f},{btc_y:.1f}")
            
            # Generate X-axis labels (dates) - Week 5 style
            from datetime import datetime
            x_labels_html = []
            for idx in range(len(normalized_data)):
                entry = normalized_data[idx]
                date_str = entry.get('date', '')
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                label = date_obj.strftime('%b %-d, %Y').replace(' 0', ' ')
                x = x_coord(idx)
                x_labels_html.append(f'<text class="myblock-chart-label" x="{x:.1f}" y="375" text-anchor="middle">{label}</text>')
            
            # Generate Y-axis labels and gridlines - Week 5 fixed positions
            y_grid_positions = [50, 125, 200, 275, 350]  # y=50 (120), y=125 (110), y=200 (100), y=275 (90), y=350 (80)
            y_labels_html = []
            gridlines_html = []
            for i, (val, y_pos) in enumerate(zip(y_labels, y_grid_positions)):
                y_labels_html.append(f'<text class="myblock-chart-label" x="65" y="{y_pos + 5}" text-anchor="end">{val}</text>')
                gridlines_html.append(f'<line class="myblock-chart-grid-line" x1="80" y1="{y_pos}" x2="850" y2="{y_pos}"/>')
            
            # Generate dots - Week 5 format with proper formatting
            dots_html = []
            for i, entry in enumerate(normalized_data):
                x = x_coord(i)
                genai_y = y_coord(entry.get("genai_norm", 100))
                spx_y = y_coord(entry.get("spx_norm", 100))
                btc_y = y_coord(entry.get("btc_norm", 100))
                dots_html.append(f'<circle class="myblock-chart-dot myblock-chart-dot-genai" cx="{x:.1f}" cy="{genai_y:.1f}"/>')
                dots_html.append(f'<circle class="myblock-chart-dot myblock-chart-dot-sp500" cx="{x:.1f}" cy="{spx_y:.1f}"/>')
                dots_html.append(f'<circle class="myblock-chart-dot myblock-chart-dot-bitcoin" cx="{x:.1f}" cy="{btc_y:.1f}"/>')
            
            # Get total returns for legend
            latest = normalized_data[-1]
            genai_return = latest.get('genai_norm', 100) - 100
            spx_return = latest.get('spx_norm', 100) - 100
            btc_return = latest.get('btc_norm', 100) - 100
            
            def format_pct(val):
                sign = '+' if val >= 0 else ''
                return f"{sign}{val:.2f}%"
            
            # Build chart HTML - Week 5 format with clean comments
            chart_html = f'''<div class="myblock-chart-container">
  <div class="myblock-chart-title">Performance Since Inception (Normalized to 100)</div>
  <div class="myblock-chart-wrapper">
<svg class="myblock-chart-svg" viewBox="0 0 900 400" preserveAspectRatio="xMidYMid meet" role="img" aria-labelledby="chartTitle chartDesc">
<title id="chartTitle">Normalized Performance Since Inception</title>
<desc id="chartDesc"> Line chart comparing normalized performance of the GenAi Chosen portfolio, the S&amp;P 500, and Bitcoin from October 9, 2025, with all assets normalized to 100 on the inception date and 100 shown as the central reference line. </desc>
<!--  Grid lines  -->
{''.join(gridlines_html)}
<!--  Y-axis labels  -->
{''.join(y_labels_html)}
<!--  X-axis labels  -->
{''.join(x_labels_html)}
<!--  Axes  -->
<line class="myblock-chart-axis" x1="80" y1="50" x2="80" y2="350"/>
<line class="myblock-chart-axis" x1="80" y1="350" x2="850" y2="350"/>
<!--  GenAi line  -->
<polyline class="myblock-chart-line-genai" points="{' '.join(genai_points)}"/>
<!--  SPX line  -->
<polyline class="myblock-chart-line-sp500" points="{' '.join(spx_points)}"/>
<!--  BTC line  -->
<polyline class="myblock-chart-line-bitcoin" points="{' '.join(btc_points)}"/>
{''.join(dots_html)}
</svg>

  </div>
  <div class="myblock-chart-legend">
    <div class="myblock-chart-legend-item">
      <div class="myblock-chart-legend-line myblock-legend-genai"></div>
      <span><strong>GenAi Chosen</strong> ({format_pct(genai_return)})</span>
    </div>
    <div class="myblock-chart-legend-item">
      <div class="myblock-chart-legend-line myblock-legend-sp500"></div>
      <span><strong>S&amp;P 500</strong> ({format_pct(spx_return)})</span>
    </div>
    <div class="myblock-chart-legend-item">
      <div class="myblock-chart-legend-line myblock-legend-bitcoin"></div>
      <span><strong>Bitcoin</strong> ({format_pct(btc_return)})</span>
    </div>
  </div>
</div>'''
            
            self.performance_chart = chart_html
            
            # Save to file for archival/debugging
            output_path = DATA_DIR / f"W{self.week_number}" / "performance_chart.svg"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(chart_html)
            
            logging.info(f"Performance chart generated: {output_path}")
            self.add_step("Generate Performance Chart", "success",
                         "Generated normalized performance chart",
                         {'output_file': str(output_path)})
            
            return chart_html
            
        except Exception as e:
            self.add_step("Generate Performance Chart", "error",
                         f"Failed to generate performance chart: {str(e)}")
            raise
    
    def generate_visuals_json(self):
        """Generate visuals.json metadata descriptor."""
        try:
            meta = self.master_json.get('meta', {})
            visuals_data = {
                "performanceTableFile": "performance_table.html",
                "performanceChartFile": "performance_chart.svg",
                "dateRange": {
                    "inception": meta.get('inception_date', '2025-10-09'),
                    "current": meta.get('current_date', '')
                },
                "benchmarks": ["sp500", "bitcoin"],
                "normalized": True
            }
            
            self.visuals_json = visuals_data
            
            # Save to file
            output_path = DATA_DIR / f"W{self.week_number}" / "visuals.json"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(visuals_data, f, indent=2)
            
            logging.info(f"Visuals metadata generated: {output_path}")
            return visuals_data
            
        except Exception as e:
            logging.warning(f"Failed to generate visuals.json: {e}")
            return None
    
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
            
            # Step 1: Data acquisition and calculation (MUST succeed or abort)
            # Always use Alpha Vantage method - it fetches prices AND calculates metrics
            updated_master = self.generate_master_from_alphavantage()
            if not updated_master:
                raise ValueError("Data engine failed to generate master.json")
            
            # Step 2: Data validation (ALWAYS run when AI is enabled, non-fatal)
            # NOTE: This returns a dict (not exception) because validation is non-fatal
            # Even if validation fails, we continue with the generated data
            if self.ai_enabled:
                validation_result = self.run_prompt_a_validator()
                if validation_result['status'] == 'fail':
                    logging.warning("⚠ Validation detected calculation inconsistencies - continuing execution")
                    logging.warning("Review validation report in Data/W{self.week_number}/validation_report.txt")
                elif validation_result['status'] == 'error':
                    logging.warning("⚠ Validation step encountered an error - continuing execution")
                elif validation_result['status'] == 'pass':
                    logging.info("✅ Validation passed - calculations verified")
            else:
                logging.warning("⚠ AI not enabled - skipping Prompt A validation")
            
            # Step 3: Visual generation (deterministic Python, no AI needed)
            self.generate_visuals()
            if not self.performance_table or not self.performance_chart:
                raise ValueError("Visual components generation failed")
            
            # Step 4: Narrative generation (requires AI)
            if self.ai_enabled:
                # All-or-nothing: generate content first, write file only if successful
                self.run_prompt_b()
                if not self.narrative_html:
                    raise ValueError("Narrative HTML generation failed (Prompt B)")
                self.run_prompt_d()
                # If we reached here, all prompts succeeded and file was written
            else:
                # No AI available - fail fast, don't create incomplete output
                error_msg = "AI client not initialized - cannot generate narrative content"
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
                       help='[DEPRECATED] Not used with Azure OpenAI')
    parser.add_argument('--model', type=str, default='gpt-4.1',
                       help='Azure OpenAI deployment name (default: gpt-4.1)')
    parser.add_argument('--data-source', type=str, choices=['ai', 'alphavantage'], default='alphavantage',
                       help='Data source: alphavantage (fetch+calculate, optional AI validation) or ai (fetch+calculate+validate with AI)')
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
