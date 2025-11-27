"""
Stage 1: Generate Newsletter Narrative
Extracts key insights from blog post and portfolio data, creates narrative JSON.
"""

import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict

from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def retry_with_backoff(func, max_retries=3, initial_delay=1.0, backoff_factor=2.0):
    """
    Retry a function with exponential backoff for transient failures.

    Args:
        func: Function to execute
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        backoff_factor: Multiplier for delay on each retry

    Returns:
        Function result

    Raises:
        Exception: If all retries are exhausted
    """
    delay = initial_delay
    last_exception = None

    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            last_exception = e
            error_type = type(e).__name__

            # Don't retry on validation errors or missing config
            if error_type in ["ValueError", "FileNotFoundError", "KeyError"]:
                raise

            if attempt < max_retries - 1:
                logging.warning(
                    f"Attempt {attempt + 1}/{max_retries} failed: {error_type}: {e}. Retrying in {delay}s..."
                )
                time.sleep(delay)
                delay *= backoff_factor
            else:
                logging.error(f"All {max_retries} attempts failed: {error_type}")

    raise last_exception


def get_latest_week_number() -> int:
    """Auto-detect latest week from Posts directory"""
    posts_dir = Path(__file__).parent.parent / "Posts"

    if not posts_dir.exists():
        raise FileNotFoundError(f"Posts directory not found: {posts_dir}")

    week_numbers = []
    pattern = re.compile(r"GenAi-Managed-Stocks-Portfolio-Week-(\d+)\.html")

    for file in posts_dir.glob("GenAi-Managed-Stocks-Portfolio-Week-*.html"):
        match = pattern.match(file.name)
        if match:
            week_numbers.append(int(match.group(1)))

    if not week_numbers:
        raise ValueError("No weekly blog posts found in Posts directory")

    return max(week_numbers)


def extract_blog_sections(html_content: str) -> Dict[str, str]:
    """
    Extract narrative sections from blog post HTML.

    Args:
        html_content: Raw HTML content of blog post

    Returns:
        Dictionary with 'opening', 'top_movers', 'portfolio_progress' sections
    """
    soup = BeautifulSoup(html_content, "html.parser")

    sections = {"opening": "", "top_movers": "", "portfolio_progress": ""}

    # Extract opening paragraph (usually has class text-xl or first p after h1)
    opening = soup.find("p", class_="text-xl")
    if opening:
        sections["opening"] = opening.get_text(strip=True)
    else:
        # Fallback: first paragraph
        first_p = soup.find("p")
        if first_p:
            sections["opening"] = first_p.get_text(strip=True)
        else:
            logging.warning("No opening paragraph found in blog post")

    # Extract "Top Movers" section
    found_top_movers = False
    for heading in soup.find_all(["h2", "h3"]):
        heading_text = heading.get_text(strip=True)
        if "top movers" in heading_text.lower():
            top_movers_paragraphs: list[str] = []
            current = heading.find_next_sibling()
            while current and len(top_movers_paragraphs) < 3:
                if current.name == "p":
                    top_movers_paragraphs.append(current.get_text(strip=True))
                elif current.name in ["h2", "h3"]:
                    break
                current = current.find_next_sibling()
            sections["top_movers"] = " ".join(top_movers_paragraphs)
            found_top_movers = True
            break

    if not found_top_movers:
        logging.warning("'Top Movers' section not found in blog post")

    # Extract "Portfolio Progress" section
    found_portfolio_progress = False
    for heading in soup.find_all(["h2", "h3"]):
        heading_text = heading.get_text(strip=True)
        if "portfolio progress" in heading_text.lower():
            progress_paragraphs: list[str] = []
            current = heading.find_next_sibling()
            while current and len(progress_paragraphs) < 2:
                if current.name == "p":
                    progress_paragraphs.append(current.get_text(strip=True))
                elif current.name in ["h2", "h3"]:
                    break
                current = current.find_next_sibling()
            sections["portfolio_progress"] = " ".join(progress_paragraphs)
            found_portfolio_progress = True
            break

    if not found_portfolio_progress:
        logging.warning("'Portfolio Progress' section not found in blog post")

    return sections


