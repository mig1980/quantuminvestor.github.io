# Portfolio Automation Refactoring Plan

## Executive Summary

**Current State:** Monolithic 2,699-line single-file script (`portfolio_automation.py`)  
**Problem:** Poor maintainability, difficult testing, tight coupling, unclear boundaries  
**Recommendation:** Break into 8 focused modules with clear separation of concerns  
**Estimated Effort:** 3-5 days for complete refactoring  
**Risk Level:** Medium (extensive testing required)

---

## Current Architecture Analysis

### Code Metrics
- **Total Lines:** 2,699
- **Class Count:** 1 (`PortfolioAutomation`)
- **Method Count:** 40+
- **Responsibilities:** 7+ distinct concerns

### Identified Responsibilities (Current Monolith)
1. **Configuration & Initialization** (lines 68-163)
2. **Data Fetching** (Alpha Vantage, Finnhub, Marketstack) (lines 488-704)
3. **Data Processing & Calculations** (lines 705-996)
4. **AI Integration** (Azure OpenAI calls) (lines 289-351, 358-471, 1068-1152, 1750-1916)
5. **HTML/Visual Generation** (lines 1941-2227)
6. **File I/O & State Management** (lines 260-288, 915-996)
7. **Report Generation** (lines 182-234, 1620-1745)
8. **Workflow Orchestration** (lines 2530-2650)

### Key Issues
1. **Testability:** Impossible to unit test individual components without mocking entire class
2. **Reusability:** Cannot reuse data fetchers or calculators in other contexts
3. **Clarity:** 2,699 lines make it difficult to understand any single feature
4. **Debugging:** Hard to isolate issues when everything is interconnected
5. **Extension:** Adding new data sources or AI providers requires modifying core class
6. **Parallelization:** Sequential execution baked into single class (no concurrent fetching)

---

## Proposed Modular Architecture

### Directory Structure
```
scripts/
├── portfolio_automation.py          # Main orchestrator (200 lines)
├── config.py                         # Configuration management (100 lines)
├── data/
│   ├── __init__.py
│   ├── fetchers.py                  # API data fetching (400 lines)
│   ├── calculators.py               # Portfolio calculations (300 lines)
│   └── validators.py                # Data validation utilities (150 lines)
├── ai/
│   ├── __init__.py
│   ├── client.py                    # AI client wrapper (150 lines)
│   ├── prompts.py                   # Prompt A/B/D handlers (400 lines)
│   └── seo.py                       # SEO metadata generation (100 lines)
├── generators/
│   ├── __init__.py
│   ├── visuals.py                   # Table & chart generation (400 lines)
│   ├── html.py                      # HTML assembly & optimization (300 lines)
│   └── reports.py                   # Text report generation (200 lines)
├── storage/
│   ├── __init__.py
│   ├── master_json.py               # Master.json operations (200 lines)
│   └── file_manager.py              # File I/O & backups (150 lines)
└── utils/
    ├── __init__.py
    ├── logging_config.py            # Logging setup (50 lines)
    └── rate_limiter.py              # Rate limiting logic (100 lines)
```

**Total Estimated Lines:** ~3,200 (more lines but better organized)

---

## Detailed Module Specifications

### 1. `config.py` - Configuration Management

**Purpose:** Centralize all configuration, environment variables, and constants

**Responsibilities:**
- Load environment variables
- Validate API keys
- Define constants (paths, rate limits, timeouts)
- Provide configuration object

**Key Classes:**
```python
class Config:
    """Immutable configuration object"""
    def __init__(self):
        self.azure_api_key = os.getenv('AZURE_OPENAI_API_KEY')
        self.alphavantage_key = os.getenv('ALPHAVANTAGE_API_KEY')
        self.marketstack_key = os.getenv('MARKETSTACK_API_KEY')
        self.finnhub_key = os.getenv('FINNHUB_API_KEY')
        
        # Paths
        self.repo_root = Path(__file__).parent.parent
        self.master_data_dir = self.repo_root / "master data"
        self.archive_dir = self.master_data_dir / "archive"
        self.data_dir = self.repo_root / "Data"
        self.posts_dir = self.repo_root / "Posts"
        self.prompt_dir = self.repo_root / "Prompt"
        
        # Rate limits
        self.alphavantage_rate_limit = 12  # seconds
        self.finnhub_rate_limit = 12
        self.marketstack_rate_limit = 2
        
        # CSP policy
        self.csp_template = "..."
        
    def validate(self) -> List[str]:
        """Return list of validation errors"""
        errors = []
        if not self.alphavantage_key:
            errors.append("ALPHAVANTAGE_API_KEY not set")
        # ... more validation
        return errors
```

**Benefits:**
- Single source of truth for configuration
- Easy to test with mock configs
- Environment-specific configs (dev, prod)
- Validation in one place

---

### 2. `data/fetchers.py` - API Data Fetching

**Purpose:** Abstract all external API calls with fallback chains

**Responsibilities:**
- Fetch stock quotes from Alpha Vantage, Finnhub, Marketstack
- Fetch crypto prices
- Handle rate limiting
- Implement fallback chains
- Retry logic with exponential backoff

