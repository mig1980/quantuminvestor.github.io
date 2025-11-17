"""Hero Image Automation (Remote Asset + Overlay)

Retrieves a relevant hero background image from one of the providers (Pexels, Pixabay, Lummi.ai) then overlays
dynamic week metrics. Falls back to generated gradient if all providers fail or no API keys.

Providers (priority order):
  1. Pexels (requires env PEXELS_API_KEY)
  2. Pixabay (requires env PIXABAY_API_KEY)
  3. Lummi.ai (stub – requires env LUMMI_API_KEY, implement endpoint later)

Usage (PowerShell):
  python scripts/hero_image_generator.py --week 6 --master "master data/master.json" --out Media/W6.webp --query "futuristic finance data"

Note: Always use consolidated master data/master.json (single source of truth)

Environment variables:
  $Env:PEXELS_API_KEY
  $Env:PIXABAY_API_KEY
  $Env:LUMMI_API_KEY  (if implementing custom generation)

If no key succeeds, a synthetic gradient background is used.
"""
from __future__ import annotations
import argparse, json, os, math, io, random
from pathlib import Path
from typing import Tuple
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

WIDTH, HEIGHT = 1200, 800
PADDING = 64

def font(size:int):
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
    try: return ImageFont.truetype(face or "Arial", size)
    except: return ImageFont.load_default()

def parse_args():
    ap = argparse.ArgumentParser(description="Fetch remote hero image and overlay metrics")
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--master", type=str, required=True)
    ap.add_argument("--out", type=str, required=True)
    ap.add_argument("--query", type=str, default="futuristic finance technology")
    ap.add_argument("--title", type=str, default=None)
    ap.add_argument("--provider-order", type=str, default="pexels,pixabay,lummi")
    return ap.parse_args()

def load_master(path:Path) -> dict:
    with path.open('r', encoding='utf-8') as f: return json.load(f)

def extract_metrics(master:dict) -> Tuple[str,str,str,str]:
    ph = master.get('portfolio_history', [])
    spx = master.get('benchmarks', {}).get('sp500', {}).get('history', [])
    if not ph or not spx: return ('--','--','--','--')
    lp, ls = ph[-1], spx[-1]
    w = lp.get('weekly_pct'); t = lp.get('total_pct'); spt = ls.get('total_pct')
    week_str = f"{w:.2f}%" if w is not None else "--"
    total_str = f"{t:.2f}%" if t is not None else "--"
    alpha_str = f"{(t - spt):.2f}%" if (t is not None and spt is not None) else "--"
    inception = master.get('meta', {}).get('inception_date'); current = master.get('meta', {}).get('current_date')
    date_range = f"{inception} → {current}" if inception and current else ""
    return week_str, total_str, alpha_str, date_range

def fetch_pexels(query:str):
    key = os.getenv('PEXELS_API_KEY');
    if not key: return None
    url = 'https://api.pexels.com/v1/search'
    params = { 'query': query, 'orientation': 'landscape', 'per_page': 5 }
    resp = requests.get(url, headers={'Authorization': key}, params=params, timeout=10)
    if resp.status_code != 200: return None
    data = resp.json()
    photos = data.get('photos', [])
    for p in photos:
        src = p.get('src', {}).get('large') or p.get('src', {}).get('original')
        if src:
            try:
                img_resp = requests.get(src, timeout=15)
                if img_resp.status_code == 200:
                    return Image.open(io.BytesIO(img_resp.content)).convert('RGBA')
            except: continue
    return None

def fetch_pixabay(query:str):
    key = os.getenv('PIXABAY_API_KEY');
    if not key: return None
    url = 'https://pixabay.com/api/'
    params = { 'key': key, 'q': query, 'image_type': 'photo', 'orientation': 'horizontal', 'per_page': 5, 'safesearch': 'true' }
    resp = requests.get(url, params=params, timeout=10)
    if resp.status_code != 200: return None
    data = resp.json(); hits = data.get('hits', [])
    for h in hits:
        src = h.get('largeImageURL') or h.get('webformatURL')
        if src:
            try:
                img_resp = requests.get(src, timeout=15)
                if img_resp.status_code == 200:
                    return Image.open(io.BytesIO(img_resp.content)).convert('RGBA')
            except: continue
    return None

def fetch_lummi(query:str):
    # Placeholder stub – implement real API call when available
    return None

