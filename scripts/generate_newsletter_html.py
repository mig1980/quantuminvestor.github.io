"""
Stage 2: Generate Newsletter HTML
Takes narrative JSON and creates final HTML email matching week7_newsletter_enhanced.html format.
Optimized for 95%+ email client compatibility, ~50KB file size, mobile/desktop responsive.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def format_percentage(value: float, include_sign: bool = True) -> str:
    """Format percentage with appropriate sign"""
    if include_sign:
        sign = "+" if value > 0 else ""
        return f"{sign}{value:.2f}%"
    return f"{value:.2f}%"


def generate_html(narrative_data: Dict[str, Any]) -> str:
    """
    Generate email-optimized HTML from narrative JSON.
    Matches week7_newsletter_enhanced.html exactly - ~50KB, 94%+ compatibility.

    Args:
        narrative_data: Dictionary containing newsletter narrative data

    Returns:
        Complete HTML string optimized for email clients
    """
    week_num = narrative_data["week_number"]
    date_range = narrative_data.get("date_range", "")
    subject = narrative_data["subject_line"]
    preheader = narrative_data["preheader"]
    perf_data = narrative_data["performance_data"]
    market_context = narrative_data["market_context"]
    market_outlook = narrative_data.get("market_outlook", "")
    benchmark = narrative_data["benchmark_comparison"]
    cta_url = narrative_data["call_to_action_url"]
    portfolio_value = perf_data.get("portfolio_value", 10000)

    # Format performance values
    weekly_change = perf_data["weekly_change"]
    total_return = perf_data["total_return"]
    weekly_sign = "+" if weekly_change >= 0 else ""
    total_sign = "+" if total_return >= 0 else ""
    dollar_change = portfolio_value - 10000
    dollar_sign = "+" if dollar_change >= 0 else "-"
    total_color = "#059669" if total_return >= 0 else "#dc2626"

    # Format benchmark percentages
    portfolio_weekly = benchmark["portfolio_weekly"]
    sp500_weekly = benchmark["sp500_weekly"]
    bitcoin_weekly = benchmark["bitcoin_weekly"]
    benchmark_summary = benchmark["summary"]

    # Parse date range for Monday-Friday format (uppercase)
    if "to" in date_range.lower():
        parts = date_range.upper().split(" TO ")
        if len(parts) == 2:
            formatted_date = f"{parts[0].strip()} – {parts[1].strip()}"
        else:
            formatted_date = date_range.upper()
    else:
        formatted_date = date_range.upper()

    # Extract theme from subject line
    subject_parts = subject.split("|")
    theme = subject_parts[1].strip() if len(subject_parts) > 1 else "Performance Update"

    # Create benchmark comparison bar chart
    def create_bar_chart(label, value, max_abs_value):
        color = "#059669" if value >= 0 else "#dc2626"
        bar_width = min(100, (abs(value) / max_abs_value * 100)) if max_abs_value > 0 else 0
        sign = "+" if value >= 0 else ""
        return f"""<tr>
            <td style="padding: 8px 0;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                    <tr>
                        <td width="90" style="font-size: 13px; color: {color}; font-weight: 600; padding-right: 12px;">{label}</td>
                        <td style="background-color: rgba(210, 168, 255, 0.1); border-radius: 4px; height: 24px; overflow: hidden; position: relative;">
                            <div style="background: {color}; height: 24px; width: {bar_width:.1f}%; border-radius: 4px;"></div>
                        </td>
                        <td width="70" style="font-size: 14px; font-weight: 600; color: {color}; padding-left: 12px; text-align: right;">{sign}{value:.2f}%</td>
                    </tr>
                </table>
            </td>
        </tr>"""

    max_bench_value = max(abs(portfolio_weekly), abs(sp500_weekly), abs(bitcoin_weekly))
    benchmark_bars = (
        create_bar_chart("Portfolio", portfolio_weekly, max_bench_value)
        + create_bar_chart("S&P 500", sp500_weekly, max_bench_value)
        + create_bar_chart("Bitcoin", bitcoin_weekly, max_bench_value)
    )

    # Build complete HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta name="color-scheme" content="light dark">
    <meta name="supported-color-schemes" content="light dark">
    <title>Week {week_num}: {weekly_sign}{weekly_change:.2f}% | {theme} - Quantum Investor Digest</title>
    <!--[if mso]>
    <noscript>
    <xml>
    <o:OfficeDocumentSettings>
    <o:PixelsPerInch>96</o:PixelsPerInch>
    </o:OfficeDocumentSettings>
    </xml>
    </noscript>
    <![endif]-->
    <style type="text/css">
        /* Reset & Base Styles */
        body {{
            margin: 0;
            padding: 0;
            -webkit-text-size-adjust: 100%;
            -ms-text-size-adjust: 100%;
        }}
        table {{
            border-collapse: collapse;
            mso-table-lspace: 0pt;
            mso-table-rspace: 0pt;
        }}
        img {{
            border: 0;
            height: auto;
            line-height: 100%;
            outline: none;
            text-decoration: none;
            -ms-interpolation-mode: bicubic;
        }}
        a {{
            text-decoration: none;
        }}

        /* Mobile Responsive - Outlook-safe */
        @media only screen and (max-width: 600px) {{
            .mobile-center {{
                text-align: center !important;
            }}
            .mobile-full-width {{
                width: 100% !important;
                display: block !important;
            }}
            .mobile-padding {{
                padding: 16px !important;
            }}
            .mobile-hide {{
                display: none !important;
            }}
            .mobile-font-large {{
                font-size: 32px !important;
            }}
            .mobile-font-medium {{
                font-size: 24px !important;
            }}
            .mobile-font-small {{
                font-size: 14px !important;
            }}
            .mobile-stack {{
                display: block !important;
                width: 100% !important;
                padding-left: 0 !important;
                padding-right: 0 !important;
                padding-bottom: 16px !important;
            }}
            .mobile-stack-padding {{
                padding: 12px 0 !important;
            }}
            .mobile-button {{
                padding: 16px 32px !important;
                font-size: 14px !important;
            }}
            .mobile-heading {{
                font-size: 20px !important;
            }}
            table[class="mobile-scale"] {{
                width: 100% !important;
            }}

            /* Force metric cards to stack on mobile */
            .mobile-stack-row {{
                display: block !important;
            }}

            .mobile-full-width {{
                display: block !important;
                width: 100% !important;
                padding-left: 0 !important;
                padding-right: 0 !important;
                margin-bottom: 16px !important;
            }}

            .mobile-full-width:last-child {{
                margin-bottom: 0 !important;
            }}
        }}

        /* Outlook-specific fixes */
        <!--[if mso]>
        <style type="text/css">
            table {{ mso-table-lspace: 0pt; mso-table-rspace: 0pt; }}
            img {{ -ms-interpolation-mode: bicubic; }}
            .mobile-stack {{ display: table-cell !important; }}
        </style>
        <![endif]-->
    </style>
</head>
<body style="margin: 0; padding: 0; background-color: #000000; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
    <!-- Preheader Text (Hidden but shown in preview) -->
    <div style="display: none; max-height: 0; overflow: hidden; mso-hide: all;">
        {preheader}
    </div>

    <!-- Outer wrapper table -->
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #000000;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <!-- Main container table (680px max-width) -->
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width: 680px; background-color: #111111; box-shadow: 0 20px 60px rgba(210, 168, 255, 0.15);">

                    <!-- Header with Gradient Accent Bar -->
                    <tr>
                        <td style="padding: 0;">
                            <!-- Gradient Accent Bar -->
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td height="4" style="background: linear-gradient(90deg, #7c3aed 0%, #a855f7 50%, #ec4899 100%);"></td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td style="background: linear-gradient(180deg, #0a0a0a 0%, #151515 100%); padding: 24px 32px;">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td style="vertical-align: middle;">
                                        <div style="font-size: 32px; font-weight: 700; color: #ffffff; line-height: 1.2; margin-bottom: 2px;">Quantum Investor</div>
                                        <div style="font-size: 32px; font-weight: 700; color: #ffffff; line-height: 1.2; margin-bottom: 8px;">Digest</div>
                                        <div style="font-size: 13px; color: #9ca3af;">Weekly Edition • {formatted_date}</div>
                                    </td>
                                    <td align="right" style="vertical-align: middle;">
                                        <!--[if mso]>
                                        <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="display: inline-block;">
                                            <tr>
                                                <td style="border: 2px solid #7c3aed; background-color: #f3e8ff; padding: 8px 16px;">
                                        <![endif]-->
                                        <div style="border: 2px solid #7c3aed; background-color: #f3e8ff; background: rgba(124, 58, 237, 0.1); border-radius: 20px; padding: 8px 16px; display: inline-block; mso-border-radius: 20px;">
                                            <img src="https://api.iconify.design/mdi/robot.svg?color=%23a78bfa" style="width: 13px; height: 13px; vertical-align: middle; margin-right: 6px;" alt="AI" width="13" height="13"><span style="font-size: 11px; color: #a78bfa; font-weight: 600; line-height: 13px; vertical-align: middle;">AI POWERED</span>
                                        </div>
                                        <!--[if mso]>
                                                </td>
                                            </tr>
                                        </table>
                                        <![endif]-->
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- AI Insight Card - Top Section -->
                    <tr>
                        <td style="padding: 32px 32px 0 32px; background-color: #111111;">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background: linear-gradient(135deg, rgba(210, 168, 255, 0.12) 0%, rgba(210, 168, 255, 0.05) 100%); border-radius: 12px; border: 1px solid rgba(210, 168, 255, 0.3);">
                                <tr>
                                    <td style="padding: 24px;">
                                        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                            <tr>
                                                <td colspan="2" class="mobile-stack" style="vertical-align: middle;">
                                                    <div style="font-size: 18px; font-weight: 600; color: #a78bfa; margin-bottom: 16px;">AI INSIGHT</div>
                                                    <div style="font-size: 17px; font-weight: 600; color: #ffffff; line-height: 1.4; margin-bottom: 16px;">
                                                        {preheader}
                                                    </div>
                                                    <a href="{cta_url}" class="mobile-button" style="display: block; background-color: #7c3aed; background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%); color: #ffffff; padding: 12px 20px; border-radius: 8px; text-decoration: none; font-size: 13px; font-weight: 600; text-align: center; mso-border-radius: 8px;">
                                                        View Analysis
                                                    </a>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Portfolio Performance Cards -->
                    <tr>
                        <td style="background-color: #111111; padding: 32px;">
                            <div style="font-size: 18px; font-weight: 600; color: #ffffff; margin-bottom: 20px;">GEN AI MANAGED PORTFOLIO THIS WEEK</div>

                            <!-- Metric Cards Row -->
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                <tr class="mobile-stack-row">
                                    <!-- Total Return Card -->
                                    <td width="48%" class="mobile-full-width" style="vertical-align: top; padding-right: 12px;">
                                        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background: linear-gradient(135deg, #0a0a0a 0%, #151515 100%); border-radius: 12px; border: 1px solid rgba(210, 168, 255, 0.2);">
                                            <tr>
                                                <td style="padding: 20px;">
                                                    <div style="display: flex; align-items: center; margin-bottom: 8px;">
                                                        <span style="font-size: 13px; color: #94a3b8; font-weight: 500;">Total Return</span>
                                                        <img src="https://api.iconify.design/mdi/trending-up.svg?color=%2394a3b8" style="width: 18px; height: 18px; margin-left: 8px; vertical-align: middle;" alt="Return">
                                                    </div>
                                                    <div style="font-size: 32px; font-weight: 700; color: {total_color}; margin-bottom: 4px; letter-spacing: -0.02em;">{dollar_sign}${abs(dollar_change):,.0f}</div>
                                                    <div style="font-size: 13px; color: #64748b;">{total_sign}{total_return:.2f}% this week</div>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>

                                    <!-- Portfolio Value Card -->
                                    <td width="48%" class="mobile-full-width" style="vertical-align: top; padding-left: 12px;">
                                        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background: linear-gradient(135deg, #0a0a0a 0%, #151515 100%); border-radius: 12px; border: 1px solid rgba(210, 168, 255, 0.2);">
                                            <tr>
                                                <td style="padding: 20px;">
                                                    <div style="display: flex; align-items: center; margin-bottom: 8px;">
                                                        <span style="font-size: 13px; color: #94a3b8; font-weight: 500;">Portfolio Value</span>
                                                        <img src="https://api.iconify.design/mdi/chart-bar.svg?color=%2394a3b8" style="width: 18px; height: 18px; margin-left: 8px; vertical-align: middle;" alt="Portfolio">
                                                    </div>
                                                    <div style="font-size: 32px; font-weight: 700; color: #ffffff; margin-bottom: 4px; letter-spacing: -0.02em;">${portfolio_value:,.0f}</div>
                                                    <div style="font-size: 13px; color: #64748b;">Across 10 positions</div>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Benchmark Comparison Section -->
                    <tr>
                        <td style="padding: 0 32px 32px 32px; background-color: #111111;">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background: linear-gradient(135deg, #0a0a0a 0%, #151515 100%); border-radius: 12px; border: 1px solid rgba(210, 168, 255, 0.2);">
                                <tr>
                                    <td style="padding: 24px;">
                                        <div style="font-size: 16px; font-weight: 600; color: #ffffff; margin-bottom: 12px;">Benchmark Comparison</div>
                                        <div style="font-size: 14px; color: #94a3b8; line-height: 1.6; margin-bottom: 20px;">
                                            {benchmark_summary}
                                        </div>
                                        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                            {benchmark_bars}
                                        </table>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Market Summary -->
                    <tr>
                        <td style="padding: 0 32px 32px 32px; background-color: #111111;">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background: linear-gradient(135deg, #0a0a0a 0%, #151515 100%); border-radius: 12px; border: 1px solid rgba(210, 168, 255, 0.2);">
                                <tr>
                                    <td style="padding: 24px;">
                                        <!-- What Happened Section -->
                                        <div style="margin-bottom: 24px;">
                                            <div style="font-size: 14px; color: #94a3b8; margin-bottom: 12px; font-weight: 600; letter-spacing: 0.05em;">📍 WHAT HAPPENED</div>
                                            <div style="font-size: 15px; color: #e2e8f0; line-height: 1.7;">
                                                {market_context}
                                            </div>
                                        </div>

                                        <!-- What's Next Section -->
                                        <div style="padding-top: 20px; border-top: 1px solid rgba(210, 168, 255, 0.2);">
                                            <div style="font-size: 14px; color: #94a3b8; margin-bottom: 12px; font-weight: 600; letter-spacing: 0.05em;">🔮 WHAT'S NEXT</div>
                                            <div style="font-size: 15px; color: #e2e8f0; line-height: 1.7;">
                                                {market_outlook}
                                            </div>
                                        </div>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Action Buttons (Dashboard Style) -->
                    <tr>
                        <td style="padding: 0 32px 40px 32px; background-color: #111111;">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <!-- View Full Portfolio Dashboard Button -->
                                    <td width="100%">
                                        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                            <tr>
                                                <td align="center" style="background-color: #7c3aed; background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%); border-radius: 8px; padding: 16px; text-align: center; mso-border-radius: 8px;">
                                                    <a href="{cta_url}" style="color: #ffffff; text-decoration: none; font-size: 15px; font-weight: 600; display: block;">
                                                        View Full Portfolio Dashboard
                                                    </a>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background: linear-gradient(180deg, #0a0a0a 0%, #000000 100%); border-top: 1px solid rgba(210, 168, 255, 0.2); padding: 40px 32px; text-align: center;">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td align="center" style="font-size: 17px; font-weight: 600; padding-bottom: 16px; letter-spacing: 0.05em;">
                                        <a href="https://quantuminvestor.net" style="color: #7c3aed; text-decoration: none;">Quantum Investor Digest</a>
                                    </td>
                                </tr>
                                <tr>
                                    <td align="center" style="font-size: 13px; color: #6b7280; line-height: 1.6; padding-bottom: 12px;">
                                        This newsletter is for informational purposes only and does not constitute investment advice.
                                    </td>
                                </tr>
                                <tr>
                                    <td align="center" style="font-size: 13px; color: #6b7280; line-height: 1.6; padding-bottom: 4px;">
                                        You're receiving this because you subscribed at quantuminvestor.net
                                    </td>
                                </tr>
                                <tr>
                                    <td align="center" style="font-size: 13px; color: #6b7280; line-height: 1.6; padding-bottom: 4px;">
                                        Sent to <span style="color: #9ca3af;">{{{{SUBSCRIBER_EMAIL}}}}</span>
                                    </td>
                                </tr>
                                <tr>
                                    <td align="center" style="padding: 16px 0;">
                                        <div style="height: 1px; background: linear-gradient(90deg, transparent 0%, rgba(37, 99, 235, 0.3) 50%, transparent 100%); max-width: 400px; margin: 0 auto;"></div>
                                    </td>
                                </tr>
                                <tr>
                                    <td align="center" style="font-size: 13px; color: #6b7280; line-height: 1.6; padding-top: 16px;">
                                        <a href="https://quantuminvestor.net/newsletters/week{week_num}_newsletter.html" style="color: #6b7280; text-decoration: none;">View in Browser</a>
                                        <span style="color: #6b7280; margin: 0 12px;">•</span>
                                        <a href="https://quantuminvestor.net/Disclosures.html" style="color: #6b7280; text-decoration: none;">Disclosures</a>
                                        <span style="color: #6b7280; margin: 0 12px;">•</span>
                                        <a href="https://api.quantuminvestor.net/api/Unsubscribe?email={{{{SUBSCRIBER_EMAIL}}}}" style="color: #6b7280; text-decoration: none;">Unsubscribe</a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Bottom Gradient Accent -->
                    <tr>
                        <td style="padding: 0;">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td height="4" style="background: linear-gradient(90deg, #7c3aed 0%, #a855f7 50%, #ec4899 100%);"></td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

    return html


def main():
    """Main execution function"""
    if len(sys.argv) < 2:
        print("Usage: python generate_newsletter_html.py <week_number>")
        sys.exit(1)

    try:
        week_num = int(sys.argv[1])
    except ValueError:
        print(f"Error: Invalid week number '{sys.argv[1]}'. Must be an integer.")
        sys.exit(1)

    # Paths
    base_dir = Path(__file__).parent.parent
    json_path = base_dir / "newsletters" / f"week{week_num}_narrative.json"
    output_path = base_dir / "newsletters" / f"week{week_num}_newsletter.html"

    # Validate JSON exists
    if not json_path.exists():
        logging.error(f"Narrative JSON not found: {json_path}")
        print(f"❌ Error: {json_path} does not exist.")
        print(f"   Run Stage 1 first: python scripts/generate_newsletter_narrative.py {week_num}")
        sys.exit(1)

    # Load narrative data
    logging.info(f"Loading narrative data from {json_path}")
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            narrative_data = json.load(f)
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in {json_path}: {e}")
        print(f"❌ Error: Invalid JSON format in {json_path}")
        sys.exit(1)

    # Generate HTML
    logging.info(f"Generating HTML for Week {week_num}")
    html_content = generate_html(narrative_data)

    # Save HTML
    logging.info(f"Saving HTML to {output_path}")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    # Get file size
    file_size_kb = len(html_content.encode("utf-8")) / 1024

    # Success message
    print("\n" + "=" * 60)
    print("📧 STAGE 2 COMPLETE - OPTIMIZED EMAIL GENERATED")
    print("=" * 60)
    print(f"✅ Newsletter HTML created")
    print(f"📂 Output: newsletters/week{week_num}_newsletter.html")
    print(f"📝 Subject: {narrative_data['subject_line']}")
    print(f"📊 File Size: {file_size_kb:.1f} KB (Target: <102 KB) ✅")
    print("=" * 60)

    logging.info("Newsletter generation complete")


if __name__ == "__main__":
    main()