**Key Classes:**
```python
from abc import ABC, abstractmethod
from typing import Optional, Dict

class DataFetcher(ABC):
    """Abstract base for all data fetchers"""
    @abstractmethod
    def fetch_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch quote, return {'date': str, 'close': float, 'source': str}"""
        pass

class AlphaVantageFetcher(DataFetcher):
    def __init__(self, api_key: str, rate_limiter: RateLimiter):
        self.api_key = api_key
        self.rate_limiter = rate_limiter
        self.session = self._create_session()
    
    def fetch_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        self.rate_limiter.wait_if_needed()
        # ... fetch logic
        
    def fetch_crypto(self, symbol: str) -> Optional[Dict[str, Any]]:
        # ... crypto-specific logic

class FinnhubFetcher(DataFetcher):
    # Similar structure

class MarketstackFetcher(DataFetcher):
    # Similar structure

class FallbackDataFetcher:
    """Orchestrates fallback chain across multiple fetchers"""
    def __init__(self, primary: DataFetcher, 
                 fallbacks: List[DataFetcher]):
        self.primary = primary
        self.fallbacks = fallbacks
    
    def fetch_quote(self, symbol: str) -> Dict[str, Any]:
        """Try primary, then fallbacks. Raise if all fail."""
        result = self.primary.fetch_quote(symbol)
        if result:
            return result
        
        for fetcher in self.fallbacks:
            result = fetcher.fetch_quote(symbol)
            if result:
                return result
        
        raise ValueError(f"All fetchers failed for {symbol}")
    
    def fetch_quotes_concurrent(self, symbols: List[str], 
                                max_workers: int = 3) -> Dict[str, Dict]:
        """Fetch multiple quotes concurrently with rate limit control"""
        from concurrent.futures import ThreadPoolExecutor
        # ... concurrent implementation
```

**Benefits:**
- Easy to add new data sources (just implement `DataFetcher`)
- Testable in isolation with mock API responses
- Concurrent fetching becomes trivial
- Rate limiting centralized in `RateLimiter` class

---

### 3. `data/calculators.py` - Portfolio Calculations

**Purpose:** Pure functions for all portfolio math (no side effects)

**Responsibilities:**
- Calculate weekly/total returns
- Compute portfolio values
- Normalize benchmark data
- Generate portfolio history entries

**Key Functions:**
```python
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class Stock:
    ticker: str
    name: str
    shares: int
    prices: Dict[str, float]  # {date: price}
    
    @property
    def current_value(self) -> float:
        latest_price = list(self.prices.values())[-1]
        return self.shares * latest_price
    
    def weekly_return(self) -> float:
        """Calculate weekly % return"""
        prices = list(self.prices.values())
        if len(prices) < 2:
            return 0.0
        return ((prices[-1] / prices[-2]) - 1) * 100
    
    def total_return(self, inception_price: float) -> float:
        """Calculate total % return from inception"""
        current_price = list(self.prices.values())[-1]
        return ((current_price / inception_price) - 1) * 100

@dataclass
class Portfolio:
    stocks: List[Stock]
    inception_value: float
    
    @property
    def current_value(self) -> float:
        return sum(s.current_value for s in self.stocks)
    
    def weekly_return(self, previous_value: float) -> float:
        return ((self.current_value / previous_value) - 1) * 100
    
    def total_return(self) -> float:
        return ((self.current_value / self.inception_value) - 1) * 100

def calculate_normalized_chart(portfolio_history: List[Dict],
                               sp500_history: List[Dict],
                               btc_history: List[Dict],
                               inception_value: float,
                               sp500_inception: float,
                               btc_inception: float) -> List[Dict]:
    """Generate normalized chart data (all start at 100)"""
    normalized = []
    for i, p_entry in enumerate(portfolio_history):
        normalized.append({
            'date': p_entry['date'],
            'portfolio_value': p_entry['value'],
            'genai_norm': round(100 * p_entry['value'] / inception_value, 2),
            'spx_close': sp500_history[i]['close'],
            'spx_norm': round(100 * sp500_history[i]['close'] / sp500_inception, 2),
            'btc_close': btc_history[i]['close'],
            'btc_norm': round(100 * btc_history[i]['close'] / btc_inception, 2)
        })
    return normalized
```

**Benefits:**
- Pure functions = easy to test
- No dependencies on external state
- Can reuse in other contexts (backtesting, analysis)
- Clear data flow (input → calculation → output)

---

### 4. `data/validators.py` - Data Validation

**Purpose:** Validate data integrity and consistency

**Responsibilities:**
- Validate date formats
- Check for duplicate weeks
- Verify calculation accuracy
- Sanitize input data

**Key Functions:**
```python
from datetime import datetime
from typing import List, Tuple

class ValidationError(Exception):
    """Raised when data validation fails"""
    pass

def validate_date_format(date_str: str) -> str:
    """Validate and normalize date string"""
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        return date_obj.strftime('%Y-%m-%d')
    except ValueError:
        raise ValidationError(f"Invalid date format: {date_str}")

def validate_no_duplicate_week(master_json: Dict, new_date: str) -> None:
    """Ensure new_date doesn't already exist in master.json"""
    current_date = master_json['meta']['current_date']
    if new_date == current_date:
        raise ValidationError(
            f"Duplicate week: {new_date} already exists in master.json"
        )

def validate_price_data(prices: Dict[str, float], symbol: str) -> None:
    """Validate price data completeness"""
    if not prices:
        raise ValidationError(f"No price data for {symbol}")
    
    for date, price in prices.items():
        if price <= 0:
            raise ValidationError(
                f"Invalid price for {symbol} on {date}: {price}"
            )

def validate_master_json_structure(data: Dict) -> List[str]:
    """Validate master.json has required fields. Return list of errors."""
    errors = []
    required_keys = ['meta', 'stocks', 'portfolio_totals', 
                     'benchmarks', 'portfolio_history', 'normalized_chart']
    
    for key in required_keys:
        if key not in data:
            errors.append(f"Missing required key: {key}")
    
    # ... more structural validation
    return errors
```

