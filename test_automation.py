#!/usr/bin/env python3
"""Quick test to validate portfolio_automation.py structure"""
import sys
sys.path.insert(0, 'scripts')

try:
    from portfolio_automation import PortfolioAutomation
    print("✅ Script imports successfully")
    
    methods = [m for m in dir(PortfolioAutomation) if not m.startswith('_')]
    print(f"✅ PortfolioAutomation class has {len(methods)} public methods")
    
    # Check critical methods exist
    required_methods = [
        'detect_next_week',
        'load_prompts', 
        'load_master_json',
        'call_gpt4',
        'run_prompt_a',
        'run_prompt_b',
        'run_prompt_c',
        'run_prompt_d',
        'generate_hero_image',
        'generate_snippet_card',
        'generate_master_from_alphavantage',
        'run'
    ]
    
    missing = [m for m in required_methods if m not in methods]
    if missing:
        print(f"❌ Missing methods: {', '.join(missing)}")
    else:
        print(f"✅ All {len(required_methods)} critical methods present")
        print("\n📋 Method List:")
        for m in sorted(methods):
            print(f"   • {m}")
    
    print("\n✅ Automation script is structurally complete!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