def fallback_gradient() -> Image.Image:
    base = Image.new('RGBA', (WIDTH, HEIGHT), (10,10,10,255))
    grad = Image.new('L', (WIDTH, HEIGHT))
    cx, cy = WIDTH*0.5, HEIGHT*0.4
    maxd = (WIDTH**2 + HEIGHT**2)**0.5
    pix = grad.load()
    for y in range(HEIGHT):
        for x in range(WIDTH):
            d = ((x-cx)**2 + (y-cy)**2)**0.5
            v = max(0, 255 - int((d/maxd)*255))
            pix[x,y] = v
    grad = grad.filter(ImageFilter.GaussianBlur(200))
    overlay = Image.new('RGBA', (WIDTH, HEIGHT), (72,0,120,255)); overlay.putalpha(grad)
    return Image.alpha_composite(base, overlay)

def darken_for_text(img:Image.Image):
    # Apply top-left vignette darkening to ensure legible overlay
    mask = Image.new('L', (WIDTH, HEIGHT), 0)
    draw = ImageDraw.Draw(mask)
    draw.rectangle([0,0,WIDTH, int(HEIGHT*0.55)], fill=160)
    shadow = Image.new('RGBA', (WIDTH, HEIGHT), (0,0,0,140))
    shadow.putalpha(mask)
    return Image.alpha_composite(img, shadow)

def overlay_text(img:Image.Image, week:int, metrics:Tuple[str,str,str,str], title_override:str|None):
    d = ImageDraw.Draw(img)
    week_str, total_str, alpha_str, date_range = metrics
    badge = f"Week {week}"; badge_font = font(40)
    b_w, b_h = d.textbbox((0,0), badge, font=badge_font)[2:]
    bx_pad, by_pad = 30, 16
    d.rounded_rectangle([PADDING, PADDING, PADDING+b_w+bx_pad*2, PADDING+b_h+by_pad*2], radius=60, fill=(30,27,75,230))
    d.text((PADDING+bx_pad, PADDING+by_pad), badge, font=badge_font, fill=(235,235,255,255))
    title = title_override or f"AI Portfolio Weekly Performance"
    d.text((PADDING, PADDING+b_h+by_pad*2+42), title, font=font(78), fill=(255,255,255,240))
    base_y = PADDING+b_h+by_pad*2+42 + 120
    label_font = font(16); metric_font = font(36)
    def draw_metric(x,label,val,color=(255,255,255,235)):
        d.text((x, base_y), label.upper(), font=label_font, fill=(180,180,200,200))
        d.text((x, base_y+26), val, font=metric_font, fill=color)
    alpha_color = (74,222,128,255) if (not alpha_str.startswith('-') and alpha_str != '--') else (248,113,113,255)
    draw_metric(PADDING, 'Week Change', week_str)
    draw_metric(PADDING+400, 'Since Inception', total_str)
    draw_metric(PADDING+800, 'Alpha vs SPX', alpha_str, alpha_color)
    footer_font = font(26)
    if date_range:
        d.text((PADDING, HEIGHT-PADDING-44), date_range, font=footer_font, fill=(200,200,205,240))
    d.text((WIDTH-PADDING-360, HEIGHT-PADDING-44), 'quantuminvestor.net', font=footer_font, fill=(200,200,215,240))
    return img

def fetch_image(query:str, order:str):
    providers = [p.strip().lower() for p in order.split(',') if p.strip()]
    for p in providers:
        if p == 'pexels':
            img = fetch_pexels(query)
        elif p == 'pixabay':
            img = fetch_pixabay(query)
        elif p == 'lummi':
            img = fetch_lummi(query)
        else:
            img = None
        if img:
            return img
    return None

def main():
    args = parse_args()
    master_path = Path(args.master)
    if not master_path.exists():
        raise SystemExit(f"master.json not found: {master_path}")
    master = load_master(master_path)
    metrics = extract_metrics(master)
    remote = fetch_image(args.query, args.provider_order)
    if remote:
        # Resize & crop to 1200x800 preserving aspect
        remote_ratio = remote.width / remote.height
        target_ratio = WIDTH / HEIGHT
        if remote_ratio > target_ratio:
            # Wider: fit height, crop width
            new_h = HEIGHT
            new_w = int(remote_ratio * new_h)
        else:
            new_w = WIDTH
            new_h = int(new_w / remote_ratio)
        resized = remote.resize((new_w, new_h), Image.Resampling.LANCZOS)
        left = (new_w - WIDTH)//2; top = (new_h - HEIGHT)//2
        img = resized.crop((left, top, left+WIDTH, top+HEIGHT)).convert('RGBA')
        img = darken_for_text(img)
    else:
        img = fallback_gradient()
    img = overlay_text(img, args.week, metrics, args.title)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.convert('RGB').save(out_path, format='WEBP', quality=90)
    source_note = 'remote' if remote else 'fallback-gradient'
    print(f"✓ Hero image generated ({source_note}): {out_path}")

if __name__ == '__main__':
    main()