**Benefits:**
- Centralized validation logic
- Fail fast with clear error messages
- Reusable across different entry points
- Easy to extend with new validation rules

---

### 5. `ai/client.py` - AI Client Wrapper

**Purpose:** Abstract AI interactions with retry logic

**Responsibilities:**
- Initialize Azure OpenAI client
- Handle retries and backoff
- Manage rate limits
- Provide clean API for prompts

**Key Classes:**
```python
from openai import OpenAI
from typing import Optional
import time

class AIClient:
    """Wrapper for Azure OpenAI API with retry logic"""
    
    def __init__(self, api_key: str, model: str, base_url: str):
        self.api_key = api_key
        self.model = model
        self.client = OpenAI(base_url=base_url, api_key=api_key)
    
    def call(self, system_prompt: str, user_message: str, 
             temperature: float = 0.7, max_retries: int = 3) -> str:
        """Call AI with retry logic and exponential backoff"""
        
        for attempt in range(max_retries):
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
                if 'rate' in str(e).lower() or '429' in str(e):
                    wait_time = 60
                    time.sleep(wait_time)
                    continue
                
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                    continue
                
                raise
        
        raise RuntimeError("AI call failed after all retries")
```

**Benefits:**
- Easy to swap AI providers (OpenAI, Anthropic, etc.)
- Retry logic in one place
- Testable with mock responses
- Clear separation from business logic

---

### 6. `ai/prompts.py` - Prompt Handlers

**Purpose:** Execute Prompts A, B, D with specific logic

**Responsibilities:**
- Load prompt templates
- Execute validation (Prompt A)
- Generate narrative (Prompt B)
- Assemble final HTML (Prompt D)
- Extract structured data from responses

