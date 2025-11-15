# GitHub Actions Automation Setup

This document explains how to configure and use the automated weekly portfolio update system.

## Overview

The automation runs every **Thursday at 4:45 PM Eastern Time** via GitHub Actions. It:

1. Loads the previous week's `master.json`
2. Runs the 4-prompt sequence (A → B → C → D)
3. Generates a new weekly HTML post
4. Updates `index.html` and `posts.html`
5. Commits and pushes changes to your repository

---

## Initial Setup

### 1. Get an OpenAI API Key

1. Go to [OpenAI Platform](https://platform.openai.com/api-keys)
2. Create a new API key
3. Copy the key (starts with `sk-...`)
4. **Important:** You'll need GPT-4 access (paid account required)

**Cost estimate:** ~$0.50-$2.00 per weekly run depending on data size

### 2. Add API Key to GitHub Secrets

1. Go to your GitHub repository
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `OPENAI_API_KEY`
5. Value: Paste your OpenAI API key
6. Click **Add secret**

### 3. Verify File Structure

Ensure your repository has this structure:

```
My-blog/
├── .github/
│   └── workflows/
│       └── weekly-portfolio-update.yml  ✓ Created
├── scripts/
│   ├── portfolio_automation.py          ✓ Created
│   └── requirements.txt                 ✓ Created
├── Prompt/
│   ├── Prompt-A-v5.3A.md               ✓ Exists
│   ├── Prompt-B-v5.4B.md               ✓ Exists
│   ├── Prompt-C-v5.4C.md               ✓ Exists
│   └── Prompt-D-v5.4D.md               ✓ Exists
├── Data/
│   ├── W5/
│   │   └── master.json                 ✓ Latest week
│   └── archive/                        (auto-created)
└── Posts/                              (generated posts go here)
```

---

## Testing the Automation

### Local Testing (Recommended First)

**Requirements:**
- Python 3.8+ (Python 3.11 recommended)
- OpenAI API key with GPT-4 access
- pip (Python package manager)

**Steps:**

1. Install dependencies:
   ```powershell
   cd c:\Users\mgavril\Documents\GitHub\My-blog
   pip install -r scripts/requirements.txt
   ```
   
   **Note:** The script uses the latest OpenAI Python SDK (v1.12.0+) with the modern client pattern.

2. Set your API key:
   ```powershell
   $env:OPENAI_API_KEY="sk-your-key-here"
   ```

3. Run the automation:
   ```powershell
   # Auto-detect next week number
   python scripts/portfolio_automation.py
   
   # Or specify week number
   python scripts/portfolio_automation.py --week 6
   
   # Use a different/cheaper model
   python scripts/portfolio_automation.py --week 6 --model gpt-4-turbo
   ```

4. Review generated files:
   - `Data/W6/master.json`
   - `Posts/GenAi-Managed-Stocks-Portfolio-Week-6.html`
   - `Data/archive/master-20251114.json`

**Command-line options:**
- `--week <number>` : Specify week number (default: auto-detect)
- `--model <name>` : OpenAI model (default: gpt-4-turbo-preview)
- `--api-key <key>` : API key (default: from OPENAI_API_KEY env var)

### GitHub Actions Testing

**Manual Trigger:**

1. Go to your repository on GitHub
2. Navigate to **Actions** tab
3. Click **Weekly Portfolio Update** workflow
4. Click **Run workflow** dropdown
5. (Optional) Enter a week number, or leave blank for auto-detect
6. Click **Run workflow**

**Monitor the run:**
- Watch the job progress in real-time
- Check logs if any step fails
- Review the workflow summary for generated files

---

## Schedule Configuration

The workflow runs automatically every Thursday at 4:45 PM Eastern Time.

**Cron schedule:** `45 20 * * 4`
- `45` = 45th minute
- `20` = 8 PM UTC (4 PM EDT, 3 PM EST—adjust if needed)
- `*` = every day of month
- `*` = every month
- `4` = Thursday (0=Sunday, 4=Thursday)

**Daylight Saving Time Note:**
- The schedule uses **20:45 UTC** which equals **4:45 PM EDT** (March-November)
- During **EST** (November-March), this becomes **3:45 PM EST**
- To keep it at 4:45 PM year-round during EST, change to `45 21 * * 4` (21:45 UTC)

**To adjust the schedule:**

Edit `.github/workflows/weekly-portfolio-update.yml`:

```yaml
schedule:
  - cron: '45 20 * * 4'  # Change time here
```

---

## Workflow Behavior

### What Happens Automatically

1. **Data Retrieval**: Prompt A fetches latest stock prices (Thursday close)
2. **Narrative Generation**: Prompt B writes the weekly analysis
3. **Visual Creation**: Prompt C generates table and chart
4. **HTML Assembly**: Prompt D creates the final page
5. **Git Commit**: Changes are committed with message like:
   ```
   chore: automated weekly portfolio update (Week 2025-11-14)
   ```

### What You Need to Manually Review

- **Content accuracy**: Review the generated post for correctness
- **Index/posts pages**: The script creates placeholders—you may need to manually update card HTML
- **Data quality**: Verify prices fetched by Prompt A match official closes

---

## Troubleshooting

### Workflow Fails: "OpenAI API key not found"

**Solution:** Add `OPENAI_API_KEY` to GitHub Secrets (see Setup section)

### Workflow Fails: "Cannot find master.json for Week X"

**Solution:** Ensure previous week's data exists in `Data/WX/master.json`

### Workflow Fails: Rate limit error

**Solution:** OpenAI rate limits can trigger during high usage. Wait a few minutes and re-run.

### Workflow Fails: "Missing prompt files"

**Cause:** One or more Prompt-*.md files not found

**Solution:**
1. Verify all 4 files exist in `Prompt/` folder:
   - `Prompt-A-v5.3A.md`
   - `Prompt-B-v5.4B.md`
   - `Prompt-C-v5.4C.md`
   - `Prompt-D-v5.4D.md`
2. The script validates prompts on startup and will fail fast if any are missing

### Workflow Fails: "Could not extract valid master.json"

**Cause:** Prompt A response didn't return properly formatted JSON

**Solution:**
1. Check workflow logs to see GPT-4's actual response
2. Verify previous week's `master.json` is valid JSON
3. If needed, manually fix the generated `Data/WX/master.json`
4. The script now has multiple fallback JSON extraction patterns

### Workflow Fails: "Could not extract narrative HTML"

**Cause:** Prompt B response format unexpected

**Solution:**
1. Review workflow logs for the full GPT-4 response
2. The script will use fallback SEO metadata if extraction fails
3. You can manually create the narrative HTML following Week 5 style

### Generated HTML looks wrong

**Solution:** 
1. Check Prompt files are up-to-date
2. Verify `master.json` data is clean
3. Review GPT-4 response in workflow logs
4. Manually edit the HTML if needed
5. The script now includes better error handling and fallback patterns

### Warnings during generation

The script now includes validation checks that may show warnings:

- **"Warning: Generated HTML doesn't start with DOCTYPE"** - Non-critical, but check final HTML structure
- **"Warning: Missing expected elements"** - Lists missing HTML elements (head, body, etc.)
- **"Could not extract performance table/chart"** - Prompt C didn't generate visuals correctly
- **"Could not find insertion point"** - Table/chart embedding failed, will need manual insertion

These are informational and won't stop the workflow, but should be reviewed.

### Schedule not triggering

**Possible causes:**
- Repository must have at least one commit after adding the workflow
- GitHub Actions must be enabled (Settings → Actions → Allow all actions)
- Default branch must be `main` or adjust workflow `on:` section

---

## Known Limitations

### Price Fetching

**Current behavior:** Prompt A relies on GPT-4 to fetch stock prices, which:
- May not have access to real-time data
- Could return stale or incorrect prices
- Depends on GPT-4's training data cutoff

**Workaround:** Manually verify and update prices in `master.json` before final publication

**Future improvement:** Add direct API integration with Yahoo Finance or Alpha Vantage

### Index Page Updates

**Current behavior:** The `update_index_pages()` function is incomplete

**Manual steps required:**
1. After workflow runs, open `index.html` and `Posts/posts.html`
2. Add a new post card for Week X using the existing card structure
3. Update the card's:
   - Title: "GenAi-Managed Stocks Portfolio Week X"
   - Date: Current evaluation date
   - Link: `Posts/GenAi-Managed-Stocks-Portfolio-Week-X.html`
   - Image: `Media/WX.webp` (you'll need to create this)
4. Commit changes

**Future improvement:** Implement automatic HTML insertion logic

### Error Recovery

**Current behavior:** If any prompt fails, the entire workflow stops

**Manual recovery:**
1. Check which prompt failed in workflow logs
2. Fix the issue (bad JSON, API error, etc.)
3. Re-run the workflow manually
4. The script will overwrite previous attempt

---

## Manual Intervention Points

### Updating Stock Prices Manually

If automated price fetching fails, you can manually update `master.json`:

1. Edit `Data/WX/master.json`
2. Update the `prices` section for each stock with the latest Thursday close
3. Update benchmark history for S&P 500 and Bitcoin
4. Commit and push changes
5. Re-run the workflow

### Customizing Generated Content

After the workflow runs, you can edit the generated HTML:

1. Open `Posts/GenAi-Managed-Stocks-Portfolio-Week-X.html`
2. Make manual edits (fix typos, adjust wording, etc.)
3. Commit changes

---

## Cost Management

**GitHub Actions:**
- **Free tier:** 2,000 minutes/month (private repos)
- **Public repos:** Unlimited minutes
- Each workflow run: ~5 minutes
- **Monthly cost:** $0 (unless exceeding free tier)

**OpenAI API (as of Nov 2025):**
- GPT-4 Turbo: ~$0.01 per 1K input tokens, ~$0.03 per 1K output tokens
- GPT-4: ~$0.03 per 1K input tokens, ~$0.06 per 1K output tokens (higher quality)
- Estimated per run: 15K-20K tokens total (4 prompts)

**Cost per run by model:**
- `gpt-4-turbo-preview` (default): ~$1.00-$2.00
- `gpt-4-turbo`: ~$1.50-$2.50
- `gpt-4`: ~$3.00-$5.00 (highest quality)

**Monthly cost (4-5 runs):**
- GPT-4 Turbo (default): ~$4-$10
- GPT-4: ~$12-$25

**Total monthly cost:** ~$4-$25 depending on model choice

**Cost optimization tips:**
- Use `--model gpt-4-turbo` for best cost/quality balance (default)
- Avoid `gpt-4` unless you need maximum accuracy
- Consider Claude 3.5 Sonnet as an alternative (~30% cheaper)
- Run locally first to catch errors before automated runs

---

## Advanced Configuration

### Using Anthropic Claude Instead

To use Claude instead of GPT-4:

1. Get an Anthropic API key from [console.anthropic.com](https://console.anthropic.com/)
2. Add `ANTHROPIC_API_KEY` to GitHub Secrets
3. Edit `scripts/portfolio_automation.py`:
   ```python
   import anthropic
   
   def call_claude(self, system_prompt, user_message):
       client = anthropic.Anthropic(api_key=self.api_key)
       message = client.messages.create(
           model="claude-3-opus-20240229",
           max_tokens=4096,
           system=system_prompt,
           messages=[{"role": "user", "content": user_message}]
       )
       return message.content[0].text
   ```

### Enabling Email Notifications

Add this step to the workflow after "Create workflow summary":

```yaml
- name: Send email notification
  uses: dawidd6/action-send-mail@v3
  with:
    server_address: smtp.gmail.com
    server_port: 587
    username: ${{ secrets.EMAIL_USERNAME }}
    password: ${{ secrets.EMAIL_PASSWORD }}
    subject: "Portfolio Update Week ${{ env.WEEK_NUMBER }} Generated"
    to: your-email@example.com
    from: GitHub Actions
    body: Check the new post at https://quantuminvestor.net/Posts/GenAi-Managed-Stocks-Portfolio-Week-${{ env.WEEK_NUMBER }}.html
```

---

## Support

If you encounter issues:

1. Check GitHub Actions logs for error details
2. Verify API keys are correctly set
3. Ensure all Prompt files are present
4. Review the generated `master.json` for data consistency
5. Test locally first before relying on automated runs

---

## Best Practices

### Pre-Run Checklist

Before relying on automation, verify:
- [ ] Previous week's `master.json` exists and is valid JSON
- [ ] OpenAI API key is active and has credits
- [ ] All 4 Prompt files are present in `Prompt/` folder (script validates automatically)
- [ ] GitHub Actions is enabled for your repository
- [ ] Previous week's post HTML follows Week 5 structure (for consistency)

**The script now automatically validates:**
- All 4 prompts are loaded on startup
- Generated HTML has required DOCTYPE and structure
- JSON is properly formatted before saving
- File sizes are reasonable (logged in output)

### Post-Run Verification

After each automated run:
- [ ] Review generated HTML for formatting errors
- [ ] Verify stock prices against official market data (Prompt A may use stale data)
- [ ] Check that performance calculations are accurate
- [ ] Ensure chart and table render correctly (look for insertion warnings)
- [ ] Review any validation warnings in workflow logs
- [ ] Check file sizes are reasonable (shown in "Prompt D completed" message)
- [ ] Manually update `index.html` and `posts.html` (until auto-update is implemented)
- [ ] Create hero image `Media/WX.webp` if needed

**What to look for in logs:**
- "✓ Loaded 4 prompt templates" - All prompts found
- "✓ Using model: gpt-4-turbo-preview" - Correct model selected
- File size in bytes at "Prompt D completed" - Should be 50-150KB
- Any "⚠️" warnings - Review and fix if critical

### Data Backup

- Archive folder (`Data/archive/`) automatically stores snapshots
- Git history provides version control
- Consider weekly backups of entire `Data/` folder

---

## Maintenance

**Weekly:**
- Review generated post for accuracy
- Verify prices match market closes (Thursday close)
- Check for any workflow failures
- Update index/posts pages manually

**Monthly:**
- Monitor OpenAI API usage and costs
- Review GitHub Actions minutes (if private repo)
- Audit archived `master.json` files for consistency

**Quarterly:**
- Update Python dependencies: `pip install --upgrade -r scripts/requirements.txt`
- Review and update Prompt files if strategy changes
- Test local run to ensure dependencies are compatible
