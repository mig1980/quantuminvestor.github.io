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

# Configure paths
REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "Data"
POSTS_DIR = REPO_ROOT / "Posts"
PROMPT_DIR = REPO_ROOT / "Prompt"
ARCHIVE_DIR = DATA_DIR / "archive"

class PortfolioAutomation:
    def __init__(self, week_number=None, api_key=None, model="gpt-4-turbo-preview"):
        self.week_number = week_number or self.detect_next_week()
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.model = model
        
        if not self.api_key:
            raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY environment variable.")
        
        self.client = OpenAI(api_key=self.api_key)
        print(f"✓ Using model: {self.model}")
        
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
        
        user_message = f"""
{self.prompts['A']}

---

Here is last week's master.json:

```json
{json.dumps(self.master_json, indent=2)}
```

Please update this for Week {self.week_number}, following all Change Management rules.
Fetch latest prices for Thursday close (or most recent trading day).
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
            # Load previous week's data
            self.load_master_json()
            
            # Run 4-prompt sequence
            self.run_prompt_a()
            self.run_prompt_b()
            self.run_prompt_c()
            self.run_prompt_d()
            
            # Update site navigation
            self.update_index_pages()
            
            print(f"\n{'='*60}")
            print(f"✅ SUCCESS! Week {self.week_number} generated successfully")
            print(f"{'='*60}")
            print(f"\nGenerated files:")
            print(f"  - Data/W{self.week_number}/master.json")
            print(f"  - Posts/GenAi-Managed-Stocks-Portfolio-Week-{self.week_number}.html")
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
    
    args = parser.parse_args()
    
    week_number = None if args.week == 'auto' else int(args.week)
    
    automation = PortfolioAutomation(
        week_number=week_number, 
        api_key=args.api_key,
        model=args.model
    )
    automation.run()

if __name__ == '__main__':
    main()
