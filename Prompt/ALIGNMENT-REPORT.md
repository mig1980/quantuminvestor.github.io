# Prompt B / Automation / Prompt D Alignment Report

**Date**: 2025-11-28  
**Status**: ✅ ALIGNED with modifications needed

---

## Summary

The updated Prompt B (v5.5B) with flexible portfolio construction is **compatible** with the existing automation pipeline and Prompt D, but requires **minor updates** to both to handle:

1. **Variable position count** (6–12 stocks, not fixed at 10)
2. **Variable position weights** (8–20%, not equal-weight 10%)
3. **New conditional sections** (Market Opportunities vs Rebalance Execution)
4. **Prompt-MarketResearch integration** (research_candidates.json input)

---

## Current State Analysis

### ✅ What Already Works

#### 1. **Core HTML Structure** (Fully Compatible)
- Prompt B outputs `<div class="prose prose-invert max-w-none">...</div>`
- Prompt D wraps it in `<main><article>` container
- Automation adds `<head>`, meta tags, CSS, scripts
- **No changes needed**

#### 2. **Visual Embedding** (Fully Compatible)
- Table: Uses `<!-- PERFORMANCE TABLE WILL BE INSERTED HERE BY AUTOMATION -->` placeholder
- Chart: Uses `<!-- CHART WILL BE INSERTED HERE BY AUTOMATION -->` placeholder
- Automation finds placeholders with regex and injects HTML/SVG
- **No changes needed**

#### 3. **Holdings List Detection** (Fully Compatible)
- Automation finds `</ul>` tag and injects heatmap button
- Regex pattern: `r"(</ul>)(\s*)(<p[^>]*>)"`
- Works regardless of list length (6–12 items)
- **No changes needed**

#### 4. **CSS Styling** (Fully Compatible)
- All table/chart styles in `_apply_standard_head()`
- Prompt B/D don't add inline styles
- **No changes needed**

---

### ⚠️ Required Updates

#### 1. **Prompt B Updated Inputs** (REQUIRED)
**Current automation `run_prompt_b()`**:
```python
user_message = f"""
{self.prompts['B']}
Here is the summary data for Week {self.week_number}:
{data_json}
PERFORMANCE TABLE (HTML - use as-is):
{table_html}
PERFORMANCE CHART (SVG - use as-is):
{chart_svg}
"""
```

**Needs to add**:
```python
# NEW: Load research_candidates.json (from Prompt-MarketResearch)
research_candidates = {}
research_path = DATA_DIR / f"W{self.week_number}" / "research_candidates.json"
if research_path.exists():
    with open(research_path, "r", encoding="utf-8") as f:
        research_candidates = json.load(f)

user_message = f"""
{self.prompts['B']}
Here is the summary data for Week {self.week_number}:
{data_json}

RESEARCH CANDIDATES (from Prompt-MarketResearch):
{json.dumps(research_candidates, indent=2)}

PERFORMANCE TABLE (HTML - use as-is):
{table_html}
PERFORMANCE CHART (SVG - use as-is):
{chart_svg}
"""
```

**Action**: Add research_candidates.json loading to `run_prompt_b()` method

---

#### 2. **Holdings List Format Update** (OPTIONAL BUT RECOMMENDED)
**Current Prompt B v5.4B format**:
```html
<ul class="list-disc list-inside space-y-1 text-gray-300 mb-6">
    <li>Palantir Technologies (PLTR)</li>
    <li>Newmont Corp. (NEM)</li>
</ul>
```

**New Prompt B v5.5B format** (enhanced with position sizes):
```html
<ul class="list-disc list-inside space-y-1 text-gray-300 mb-6">
    <li>Palantir Technologies (PLTR) - $1,680 (16.3%)</li>
    <li>Newmont Corp. (NEM) - $1,420 (13.8%)</li>
</ul>
```

**Automation Impact**:
- Heatmap button injection still works (finds `</ul>` tag)
- No code changes needed
- **Optional**: Enhanced format provides more transparency

**Action**: Accept enhanced format (no automation changes needed)

---

#### 3. **Conditional Section Handling** (DOCUMENTATION ONLY)
**New Prompt B sections**:
- **HOLD weeks**: Adds "Market Opportunities Under Review" section
- **REBALANCE weeks**: Adds "Rebalance Execution Details" section

**Automation Impact**:
- Prompt D already handles `narrative.html` as-is (no parsing)
- Automation wraps entire narrative in standard structure
- No code changes needed
- **Recommended**: Update Prompt D documentation to mention flexible sections

**Action**: Update Prompt D comments to note conditional sections allowed

---

#### 4. **Decision Summary JSON** (NEW OUTPUT)
**Current Prompt B outputs**:
- `narrative.html`
- `seo.json`

**New Prompt B v5.5B adds**:
- `decision_summary.json` (for automation tracking)

