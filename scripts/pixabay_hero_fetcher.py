"""Pixabay Hero Image Fetcher

Dedicated script to fetch hero images from Pixabay API for weekly blog posts.
Searches Pixabay based on custom attributes/descriptions and downloads high-quality images.

API Documentation: https://pixabay.com/api/docs/

Usage (PowerShell):
  python scripts/pixabay_hero_fetcher.py --query "futuristic finance technology" --out Media/W6_hero.jpg
  python scripts/pixabay_hero_fetcher.py --week 6 --category "finance" --colors "blue,green" --out Media/W6_hero.jpg

Environment variables:
  $Env:PIXABAY_API_KEY (required)

Features:
  - Search by keyword query
  - Filter by category, colors, image type
  - Control image size and orientation
  - Safe search enabled by default
  - Automatic retry with fallback queries
"""
from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path
from typing import Optional, List
import requests
from PIL import Image
import io


# Pixabay API Configuration
PIXABAY_API_BASE = "https://pixabay.com/api/"

# Image download settings
DEFAULT_WIDTH = 1200
DEFAULT_HEIGHT = 800
TIMEOUT_SECONDS = 15

# Available Pixabay categories
CATEGORIES = [
    "backgrounds", "fashion", "nature", "science", "education", 
    "feelings", "health", "people", "religion", "places", 
    "animals", "industry", "computer", "food", "sports", 
    "transportation", "travel", "buildings", "business", "music"
]

# Available color filters
COLORS = [
    "grayscale", "transparent", "red", "orange", "yellow", 
    "green", "turquoise", "blue", "lilac", "pink", 
    "white", "gray", "black", "brown"
]