def calculate_week_date_range(current_date_str: str) -> str:
    """
    Calculate Monday-Friday date range for the newsletter.
    current_date_str is typically a Thursday (when portfolio runs) in YYYY-MM-DD format.
    Returns the Monday-Friday range for that week, like "Nov 17 to Nov 21, 2025"
    """
    # Parse the current date (Thursday)
    current_date = datetime.strptime(current_date_str, "%Y-%m-%d")

    # Get the weekday (0=Monday, 6=Sunday)
    weekday = current_date.weekday()

    # Calculate Monday of the same week (go back to Monday)
    days_since_monday = weekday  # 0 if already Monday, 1 if Tuesday, etc.
    monday = current_date - timedelta(days=days_since_monday)

    # Calculate Friday of the same week (Monday + 4 days)
    friday = monday + timedelta(days=4)

    # Format dates
    monday_str = monday.strftime("%b %d")
    friday_str = friday.strftime("%b %d, %Y")

    return f"{monday_str} to {friday_str}"


def generate_narrative(week_num: int) -> Dict[str, Any]:
    """
    Generate newsletter narrative from blog post and portfolio data.
    Returns narrative JSON and uploads to Azure Blob Storage.
    """
    logging.info(f"Generating narrative for Week {week_num}")

    # Paths
    base_dir = Path(__file__).parent.parent
    data_path = base_dir / f"Data/W{week_num}/master.json"
    blog_path = base_dir / f"Posts/GenAi-Managed-Stocks-Portfolio-Week-{week_num}.html"

    # Validate files exist
    if not data_path.exists():
        raise FileNotFoundError(f"Data file not found: {data_path}")
    if not blog_path.exists():
        raise FileNotFoundError(f"Blog post not found: {blog_path}")

    # Load portfolio data
    with open(data_path, "r", encoding="utf-8") as f:
        portfolio_data = json.load(f)

    # Calculate date range (Monday to Friday of the week)
    current_date = portfolio_data.get("meta", {}).get("current_date", "")
    if not current_date:
        raise ValueError("current_date not found in master.json meta section")
    date_range = calculate_week_date_range(current_date)
    logging.info(f"Week {week_num} date range: {date_range}")

    # Load blog post HTML
    with open(blog_path, "r", encoding="utf-8") as f:
        blog_html = f.read()

    # Extract sections
    sections = extract_blog_sections(blog_html)

    # Prepare AI prompt
    prompt = f"""You are analyzing a weekly blog post about an AI-managed stock portfolio to extract newsletter content.

APPROVED_ICONS (Material Design Icons - use EXACTLY these names):
- Technology: "laptop", "chip", "code-tags", "robot", "brain", "cloud"
- Finance: "bank", "cash", "currency-usd", "chart-line", "trending-up", "finance"
- Healthcare: "medical-bag", "hospital-box", "pill", "heart-pulse", "dna"
- Energy: "flash", "oil", "solar-power", "water", "gas-station", "lightning-bolt"
- Industrial: "factory", "wrench", "cog", "package-variant", "truck"
- Consumer: "cart", "shopping", "food", "home", "tshirt-crew"
- Communications: "phone", "antenna", "wifi", "signal", "cellphone"
- Materials: "gold", "diamond-stone", "hammer", "barrel"
- Real Estate: "office-building", "home-city", "domain"
- Utilities: "power-plug", "water-pump", "fire"
- Performance: "trophy", "rocket", "target", "star", "fire", "speedometer"
- Analysis: "database", "chart-areaspline", "chart-bar", "chart-pie", "magnify"
- Market: "earth", "shield-check", "scale-balance", "swap-horizontal"

For each key_insight, select an icon that best matches the sector/theme from APPROVED_ICONS list above.

BLOG POST SECTIONS:

Opening Paragraph:
{sections['opening']}

Top Movers Section:
{sections['top_movers']}

Portfolio Progress:
{sections['portfolio_progress']}

PORTFOLIO DATA (master.json):
{json.dumps(portfolio_data, indent=2)}

TASK:
Extract and condense the blog post into newsletter-ready narrative elements. Focus on clarity, conciseness, and alignment with the blog's tone.

OUTPUT FORMAT (JSON):
{{
  "week_number": {week_num},
  "date_range": "{date_range}",
  "subject_line": "Generate as: Week X: [%] | [Key Theme] (under 50 chars, no emoji)",
  "preheader": "First 50-60 characters for inbox preview",
  "opening_paragraph": "3-4 sentences summarizing weekly performance with richer context. Include: (1) Overall portfolio performance with exact percentage, (2) Key market drivers or events that influenced the week, (3) How the portfolio responded to these conditions, (4) A brief transition to the deeper analysis that follows.",
  "key_insights": [
    {{
      "title": "Insight title (3-5 words)",
      "description": "2-3 sentence explanation with more context about sector trends, stock-specific catalysts, or market dynamics",
      "icon": "Select appropriate icon from APPROVED_ICONS list",
      "emoji": "Fallback emoji for Outlook (single character)"
    }},
    {{
      "title": "Insight title (3-5 words)",
      "description": "2-3 sentence explanation with more context about sector trends, stock-specific catalysts, or market dynamics",
      "icon": "Select appropriate icon from APPROVED_ICONS list",
      "emoji": "Fallback emoji for Outlook (single character)"
    }},
    {{
      "title": "Insight title (3-5 words)",
      "description": "2-3 sentence explanation with more context about sector trends, stock-specific catalysts, or market dynamics",
      "icon": "Select appropriate icon from APPROVED_ICONS list",
      "emoji": "Fallback emoji for Outlook (single character)"
    }}
  ],
  "performance_data": {{
    "portfolio_value": "Extract from portfolio_data.portfolio_totals.current_value",
    "weekly_change": "Extract from portfolio_data.portfolio_totals.weekly_pct",
    "total_return": "Extract from portfolio_data.portfolio_totals.total_pct",
    "sp500_weekly": "Extract from portfolio_data.benchmarks.sp500.history[-1].weekly_pct",
    "sp500_total": "Extract from portfolio_data.benchmarks.sp500.history[-1].total_pct",
    "bitcoin_weekly": "Extract from portfolio_data.benchmarks.bitcoin.history[-1].weekly_pct",
    "bitcoin_total": "Extract from portfolio_data.benchmarks.bitcoin.history[-1].total_pct",
    "top_performer": {{"ticker": "Find stock with highest weekly_pct", "change": "percentage"}},
    "worst_performer": {{"ticker": "Find stock with lowest weekly_pct", "change": "percentage"}}
  }},
  "market_context": "3-4 sentences covering what happened during the week. Structure: (1) Key events or macroeconomic developments that drove market action, (2) How different sectors responded (winners/losers and why), (3) Investor sentiment and market positioning shifts observed in the blog.",
  "market_outlook": "2-3 sentences covering forward expectations. Structure: (1) Short-term outlook (next 1-2 weeks): anticipated catalysts, technical levels, or momentum expectations from the blog, (2) Mid-term outlook (1-3 months): broader trends, positioning adjustments, or thematic opportunities mentioned in the blog.",
  "benchmark_comparison": {{
    "portfolio_weekly": "Extract from portfolio_data.portfolio_totals.weekly_pct",
    "sp500_weekly": "Extract from portfolio_data.benchmarks.sp500.history[-1].weekly_pct",
    "bitcoin_weekly": "Extract from portfolio_data.benchmarks.bitcoin.history[-1].weekly_pct",
    "summary": "1-2 sentences comparing the GenAi portfolio's weekly performance against S&P 500 and Bitcoin benchmarks"
  }},
  "call_to_action_url": "https://quantuminvestor.net/Posts/GenAi-Managed-Stocks-Portfolio-Week-{week_num}.html",
  "tone": "Describe tone: honest/bullish/bearish/neutral/cautious"
}}

EXTRACTION RULES:
1. **Opening paragraph**: 3-4 sentences with richer narrative context. Go beyond raw numbers to tell the story: What market forces shaped the week? How did the portfolio respond? Set up the deeper analysis to follow.
2. **Key insights**: Extract 2-3 main points from "Top Movers" section with EXPANDED explanations (2-3 sentences each). Include more detail about why stocks moved, sector dynamics, or broader market implications. MUST include "icon" field (from APPROVED_ICONS list) and "emoji" field (single character fallback).
3. **Keep numbers exact**: Use precise percentages from master.json
4. **Mirror tone**: Match blog post's sentiment (bullish/bearish/neutral)
5. **No new analysis**: Only condense existing blog content, but capture MORE of the context and reasoning from the blog
6. **Subject line**: Format as "Week X: [%] | [Key Theme]" (under 50 chars, no emoji)
7. **Preheader**: Compelling 50-60 char summary for inbox preview
8. **Format percentages**: Always include +/- sign, 2 decimal places
9. **CRITICAL - Portfolio Composition**: The portfolio contains ONLY STOCKS. S&P 500 and Bitcoin are BENCHMARK COMPARISONS for performance tracking, NOT portfolio holdings. Do not refer to "all three assets" or imply the portfolio holds Bitcoin or S&P 500 ETFs. Correct phrasing: "The portfolio declined X% while the S&P 500 fell Y% and Bitcoin dropped Z%" or "The stock portfolio underperformed/outperformed the S&P 500 benchmark."
10. **Market Context (What Happened)**: Extract 3-4 substantive sentences covering: (a) Key events, economic data, or policy developments that drove market action during the week, (b) How different sectors and the portfolio responded (winners/losers and why), (c) Shifts in investor sentiment, risk appetite, or market positioning mentioned in the blog.
11. **Market Outlook (Forward View)**: Extract 2-3 sentences covering: (a) Short-term outlook (1-2 weeks): Near-term catalysts, technical levels, or momentum continuation/reversal expectations from the blog, (b) Mid-term outlook (1-3 months): Broader trends, sector rotation opportunities, or strategic positioning themes discussed in the blog.
12. **Benchmark Comparison Section**: Always include a benchmark_comparison object with exact weekly percentages for the GenAi portfolio, S&P 500, and Bitcoin. Add a 1-2 sentence summary comparing the portfolio's performance against both benchmarks (e.g., "The portfolio underperformed both benchmarks this week" or "The portfolio outperformed the S&P 500 but lagged Bitcoin").

CRITICAL JSON FORMATTING REQUIREMENTS:
- Your response MUST be valid, parseable JSON
- Use double quotes for all strings and property names
- Ensure all arrays end with ] and objects end with }}
- Do not add trailing commas after the last item in arrays or objects
- Verify all opening brackets {{ [ have matching closing brackets }} ]
- Each key_insights item must be a complete object with ALL required properties: "title", "description", "icon", "emoji"
- All numeric values should be numbers, not strings (unless specified as strings in the format)
- Check that every opening quote has a matching closing quote
- Escape any quotes within string values using \"
- Replace problematic characters: Use regular hyphens (-) instead of en-dashes (–) or em-dashes (—)
- For long descriptions, use regular spaces and hyphens, avoid special Unicode characters
- Do not include any text before or after the JSON object
- Validate that each closing brace/bracket matches its opening pair at the correct nesting level

BEFORE RESPONDING:
1. Write out the complete JSON structure
2. Count opening and closing braces/brackets to ensure they match
3. Verify no trailing commas exist
4. Confirm all string quotes are properly closed
5. Test that all special characters are escaped or replaced with standard ASCII equivalents

OUTPUT: Valid JSON only, no markdown formatting or code blocks. Triple-check JSON syntax before responding."""  # nosec B608

    logging.info("Calling Azure OpenAI API")

    # Configure Azure OpenAI client
    azure_api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    if not azure_api_key:
        raise ValueError("AZURE_OPENAI_API_KEY environment variable not set")

    from openai import AzureOpenAI

    azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    if not azure_endpoint:
        raise ValueError("AZURE_OPENAI_ENDPOINT environment variable not set")

    client = AzureOpenAI(
        api_key=azure_api_key,
        api_version="2024-10-21",
        azure_endpoint=azure_endpoint,
    )

    # Call Azure OpenAI API
    deployment_name = os.environ.get("AZURE_OPENAI_DEPLOYMENT")
    if not deployment_name:
        raise ValueError("AZURE_OPENAI_DEPLOYMENT environment variable not set")

    def call_openai_api():
        response = client.chat.completions.create(
            model=deployment_name,
            messages=[
                {
                    "role": "system",
                    "content": "You extract newsletter narratives from blog posts. Output valid JSON only, no markdown.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content.strip()

    # Call Azure OpenAI with retry logic
    try:
        narrative_json = retry_with_backoff(call_openai_api, max_retries=3)

        # Remove markdown code fences if present
        if narrative_json.startswith("```"):
            narrative_json = re.sub(r"^```(?:json)?\n", "", narrative_json)
            narrative_json = re.sub(r"\n```$", "", narrative_json)
            narrative_json = narrative_json.strip()

    except Exception as e:
        logging.error(f"Azure OpenAI API error: {e}")
        raise

    # Parse to validate JSON
    try:
        narrative_data = json.loads(narrative_json)
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON response from OpenAI: {e}")
        logging.error(f"Full response (first 1000 chars):\n{narrative_json[:1000]}")

        # Save the invalid JSON for debugging
        error_log = Path(__file__).parent.parent / "newsletters" / f"week{week_num}_error.json"
        with open(error_log, "w", encoding="utf-8") as f:
            f.write(narrative_json)
        logging.error(f"Saved full response to: {error_log}")
        raise

    # Validate required fields
    required_fields = [
        "week_number",
        "subject_line",
        "preheader",
        "opening_paragraph",
        "key_insights",
        "performance_data",
        "market_context",
        "market_outlook",
        "call_to_action_url",
    ]
    missing_fields = [field for field in required_fields if field not in narrative_data]

    if missing_fields:
        raise ValueError(f"AI response missing required fields: {', '.join(missing_fields)}")

    # Validate key_insights structure
    if not isinstance(narrative_data.get("key_insights"), list):
        raise ValueError("key_insights must be a list")

    if len(narrative_data["key_insights"]) < 2:
        logging.warning(f"Only {len(narrative_data['key_insights'])} key insights generated (expected 2-3)")

    # Save locally for review
    output_dir = base_dir / "newsletters"
    output_dir.mkdir(exist_ok=True)

    local_path = output_dir / f"week{week_num}_narrative.json"
    with open(local_path, "w", encoding="utf-8") as f:
        json.dump(narrative_data, f, indent=2)

    logging.info(f"Narrative generated: {narrative_data.get('subject_line', 'N/A')}")

    return narrative_data


if __name__ == "__main__":
    try:
        # Auto-detect latest week or use command-line argument
        if len(sys.argv) > 1:
            week = int(sys.argv[1])
        else:
            week = get_latest_week_number()
            logging.info(f"Auto-detected latest week: {week}")

        narrative = generate_narrative(week)

        print("\n" + "=" * 60)
        print("📋 STAGE 1 COMPLETE")
        print("=" * 60)
        print(f"✅ Narrative JSON created")
        print(f"📂 Local file: newsletters/week{week}_narrative.json")

    except Exception as e:
        logging.error(f"Script failed: {e}", exc_info=True)
        sys.exit(1)