**Example**:
```json
{
  "week": 7,
  "decision": "HOLD",
  "position_count": 9,
  "triggers_activated": [],
  "trades_executed": [],
  "portfolio_value": "$10,280",
  "sp500_alpha_bps": 187
}
```

**Automation Impact**:
- Not currently used by automation
- Useful for future analytics/reporting
- **Optional**: Save to `Data/W{n}/decision_summary.json`

**Action**: Add optional `decision_summary.json` extraction in `run_prompt_b()` (non-critical)

---

## Implementation Checklist

### Automation Script (`portfolio_automation.py`)

**Priority 1 (Required)**:
- [ ] Add `research_candidates.json` loading to `run_prompt_b()` method
  - Path: `DATA_DIR / f"W{self.week_number}" / "research_candidates.json"`
  - Handle missing file gracefully (empty dict if not exists)
  - Include in user_message to Prompt B

**Priority 2 (Recommended)**:
- [ ] Extract and save `decision_summary.json` from Prompt B response
  - Parse JSON block with pattern: `r'```json\s*({.*?})\s*```'` (second match)
  - Save to: `DATA_DIR / f"W{self.week_number}" / "decision_summary.json"`
  - Non-critical - log warning if not found

**Priority 3 (Optional)**:
- [ ] Add logging for position count changes
  - Extract `position_count` from `decision_summary.json`
  - Log: "Portfolio now holds {N} positions (was {M})"

### Prompt B (`Prompt-B-v5.4B.md`)

**Already Updated**:
- ✅ Flexible position count (6–12 stocks)
- ✅ Variable position weights (8–20%)
- ✅ Conditional sections (Market Opportunities vs Rebalance Execution)
- ✅ Integration with Prompt-MarketResearch (`research_candidates.json`)
- ✅ Enhanced holdings list format with position sizes

**No Changes Needed**

### Prompt D (`Prompt-D-v5.4D.md`)

**Priority 1 (Documentation)**:
- [ ] Update comments to note narrative may include conditional sections
  - "Market Opportunities Under Review" (HOLD weeks)
  - "Rebalance Execution Details" (REBALANCE weeks)
- [ ] Clarify that holdings list is variable length (6–12 items)

**No Code Changes Needed** - Prompt D already handles `narrative.html` as opaque block

---

## Validation Tests

Before deploying updated framework, test:

### Test 1: HOLD Week with 10 Positions
- [ ] Portfolio has 10 positions at various weights (not equal)
- [ ] Narrative includes "Market Opportunities" section
- [ ] Holdings list shows position sizes and percentages
- [ ] Heatmap button appears after holdings list
- [ ] Table and chart embed correctly

### Test 2: REBALANCE Week with 9 Positions (Consolidation)
- [ ] Portfolio reduced from 10 to 9 positions
- [ ] Narrative includes "Rebalance Execution" section
- [ ] Holdings list shows 9 stocks with new weights
- [ ] Heatmap button appears after holdings list
- [ ] Table and chart embed correctly

### Test 3: REBALANCE Week with 7 Positions (Heavy Consolidation)
- [ ] Portfolio reduced to 7 high-conviction positions
- [ ] Some positions at 15–18% weight (concentrated)
- [ ] Narrative explains consolidation rationale
- [ ] All visual components render correctly

---

## Risk Assessment

### Low Risk Changes
✅ Enhanced holdings list format (backward compatible)  
✅ Conditional narrative sections (Prompt D agnostic)  
✅ Decision summary JSON (optional output)

### Medium Risk Changes
⚠️ Prompt-MarketResearch integration (requires new workflow step)  
⚠️ Variable position count (needs validation in edge cases)

### High Risk Changes
🔴 None identified

---

## Rollback Plan

If issues arise:

1. **Prompt B**: Revert to v5.4B (fixed 10 stocks, equal-weight)
2. **Automation**: Remove `research_candidates.json` loading (line 1-2 changes)
3. **Prompt D**: No changes needed (already compatible)

Estimated rollback time: **5 minutes**

---

## Next Steps

1. **Implement Priority 1 changes** (automation script)
2. **Create Prompt-MarketResearch** (market intelligence agent)
3. **Test with Week 8 data** (use actual portfolio)
4. **Monitor first 2-3 weeks** for edge cases
5. **Document Prompt-MarketResearch workflow** in automation script

---

## Conclusion

✅ **Alignment Status**: Compatible with minor updates  
✅ **Risk Level**: Low to Medium  
✅ **Rollback Complexity**: Simple (revert 1-2 files)  
✅ **Recommended Action**: Proceed with phased implementation

The flexible portfolio framework (Prompt B v5.5B) is **production-ready** once Priority 1 automation updates are complete. The architecture maintains backward compatibility while enabling professional portfolio management with dynamic position sizing and systematic rebalancing logic.