**Key Classes:**
```python
from dataclasses import dataclass
from typing import Dict, Optional
import json
import re

@dataclass
class ValidationResult:
    status: str  # 'pass', 'fail', 'unclear', 'error'
    report: str

class PromptExecutor:
    """Base class for prompt execution"""
    def __init__(self, ai_client: AIClient, prompt_template: str):
        self.ai_client = ai_client
        self.prompt_template = prompt_template

class PromptAValidator(PromptExecutor):
    """Execute Prompt A: Data Validator (non-fatal)"""
    
    def validate(self, master_json: Dict, week_number: int) -> ValidationResult:
        """Run validation, return result dict (never raises)"""
        try:
            user_message = f"""
{self.prompt_template}

Here is master.json with Week {week_number} data:

```json
{json.dumps(master_json, indent=2)}
```
"""
            response = self.ai_client.call(
                "You are the GenAi Chosen Data Validator.",
                user_message,
                temperature=0.3
            )
            
            # Parse response
            status = self._parse_validation_status(response)
            return ValidationResult(status=status, report=response)
            
        except Exception as e:
            return ValidationResult(status='error', report=str(e))
    
    def _parse_validation_status(self, response: str) -> str:
        """Extract status from AI response"""
        response_upper = response.upper()
        
        # Check for explicit markers first
        if 'STATUS: PASS' in response_upper:
            return 'pass'
        elif 'STATUS: FAIL' in response_upper:
            return 'fail'
        
        # Fallback to emoji/keyword detection
        # ... (current logic from portfolio_automation.py)
        
        return 'unclear'

class PromptBNarrative(PromptExecutor):
    """Execute Prompt B: Narrative Writer (fatal on failure)"""
    
    def generate(self, master_json: Dict, week_number: int) -> Tuple[str, Dict]:
        """Generate narrative HTML and SEO metadata. Raises on failure."""
        # Extract summary data
        summary = self._extract_summary(master_json)
        
        user_message = f"""
{self.prompt_template}

Here is summary data for Week {week_number}:
```json
{json.dumps(summary, separators=(',', ':'))}
```
"""
        response = self.ai_client.call(
            "You are the GenAi Chosen Narrative Writer.",
            user_message
        )
        
        # Extract HTML and SEO
        narrative_html = self._extract_html(response)
        seo_json = self._extract_seo(response)
        
        if not narrative_html:
            raise ValueError("Failed to extract narrative HTML")
        
        return narrative_html, seo_json
    
    def _extract_summary(self, master_json: Dict) -> Dict:
        """Extract only essential data for narrative generation"""
        # ... (current logic from _extract_narrative_summary)
    
    def _extract_html(self, response: str) -> Optional[str]:
        """Extract narrative HTML from response"""
        html_match = re.search(r'```html\s*(<div class="prose.*?</div>)\s*```', 
                               response, re.DOTALL)
        return html_match.group(1) if html_match else None
    
    def _extract_seo(self, response: str) -> Dict:
        """Extract SEO JSON from response"""
        json_match = re.search(r'```json\s*({.*?})\s*```', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        return {}

class PromptDAssembler(PromptExecutor):
    """Execute Prompt D: Final HTML Assembler"""
    
    def assemble(self, narrative_html: str, seo_json: Dict, 
                 metadata: Dict, week_number: int) -> str:
        """Generate complete HTML page"""
        user_message = f"""
{self.prompt_template}

**narrative.html:**
```html
{narrative_html}
```

**seo.json:**
```json
{json.dumps(seo_json, indent=2)}
```

**metadata:**
```json
{json.dumps(metadata, indent=2)}
```

Generate complete HTML for Week {week_number}.
"""
        response = self.ai_client.call(
            "You are the GenAi Chosen Final Page Builder.",
            user_message
        )
        
        # Extract HTML
        html_match = re.search(r'<!DOCTYPE html>.*</html>', 
                              response, re.DOTALL | re.IGNORECASE)
        return html_match.group(0) if html_match else response
```

**Benefits:**
- Each prompt handler is independent
- Clear error handling strategy per prompt
- Testable with mock AI responses
- Easy to modify individual prompts

---

### 7. `generators/visuals.py` - Visual Generation

**Purpose:** Generate performance table and chart (deterministic Python)

**Responsibilities:**
- Generate HTML performance table
- Generate SVG performance chart
- Create visuals.json metadata

**Key Classes:**
```python
class PerformanceTableGenerator:
    """Generate HTML table from portfolio data"""
    
    def generate(self, portfolio_data: Dict, week_number: int) -> str:
        """Generate performance_table.html"""
        # Extract data
        meta = portfolio_data['meta']
        ph = portfolio_data['portfolio_history']
        sp500 = portfolio_data['benchmarks']['sp500']
        btc = portfolio_data['benchmarks']['bitcoin']
        
        # Get inception, previous, current
        inception = ph[0]
        previous = ph[-2]
        current = ph[-1]
        
        # Build HTML
        table_html = f"""<div class="myblock-performance-snapshot">
  <table class="myblock-portfolio-table">
    ...
  </table>
</div>"""
        return table_html

class PerformanceChartGenerator:
    """Generate SVG chart from normalized data"""
    
    def generate(self, normalized_data: List[Dict], 
                 dimensions: Tuple[int, int] = (800, 400)) -> str:
        """Generate performance_chart.svg"""
        width, height = dimensions
        
        # Calculate scales
        x_scale = self._calculate_x_scale(normalized_data, width)
        y_scale = self._calculate_y_scale(normalized_data, height)
        
        # Generate SVG
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" 
                     viewBox="0 0 {width} {height}" 
                     class="myblock-chart-svg">
          {self._generate_grid(width, height)}
          {self._generate_lines(normalized_data, x_scale, y_scale)}
          {self._generate_dots(normalized_data, x_scale, y_scale)}
          {self._generate_labels(normalized_data, x_scale, y_scale)}
        </svg>"""
        return svg
    
    def _calculate_x_scale(self, data: List[Dict], width: int):
        # ... scaling logic
    
    def _generate_lines(self, data: List[Dict], x_scale, y_scale) -> str:
        # ... line generation logic
```

**Benefits:**
- Pure functions for deterministic output
- Easy to test with sample data
- Can generate charts offline for testing
- Clear separation from AI logic

---

### 8. `generators/html.py` - HTML Assembly

**Purpose:** Post-process and optimize final HTML

**Responsibilities:**
- Apply standard head metadata
- Inject CSP policies
- Optimize images (fetchpriority, lazy loading)
- Add TLDR components
- Validate HTML structure

**Key Classes:**
```python
class HTMLProcessor:
    """Post-process and optimize HTML"""
    
    def __init__(self, config: Config):
        self.config = config
    
    def apply_standard_head(self, html: str, seo: Dict, 
                           week_number: int) -> str:
        """Replace <head> with standardized metadata"""
        head_markup = self._build_head_markup(seo, week_number)
        new_html = re.sub(r'<head>.*?</head>', head_markup, 
                         html, flags=re.DOTALL)
        return new_html
    
    def inject_tldr_strip(self, html: str) -> str:
        """Add TLDR component after prose div"""
        tldr_markup = """
<div id="tldrStrip" class="tldr-strip mb-10">
  <div class="tldr-metric"><span>Week Change</span><span id="tldrWeek">--</span></div>
  <div class="tldr-metric"><span>Since Inception</span><span id="tldrTotal">--</span></div>
  <div class="tldr-metric"><span>Alpha vs SPX</span><span id="tldrAlpha">--</span></div>
</div>
"""
        # Find prose div and inject after
        prose_pos = html.find('<div class="prose')
        if prose_pos != -1:
            html = html[:prose_pos] + tldr_markup + html[prose_pos:]
        return html
    
    def optimize_images(self, html: str) -> str:
        """Add fetchpriority to hero, lazy loading to others"""
        # Mark first hero image as high priority
        html = re.sub(
            r'<img([^>]*?W\d+\.webp[^>]*)>',
            lambda m: self._add_fetchpriority(m.group(0)),
            html, count=1
        )
        
        # Add lazy loading to remaining images
        html = re.sub(r'<img[^>]*>', self._add_lazy_loading, html)
        return html
    
    def validate_structure(self, html: str) -> List[str]:
        """Validate HTML has required elements. Return list of issues."""
        issues = []
        
        if not html.strip().startswith('<!DOCTYPE'):
            issues.append("Missing DOCTYPE declaration")
        
        if '</html>' not in html.lower():
            issues.append("Missing closing </html> tag")
        
        required = ['<head>', '<body>', '<article>', 'class="prose']
        for elem in required:
            if elem not in html:
                issues.append(f"Missing required element: {elem}")
        
        return issues
```

**Benefits:**
- Reusable HTML utilities
- Clear transformation pipeline
- Easy to add new optimizations
- Testable with sample HTML

---

### 9. `generators/reports.py` - Report Generation

**Purpose:** Generate text reports for data-only mode

**Responsibilities:**
- Format portfolio summary
- Generate stock performance list
- Create benchmark comparison
- Save reports to disk

**Key Functions:**
```python
class DataOnlyReportGenerator:
    """Generate human-readable text reports"""
    
    def generate(self, master_json: Dict, week_number: int) -> str:
        """Create comprehensive data report"""
        sections = [
            self._header(week_number),
            self._metadata(master_json['meta']),
            self._portfolio_summary(master_json),
            self._benchmark_comparison(master_json),
            self._stock_performance(master_json),
            self._generated_files(week_number)
        ]
        return '\n\n'.join(sections)
    
    def _portfolio_summary(self, data: Dict) -> str:
        totals = data['portfolio_totals']
        ph = data['portfolio_history']
        current = ph[-1]
        previous = ph[-2] if len(ph) > 1 else ph[0]
        
        return f"""PORTFOLIO PERFORMANCE
{'-'*80}
Current Value:     ${totals['current_value']:,.2f}
Previous Value:    ${previous['value']:,.2f}
Weekly Change:     {totals['weekly_pct']:+.2f}%
Total Return:      {totals['total_pct']:+.2f}%
Dollar Change:     ${totals['current_value'] - previous['value']:+,.2f}"""
    
    def _stock_performance(self, data: Dict) -> str:
        """Generate sorted stock performance list"""
        stocks = sorted(data['stocks'], 
                       key=lambda s: s['weekly_pct'], 
                       reverse=True)
        
        lines = ["INDIVIDUAL STOCK PERFORMANCE", "-"*80]
        for stock in stocks:
            lines.append(f"{stock['ticker']:6s} - {stock['name']}")
            lines.append(f"  Weekly Change:   {stock['weekly_pct']:+.2f}%")
            lines.append(f"  Total Return:    {stock['total_pct']:+.2f}%")
            lines.append(f"  Current Value:   ${stock['current_value']:,.2f}")
            lines.append("")
        
        return '\n'.join(lines)
```

**Benefits:**
- Reusable reporting utilities
- Easy to add new report formats (JSON, CSV, etc.)
- Testable with sample data

---

### 10. `storage/master_json.py` - Master.json Operations

**Purpose:** Centralize all master.json read/write operations

**Responsibilities:**
- Load master.json
- Save updated master.json (atomic writes)
- Create archives
- Manage legacy snapshots

**Key Classes:**
```python
class MasterJsonManager:
    """Manage master.json file operations"""
    
    def __init__(self, config: Config):
        self.config = config
        self.master_path = config.master_data_dir / "master.json"
        self.archive_dir = config.archive_dir
    
    def load(self) -> Dict:
        """Load master.json from primary location"""
        if not self.master_path.exists():
            raise FileNotFoundError(f"Master data not found: {self.master_path}")
        
        with open(self.master_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def save(self, data: Dict, create_archive: bool = True,
             create_legacy: bool = True) -> None:
        """Save master.json with atomic write + backups"""
        # Atomic write to primary location
        self._atomic_write(self.master_path, data)
        
        # Create timestamped archive
        if create_archive:
            date_str = data['meta']['current_date'].replace('-', '')
            archive_path = self.archive_dir / f"master-{date_str}.json"
            self.archive_dir.mkdir(exist_ok=True)
            self._write_json(archive_path, data)
        
        # Create legacy week snapshot
        if create_legacy:
            week_num = len(data['portfolio_history']) - 1
            legacy_dir = self.config.data_dir / f"W{week_num}"
            legacy_dir.mkdir(exist_ok=True)
            self._write_json(legacy_dir / "master.json", data)
    
    def _atomic_write(self, path: Path, data: Dict) -> None:
        """Atomic file write using temp file + rename"""
        temp_path = path.with_suffix('.tmp')
        try:
            self._write_json(temp_path, data)
            temp_path.replace(path)  # Atomic on POSIX
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise
    
    def _write_json(self, path: Path, data: Dict) -> None:
        """Write JSON with consistent formatting"""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    
    def detect_next_week(self) -> int:
        """Auto-detect next week number from master.json"""
        data = self.load()
        existing_weeks = len(data['portfolio_history']) - 1
        return existing_weeks + 1
```

**Benefits:**
- Atomic writes prevent corruption
- Consistent backup strategy
- Easy to test with mock file system
- Single place to change storage logic

---

### 11. `utils/rate_limiter.py` - Rate Limiting

**Purpose:** Centralized rate limiting logic

**Responsibilities:**
- Track API call timestamps
- Enforce rate limits
- Support multiple APIs with different limits

**Key Classes:**
```python
import time
from typing import Dict

class RateLimiter:
    """Simple rate limiter with per-API tracking"""
    
    def __init__(self, min_interval_seconds: float):
        self.min_interval = min_interval_seconds
        self.last_call_time = 0.0
    
    def wait_if_needed(self) -> None:
        """Block until sufficient time has passed"""
        elapsed = time.time() - self.last_call_time
        if elapsed < self.min_interval:
            wait_time = self.min_interval - elapsed
            time.sleep(wait_time)
        self.last_call_time = time.time()

class MultiAPIRateLimiter:
    """Manage rate limiters for multiple APIs"""
    
    def __init__(self, limits: Dict[str, float]):
        """
        Args:
            limits: {api_name: min_interval_seconds}
        """
        self.limiters = {
            name: RateLimiter(interval) 
            for name, interval in limits.items()
        }
    
    def wait(self, api_name: str) -> None:
        """Wait for specific API"""
        if api_name in self.limiters:
            self.limiters[api_name].wait_if_needed()
```

**Benefits:**
- Reusable across any API
- Thread-safe with minor modifications
- Easy to test timing behavior

---

### 12. `portfolio_automation.py` - Main Orchestrator

**Purpose:** Coordinate all modules to execute workflow

**Responsibilities:**
- Parse command-line arguments
- Initialize all components
- Execute workflow steps in order
- Handle errors and generate reports
- **ONLY orchestration - no business logic**

**Key Structure:**
```python
#!/usr/bin/env python3
"""Portfolio Automation - Main Orchestrator"""

from pathlib import Path
import argparse
import sys
import logging

from config import Config
from data.fetchers import AlphaVantageFetcher, FinnhubFetcher, FallbackDataFetcher
from data.calculators import Portfolio, Stock, calculate_normalized_chart
from data.validators import validate_no_duplicate_week, validate_master_json_structure
from ai.client import AIClient
from ai.prompts import PromptAValidator, PromptBNarrative, PromptDAssembler
from generators.visuals import PerformanceTableGenerator, PerformanceChartGenerator
from generators.html import HTMLProcessor
from generators.reports import DataOnlyReportGenerator
from storage.master_json import MasterJsonManager
from utils.rate_limiter import MultiAPIRateLimiter

class PortfolioAutomation:
    """Orchestrator - delegates work to specialized components"""
    
    def __init__(self, config: Config, week_number: int, mode: str):
        self.config = config
        self.week_number = week_number
        self.mode = mode
        
        # Initialize components
        self.storage = MasterJsonManager(config)
        self.rate_limiters = self._create_rate_limiters()
        self.fetcher = self._create_fetcher()
        self.ai_client = self._create_ai_client() if mode == 'ai' else None
        
        # Report tracking
        self.report = ExecutionReport(week_number)
    
    def _create_rate_limiters(self) -> MultiAPIRateLimiter:
        return MultiAPIRateLimiter({
            'alphavantage': self.config.alphavantage_rate_limit,
            'finnhub': self.config.finnhub_rate_limit,
            'marketstack': self.config.marketstack_rate_limit
        })
    
    def _create_fetcher(self) -> FallbackDataFetcher:
        """Create fetcher with fallback chain"""
        av = AlphaVantageFetcher(
            self.config.alphavantage_key,
            self.rate_limiters.limiters['alphavantage']
        )
        fh = FinnhubFetcher(
            self.config.finnhub_key,
            self.rate_limiters.limiters['finnhub']
        )
        return FallbackDataFetcher(primary=av, fallbacks=[fh])
    
    def _create_ai_client(self) -> AIClient:
        return AIClient(
            self.config.azure_api_key,
            self.config.model,
            self.config.azure_base_url
        )
    
    def run(self) -> None:
        """Execute complete workflow"""
        try:
            # Step 0: Load and validate
            master_json = self.storage.load()
            self._validate_date(master_json)
            
            # Step 1: Fetch data and calculate
            updated_master = self._fetch_and_calculate(master_json)
            self.storage.save(updated_master)
            
            # Step 2: Validate (if AI enabled)
            if self.ai_client:
                self._run_validation(updated_master)
            
            # Step 3: Generate visuals
            visuals = self._generate_visuals(updated_master)
            
            # Step 4: Generate content (or report)
            if self.mode == 'ai':
                self._run_ai_pipeline(updated_master, visuals)
                self._update_index_pages()
            else:
                self._generate_data_report(updated_master)
            
            self.report.mark_success()
            
        except Exception as e:
            self.report.mark_failure(e)
            raise
        finally:
            self.report.print()
    
    def _validate_date(self, master_json: Dict) -> None:
        """Validate no duplicate weeks"""
        new_date = self.config.eval_date or self._latest_market_date()
        validate_no_duplicate_week(master_json, new_date)
        self.validated_date = new_date
    
    def _fetch_and_calculate(self, master_json: Dict) -> Dict:
        """Fetch prices and recalculate portfolio"""
        # Get tickers
        tickers = [s['ticker'] for s in master_json['stocks']]
        
        # Fetch prices (could be concurrent here)
        price_data = {}
        for ticker in tickers:
            price_data[ticker] = self.fetcher.fetch_quote(ticker)
        
        # Build portfolio objects
        stocks = [
            Stock(
                ticker=s['ticker'],
                name=s['name'],
                shares=s['shares'],
                prices={**s['prices'], self.validated_date: price_data[s['ticker']]['close']}
            )
            for s in master_json['stocks']
        ]
        
        portfolio = Portfolio(
            stocks=stocks,
            inception_value=master_json['meta']['inception_value']
        )
        
        # Build updated master.json
        # ... (use calculators to build updated structure)
        
        return updated_master
    
    def _run_validation(self, master_json: Dict) -> None:
        """Run Prompt A validation"""
        validator = PromptAValidator(self.ai_client, self.config.prompt_a)
        result = validator.validate(master_json, self.week_number)
        
        if result.status == 'fail':
            logging.warning("Validation failed but continuing")
        elif result.status == 'pass':
            logging.info("Validation passed")
    
    def _generate_visuals(self, master_json: Dict) -> Dict:
        """Generate table and chart"""
        table_gen = PerformanceTableGenerator()
        chart_gen = PerformanceChartGenerator()
        
        table_html = table_gen.generate(master_json, self.week_number)
        chart_svg = chart_gen.generate(
            master_json['normalized_chart'], 
            self.week_number
        )
        
        return {'table': table_html, 'chart': chart_svg}
    
    def _run_ai_pipeline(self, master_json: Dict, visuals: Dict) -> None:
        """Run Prompts B and D to generate HTML"""
        # Prompt B: Narrative
        prompt_b = PromptBNarrative(self.ai_client, self.config.prompt_b)
        narrative_html, seo_json = prompt_b.generate(master_json, self.week_number)
        
        # Embed visuals into narrative
        narrative_html = narrative_html.replace('{{TABLE}}', visuals['table'])
        narrative_html = narrative_html.replace('{{CHART}}', visuals['chart'])
        
        # Prompt D: Assemble
        prompt_d = PromptDAssembler(self.ai_client, self.config.prompt_d)
        final_html = prompt_d.assemble(
            narrative_html, seo_json,
            master_json['meta'], self.week_number
        )
        
        # Post-process HTML
        processor = HTMLProcessor(self.config)
        final_html = processor.apply_standard_head(final_html, seo_json, self.week_number)
        final_html = processor.inject_tldr_strip(final_html)
        final_html = processor.optimize_images(final_html)
        
        # Save to Posts/
        output_path = self.config.posts_dir / f"GenAi-Managed-Stocks-Portfolio-Week-{self.week_number}.html"
        output_path.write_text(final_html, encoding='utf-8')
    
    def _generate_data_report(self, master_json: Dict) -> None:
        """Generate text report for data-only mode"""
        report_gen = DataOnlyReportGenerator()
        report_text = report_gen.generate(master_json, self.week_number)
        
        report_path = self.config.data_dir / f"W{self.week_number}" / "data_report.txt"
        report_path.parent.mkdir(exist_ok=True)
        report_path.write_text(report_text, encoding='utf-8')
    
    def _update_index_pages(self) -> None:
        """Regenerate posts.html and index.html"""
        # ... (delegate to separate IndexPageGenerator)

class ExecutionReport:
    """Track execution steps and generate report"""
    def __init__(self, week_number: int):
        self.week_number = week_number
        self.steps = []
        self.start_time = datetime.now()
        self.success = False
    
    def add_step(self, name: str, status: str, description: str):
        # ...
    
    def mark_success(self):
        self.success = True
    
    def mark_failure(self, error: Exception):
        self.success = False
        self.error = error
    
    def print(self):
        # ... (formatted report output)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--week', type=str, default='auto')
    parser.add_argument('--data-source', choices=['ai', 'data-only'], default='data-only')
    parser.add_argument('--eval-date', type=str)
    # ... more args
    
    args = parser.parse_args()
    
    # Load config
    config = Config()
    errors = config.validate()
    if errors:
        for error in errors:
            logging.error(error)
        sys.exit(1)
    
    # Determine week number
    storage = MasterJsonManager(config)
    week_number = int(args.week) if args.week != 'auto' else storage.detect_next_week()
    
    # Run automation
    automation = PortfolioAutomation(config, week_number, args.data_source)
    automation.run()

if __name__ == '__main__':
    main()
```

**Total Lines:** ~200 (down from 2,699!)

**Benefits:**
- Clear, linear workflow
- All logic delegated to specialized modules
- Easy to understand what happens when
- Simple to modify workflow order
- Testable by mocking components

---

## Migration Strategy

### Phase 1: Extract Data Layer (Week 1)
1. Create `config.py`
2. Create `data/fetchers.py`
3. Create `data/calculators.py`
4. Create `utils/rate_limiter.py`
5. Update `portfolio_automation.py` to use new modules
6. Test data fetching and calculations

**Deliverable:** Data layer fully extracted and tested

### Phase 2: Extract AI Layer (Week 2)
1. Create `ai/client.py`
2. Create `ai/prompts.py`
3. Create `ai/seo.py`
4. Update orchestrator to use AI modules
5. Test Prompts A, B, D independently

**Deliverable:** AI layer fully extracted and tested

### Phase 3: Extract Generators (Week 3)
1. Create `generators/visuals.py`
2. Create `generators/html.py`
3. Create `generators/reports.py`
4. Update orchestrator
5. Test visual generation offline

**Deliverable:** All generators extracted and tested

### Phase 4: Extract Storage (Week 4)
1. Create `storage/master_json.py`
2. Create `storage/file_manager.py`
3. Update orchestrator
4. Test atomic writes and backups

**Deliverable:** Storage layer complete

### Phase 5: Finalize Orchestrator (Week 5)
1. Simplify `portfolio_automation.py` to pure orchestration
2. Add `ExecutionReport` class
3. Comprehensive integration testing
4. Performance benchmarking
5. Documentation

**Deliverable:** Fully refactored system ready for production

---

## Testing Strategy

### Unit Tests (Per Module)
```python
# tests/data/test_fetchers.py
def test_alphavantage_fetcher():
    fetcher = AlphaVantageFetcher(api_key="fake", rate_limiter=mock_limiter)
    with patch('requests.Session.get') as mock_get:
        mock_get.return_value.json.return_value = {...}
        result = fetcher.fetch_quote("AAPL")
        assert result['close'] == 150.0
        assert result['source'] == 'Alpha Vantage'

# tests/data/test_calculators.py
def test_portfolio_total_return():
    stocks = [Stock(ticker="AAPL", shares=10, prices={"2025-01-01": 100, "2025-01-08": 110})]
    portfolio = Portfolio(stocks=stocks, inception_value=1000)
    assert portfolio.total_return() == 10.0

# tests/ai/test_prompts.py
def test_prompt_a_validation_pass():
    mock_client = Mock()
    mock_client.call.return_value = "STATUS: PASS - All calculations correct"
    
    validator = PromptAValidator(mock_client, "prompt template")
    result = validator.validate({...}, week_number=1)
    
    assert result.status == 'pass'
```

### Integration Tests
```python
# tests/integration/test_workflow.py
def test_full_workflow_data_only_mode():
    config = Config()
    automation = PortfolioAutomation(config, week_number=1, mode='data-only')
    
    automation.run()
    
    # Verify files created
    assert (config.data_dir / "W1" / "data_report.txt").exists()
    assert (config.master_data_dir / "master.json").exists()
```

### Performance Tests
```python
# tests/performance/test_concurrent_fetching.py
def test_concurrent_vs_sequential_fetching():
    """Verify concurrent fetching is faster"""
    tickers = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"]
    
    # Sequential
    start = time.time()
    for ticker in tickers:
        fetcher.fetch_quote(ticker)
    sequential_time = time.time() - start
    
    # Concurrent
    start = time.time()
    fetcher.fetch_quotes_concurrent(tickers, max_workers=3)
    concurrent_time = time.time() - start
    
    assert concurrent_time < sequential_time * 0.6  # At least 40% faster
```

---

## Expected Benefits

### Quantitative Improvements
| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Lines per file | 2,699 | <400 | 85% reduction |
| Testability | 0% coverage | 80%+ coverage | ∞ improvement |
| Module coupling | High (everything) | Low (interfaces) | 90% reduction |
| Time to add feature | Days | Hours | 75% faster |
| Concurrent execution | No | Yes | 3-5x faster |

### Qualitative Improvements
1. **Maintainability:** Each module < 400 lines, easy to understand
2. **Testability:** All modules independently testable
3. **Reusability:** Can reuse fetchers/calculators in other projects
4. **Debugging:** Isolated failures, clear stack traces
5. **Extension:** Add new data sources without touching core logic
6. **Onboarding:** New developers can understand one module at a time
7. **Reliability:** Better error isolation and recovery

---

## Risks & Mitigation

### Risk 1: Breaking Changes During Migration
**Mitigation:** 
- Keep original `portfolio_automation.py` as backup
- Migrate incrementally (one module at a time)
- Comprehensive integration tests at each phase
- Maintain backward compatibility for CLI arguments

### Risk 2: Performance Regression
**Mitigation:**
- Benchmark before/after each phase
- Profile critical paths (API calls, calculations)
- Optimize hot paths if needed
- Use concurrent fetching to improve performance

### Risk 3: Test Coverage Gaps
**Mitigation:**
- Write tests before refactoring each module
- Aim for 80%+ coverage on business logic
- Use integration tests to catch interface issues

### Risk 4: Over-Engineering
**Mitigation:**
- Follow YAGNI (You Aren't Gonna Need It)
- Start with simplest working design
- Add abstractions only when needed
- Review design after each phase

---

## Conclusion

The current monolithic architecture (2,699 lines in one file) is difficult to maintain, test, and extend. The proposed modular architecture splits responsibilities into 8 focused modules:

1. **config.py** - Configuration
2. **data/fetchers.py** - API data fetching
3. **data/calculators.py** - Portfolio math
4. **ai/prompts.py** - AI prompt execution
5. **generators/visuals.py** - Table & chart generation
6. **generators/html.py** - HTML processing
7. **storage/master_json.py** - File operations
8. **portfolio_automation.py** - Orchestration (~200 lines)

**Benefits:**
- 85% reduction in file size
- Independent testability
- Clear separation of concerns
- Easy to add features
- Better error isolation
- Enables concurrent execution

**Effort:** 3-5 weeks for complete migration with testing

**Recommendation:** Proceed with Phase 1 (Data Layer) as proof of concept. If successful, continue with remaining phases.