def parse_args():
    """Parse command-line arguments."""
    ap = argparse.ArgumentParser(
        description="Fetch hero images from Pixabay API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic search
  python pixabay_hero_fetcher.py --query "stock market data" --out hero.jpg
  
  # Advanced search with filters
  python pixabay_hero_fetcher.py --query "finance technology" \\
    --category computer --colors blue,green --min-width 1920 --out hero.jpg
  
  # Weekly post image with custom dimensions
  python pixabay_hero_fetcher.py --week 6 --query "AI trading" \\
    --width 1200 --height 800 --out Media/W6_hero.webp
        """
    )
    
    # Required arguments
    ap.add_argument(
        "--query", 
        type=str, 
        required=True,
        help="Search query keywords (e.g., 'finance technology', 'stock market')"
    )
    ap.add_argument(
        "--out", 
        type=str, 
        required=True,
        help="Output file path (supports .jpg, .png, .webp)"
    )
    
    # Optional filters
    ap.add_argument(
        "--week", 
        type=int,
        help="Week number (for naming/metadata only)"
    )
    ap.add_argument(
        "--category", 
        type=str, 
        choices=CATEGORIES,
        help=f"Image category filter. Options: {', '.join(CATEGORIES)}"
    )
    ap.add_argument(
        "--colors", 
        type=str,
        help=f"Comma-separated color filters. Options: {', '.join(COLORS)}"
    )
    ap.add_argument(
        "--image-type", 
        type=str, 
        default="photo",
        choices=["all", "photo", "illustration", "vector"],
        help="Type of images to search (default: photo)"
    )
    ap.add_argument(
        "--orientation", 
        type=str, 
        default="horizontal",
        choices=["all", "horizontal", "vertical"],
        help="Image orientation (default: horizontal)"
    )
    ap.add_argument(
        "--min-width", 
        type=int, 
        default=1200,
        help="Minimum image width in pixels (default: 1200)"
    )
    ap.add_argument(
        "--min-height", 
        type=int, 
        default=800,
        help="Minimum image height in pixels (default: 800)"
    )
    ap.add_argument(
        "--per-page", 
        type=int, 
        default=10,
        help="Number of results to fetch (default: 10, max: 200)"
    )
    ap.add_argument(
        "--safesearch", 
        action="store_true", 
        default=True,
        help="Enable safe search (default: True)"
    )
    ap.add_argument(
        "--width", 
        type=int,
        default=DEFAULT_WIDTH,
        help="Output image width in pixels (default: 1200)"
    )
    ap.add_argument(
        "--height", 
        type=int,
        default=DEFAULT_HEIGHT,
        help="Output image height in pixels (default: 800)"
    )
    ap.add_argument(
        "--order", 
        type=str, 
        default="popular",
        choices=["popular", "latest"],
        help="Sort order for results (default: popular)"
    )
    ap.add_argument(
        "--editors-choice", 
        action="store_true",
        help="Only return editor's choice images"
    )
    
    return ap.parse_args()


def validate_api_key() -> str:
    """Validate and return Pixabay API key."""
    api_key = os.getenv('PIXABAY_API_KEY')
    if not api_key:
        print("ERROR: PIXABAY_API_KEY environment variable not set", file=sys.stderr)
        print("\nTo set your API key (PowerShell):", file=sys.stderr)
        print("  $Env:PIXABAY_API_KEY = 'your-api-key-here'", file=sys.stderr)
        print("\nGet your free API key at: https://pixabay.com/api/docs/", file=sys.stderr)
        sys.exit(1)
    return api_key


def build_search_params(args, api_key: str) -> dict:
    """Build Pixabay API search parameters."""
    params = {
        'key': api_key,
        'q': args.query,
        'image_type': args.image_type,
        'orientation': args.orientation,
        'min_width': args.min_width,
        'min_height': args.min_height,
        'per_page': min(args.per_page, 200),  # API max is 200
        'safesearch': 'true' if args.safesearch else 'false',
        'order': args.order
    }
    
    # Optional filters
    if args.category:
        params['category'] = args.category
    
    if args.colors:
        # Pixabay accepts single color filter
        colors = [c.strip() for c in args.colors.split(',') if c.strip() in COLORS]
        if colors:
            params['colors'] = colors[0]  # Use first valid color
    
    if args.editors_choice:
        params['editors_choice'] = 'true'
    
    return params


def fetch_pixabay_images(params: dict) -> Optional[List[dict]]:
    """Fetch images from Pixabay API."""
    try:
        print(f"Searching Pixabay for: '{params['q']}'...")
        response = requests.get(PIXABAY_API_BASE, params=params, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        
        data = response.json()
        hits = data.get('hits', [])
        total = data.get('totalHits', 0)
        
        print(f"Found {total} total results, retrieved {len(hits)} images")
        
        if not hits:
            print("No images found matching your criteria", file=sys.stderr)
            return None
        
        return hits
    
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to fetch from Pixabay: {e}", file=sys.stderr)
        return None


def download_image(url: str) -> Optional[Image.Image]:
    """Download and return PIL Image from URL."""
    try:
        response = requests.get(url, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        img = Image.open(io.BytesIO(response.content))
        return img
    except Exception as e:
        print(f"WARNING: Failed to download image from {url}: {e}", file=sys.stderr)
        return None


def select_best_image(hits: List[dict], args) -> Optional[dict]:
    """Select the best image from search results."""
    # Prioritize by:
    # 1. Editor's choice images
    # 2. Higher resolution
    # 3. More likes
    # 4. More views
    
    scored_hits = []
    for hit in hits:
        score = 0
        
        # Editor's choice bonus
        if hit.get('editors_choice'):
            score += 1000
        
        # Resolution score
        width = hit.get('imageWidth', 0)
        height = hit.get('imageHeight', 0)
        score += (width * height) / 1000000  # Megapixels
        
        # Engagement score
        score += hit.get('likes', 0) * 0.1
        score += hit.get('views', 0) * 0.001
        
        scored_hits.append((score, hit))
    
    # Sort by score descending
    scored_hits.sort(reverse=True, key=lambda x: x[0])
    
    # Return best image
    if scored_hits:
        best_score, best_hit = scored_hits[0]
        print(f"Selected image: {best_hit['id']} (score: {best_score:.2f})")
        print(f"  Resolution: {best_hit['imageWidth']}x{best_hit['imageHeight']}")
        print(f"  Likes: {best_hit.get('likes', 0)}, Views: {best_hit.get('views', 0)}")
        print(f"  User: {best_hit.get('user', 'unknown')}")
        return best_hit
    
    return None


def resize_image(img: Image.Image, width: Optional[int], height: Optional[int]) -> Image.Image:
    """Resize image to specified dimensions while maintaining aspect ratio."""
    if not width and not height:
        return img
    
    orig_width, orig_height = img.size
    orig_ratio = orig_width / orig_height
    
    if width and height:
        # Both specified - crop to exact dimensions
        target_ratio = width / height
        
        if orig_ratio > target_ratio:
            # Image is wider - fit height and crop width
            new_height = height
            new_width = int(orig_ratio * new_height)
        else:
            # Image is taller - fit width and crop height
            new_width = width
            new_height = int(new_width / orig_ratio)
        
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Center crop
        left = (new_width - width) // 2
        top = (new_height - height) // 2
        img = img.crop((left, top, left + width, top + height))
    
    elif width:
        # Only width specified
        new_width = width
        new_height = int(new_width / orig_ratio)
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    else:
        # Only height specified
        new_height = height
        new_width = int(orig_ratio * new_height)
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    return img


def save_image(img: Image.Image, output_path: Path, args):
    """Save image to file with appropriate format."""
    # Create output directory if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Determine format from extension
    ext = output_path.suffix.lower()
    
    if ext == '.webp':
        img.convert('RGB').save(output_path, format='WEBP', quality=90)
    elif ext == '.jpg' or ext == '.jpeg':
        img.convert('RGB').save(output_path, format='JPEG', quality=95, optimize=True)
    elif ext == '.png':
        img.save(output_path, format='PNG', optimize=True)
    else:
        print(f"WARNING: Unknown extension {ext}, saving as JPEG", file=sys.stderr)
        output_path = output_path.with_suffix('.jpg')
        img.convert('RGB').save(output_path, format='JPEG', quality=95, optimize=True)
    
    print(f"✓ Image saved: {output_path} ({img.width}x{img.height})")
    return output_path


def main():
    """Main execution function."""
    args = parse_args()
    
    # Validate API key
    api_key = validate_api_key()
    
    # Build search parameters
    params = build_search_params(args, api_key)
    
    # Fetch images
    hits = fetch_pixabay_images(params)
    if not hits:
        sys.exit(1)
    
    # Select best image
    best_hit = select_best_image(hits, args)
    if not best_hit:
        print("ERROR: Could not select an image", file=sys.stderr)
        sys.exit(1)
    
    # Try largeImageURL first, fallback to webformatURL
    image_url = best_hit.get('largeImageURL') or best_hit.get('webformatURL')
    if not image_url:
        print("ERROR: No valid image URL found", file=sys.stderr)
        sys.exit(1)
    
    print(f"Downloading from: {image_url}")
    
    # Download image
    img = download_image(image_url)
    if not img:
        print("ERROR: Failed to download image", file=sys.stderr)
        sys.exit(1)
    
    print(f"Downloaded: {img.width}x{img.height} pixels")
    
    # Resize if requested
    if args.width or args.height:
        print(f"Resizing to {args.width or 'auto'}x{args.height or 'auto'}...")
        img = resize_image(img, args.width, args.height)
    
    # Save image
    output_path = Path(args.out)
    save_image(img, output_path, args)
    
    # Print attribution info (Pixabay requires attribution in some cases)
    print("\n" + "="*60)
    print("Image Attribution Info:")
    print(f"  Image ID: {best_hit['id']}")
    print(f"  User: {best_hit.get('user', 'unknown')} ({best_hit.get('user_id', '')})")
    print(f"  Source: Pixabay")
    print(f"  Page URL: {best_hit.get('pageURL', 'N/A')}")
    print("="*60)
    
    print("\n✓ Hero image successfully fetched and saved!")


if __name__ == '__main__':
    main()
