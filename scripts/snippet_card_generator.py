"""Fallback Snippet Card Generator (Python Pillow)

Generates a social preview card (1200x630 PNG) similar to Playwright template when Node/Playwright unavailable.

Usage:
  python scripts/snippet_card_generator.py --week 6 --master "master data/master.json" --out Media/W6-card.png --title "Week 6 Performance Snapshot"

Note: Always use consolidated master data/master.json (single source of truth)

Design:
 - Radial purple-to-black gradient
 - Badge with Week number
 - Large title
 - Metrics trio (week change, since inception, alpha vs SPX)
 - Date range footer & site label

Dependencies: Pillow (already in requirements)
"""
from __future__ import annotations
import argparse, json, math
from pathlib import Path
from typing import Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter

WIDTH, HEIGHT = 1200, 630
PADDING = 72
FONT_CACHE = {}

def font(size:int, weight:str="regular"):
    key = (size, weight)
    if key in FONT_CACHE:
        return FONT_CACHE[key]
    # Attempt Segoe UI variants else fallback
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
        f = ImageFont.truetype(face or "Arial", size=size)
    except:
        f = ImageFont.load_default()
    FONT_CACHE[key] = f
    return f

def parse_args():
    ap = argparse.ArgumentParser(description="Generate share snippet card")
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--master", type=str, required=True)
    ap.add_argument("--out", type=str, required=True)
    ap.add_argument("--title", type=str, default=None)
    return ap.parse_args()

def load_master(path:Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def extract_metrics(master:dict) -> Tuple[str,str,str,str]:
    ph = master.get("portfolio_history", [])
    spx = master.get("benchmarks", {}).get("sp500", {}).get("history", [])
    if not ph or not spx:
        return ("--","--","--","--")
    lp = ph[-1]
    ls = spx[-1]
    week = lp.get('weekly_pct'); total = lp.get('total_pct'); spx_total = ls.get('total_pct')
    week_str = f"{week:.2f}%" if week is not None else "--"
    total_str = f"{total:.2f}%" if total is not None else "--"
    alpha_str = "--"
    if total is not None and spx_total is not None:
        alpha_str = f"{(total - spx_total):.2f}%"
    inception = master.get('meta', {}).get('inception_date')
    current = master.get('meta', {}).get('current_date')
    date_range = f"{inception} → {current}" if inception and current else ""
    return week_str, total_str, alpha_str, date_range

def radial_gradient() -> Image.Image:
    base = Image.new('RGBA', (WIDTH, HEIGHT), (10,10,10,255))
    grad = Image.new('L', (WIDTH, HEIGHT))
    cx, cy = WIDTH*0.4, HEIGHT*0.35
    maxd = (WIDTH**2 + HEIGHT**2)**0.5
    pix = grad.load()
    for y in range(HEIGHT):
        for x in range(WIDTH):
            d = ((x-cx)**2 + (y-cy)**2)**0.5
            v = max(0, 255 - int((d/maxd)*255))
            pix[x,y] = v
    grad = grad.filter(ImageFilter.GaussianBlur(160))
    overlay = Image.new('RGBA', (WIDTH, HEIGHT), (58,0,104,255))
    overlay.putalpha(grad)
    return Image.alpha_composite(base, overlay)

def draw_content(img:Image.Image, week:int, metrics:Tuple[str,str,str,str], title_override:str|None):
    d = ImageDraw.Draw(img)
    week_str, total_str, alpha_str, date_range = metrics
    # Badge
    badge_text = f"Week {week}"; badge_font = font(36)
    bw, bh = d.textbbox((0,0), badge_text, font=badge_font)[2:]
    padx, pady = 28, 14
    d.rounded_rectangle([PADDING, PADDING, PADDING + bw + padx*2, PADDING + bh + pady*2], radius=50, fill=(30,27,75,255))
    d.text((PADDING+padx, PADDING+pady), badge_text, font=badge_font, fill=(230,230,255,255))
    # Title
    title = title_override or f"AI Portfolio Weekly Performance"
    d.text((PADDING, PADDING+bh+pady*2+34), title, font=font(74), fill=(255,255,255,240))
    block_y = PADDING+bh+pady*2+34 + 110
    metric_font = font(34)
    label_font = font(14)
    gap = 40
    def draw_metric(x,label,value,color=(255,255,255,230)):
        d.text((x, block_y), label.upper(), font=label_font, fill=(180,180,200,200))
        d.text((x, block_y+22), value, font=metric_font, fill=color)
    alpha_color = (74,222,128,255) if (not alpha_str.startswith('-') and alpha_str != '--') else (248,113,113,255)
    draw_metric(PADDING, 'Week Change', week_str)
    draw_metric(PADDING+420, 'Since Inception', total_str)
    draw_metric(PADDING+840, 'Alpha vs SPX', alpha_str, alpha_color)
    # Footer
    footer_font = font(26)
    if date_range:
        d.text((PADDING, HEIGHT-PADDING-40), date_range, font=footer_font, fill=(190,190,190,230))
    d.text((WIDTH-PADDING-330, HEIGHT-PADDING-40), 'quantuminvestor.net', font=footer_font, fill=(190,190,210,230))
    return img

def main():
    args = parse_args()
    master_path = Path(args.master)
    if not master_path.exists():
        raise SystemExit(f"master.json not found: {master_path}")
    master = load_master(master_path)
    metrics = extract_metrics(master)
    img = radial_gradient()
    img = draw_content(img, args.week, metrics, args.title)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.convert('RGB').save(out, format='PNG')
    print(f"✓ Snippet card generated (fallback): {out}")

if __name__ == '__main__':
    main()