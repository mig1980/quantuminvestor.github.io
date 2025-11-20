"""Flask API Server for Pixabay Hero Image Fetcher

This server provides REST API endpoints for the HTML frontend to interact with
the Pixabay API and manage hero images.

Usage:
  python scripts/pixabay_api_server.py

The server will start on http://localhost:5000

Endpoints:
  POST /api/search - Search for images on Pixabay
  POST /api/download - Download an image
  POST /api/save - Save an image to Media folder
"""
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import sys
import io
import requests
from pathlib import Path
from PIL import Image
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Configuration
PIXABAY_API_BASE = "https://pixabay.com/api/"
REPO_ROOT = Path(__file__).parent.parent
MEDIA_FOLDER = REPO_ROOT / "Media"

def get_api_key():
    """Get Pixabay API key from environment."""
    api_key = os.getenv('PIXABAY_API_KEY')
    if not api_key:
        raise ValueError("PIXABAY_API_KEY environment variable not set")
    return api_key

@app.route('/api/search', methods=['POST'])
def search_images():
    """Search Pixabay for images."""
    try:
        data = request.get_json()
        api_key = get_api_key()
        
        # Build search parameters
        params = {
            'key': api_key,
            'q': data.get('query', ''),
            'image_type': 'photo',
            'orientation': 'horizontal',
            'per_page': min(int(data.get('per_page', 5)), 20),
            'safesearch': 'true',
            'order': 'popular'
        }
        
        # Optional filters
        if data.get('category'):
            params['category'] = data['category']
        
        if data.get('colors'):
            params['colors'] = data['colors']
        
        # Make API request
        response = requests.get(PIXABAY_API_BASE, params=params, timeout=15)
        response.raise_for_status()
        
        result = response.json()
        images = result.get('hits', [])
        
        return jsonify({
            'success': True,
            'total': result.get('totalHits', 0),
            'images': images
        })
    
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'API request failed: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download', methods=['POST'])
def download_image():
    """Download and resize image, return as file."""
    try:
        data = request.get_json()
        image_info = data.get('image', {})
        format_type = data.get('format', 'webp').lower()
        width = int(data.get('width', 1200))
        height = int(data.get('height', 800))
        
        # Get image URL
        image_url = image_info.get('largeImageURL') or image_info.get('webformatURL')
        if not image_url:
            return jsonify({'error': 'No image URL found'}), 400
        
        # Download image
        img_response = requests.get(image_url, timeout=15)
        img_response.raise_for_status()
        
        # Process image
        img = Image.open(io.BytesIO(img_response.content))
        img = resize_and_crop(img, width, height)
        
        # Save to buffer
        buffer = io.BytesIO()
        save_image_to_buffer(img, buffer, format_type)
        buffer.seek(0)
        
        # Return file
        mimetype = {
            'webp': 'image/webp',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png'
        }.get(format_type, 'image/jpeg')
        
        return send_file(
            buffer,
            mimetype=mimetype,
            as_attachment=True,
            download_name=f'pixabay_{image_info.get("id", "image")}.{format_type}'
        )
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/save', methods=['POST'])
def save_image():
    """Download, resize, and save image to Media folder."""
    try:
        data = request.get_json()
        image_info = data.get('image', {})
        format_type = data.get('format', 'webp').lower()
        width = int(data.get('width', 1200))
        height = int(data.get('height', 800))
        
        # Get image URL
        image_url = image_info.get('largeImageURL') or image_info.get('webformatURL')
        if not image_url:
            return jsonify({'error': 'No image URL found'}), 400
        
        # Download image
        img_response = requests.get(image_url, timeout=15)
        img_response.raise_for_status()
        
        # Process image
        img = Image.open(io.BytesIO(img_response.content))
        img = resize_and_crop(img, width, height)
        
        # Create Media folder if it doesn't exist
        MEDIA_FOLDER.mkdir(exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'pixabay_{image_info.get("id", timestamp)}.{format_type}'
        filepath = MEDIA_FOLDER / filename
        
        # Save image
        save_image_to_file(img, filepath, format_type)
        
        # Return relative path
        relative_path = f'Media/{filename}'
        
        return jsonify({
            'success': True,
            'path': relative_path,
            'filename': filename
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def resize_and_crop(img, target_width, target_height):
    """Resize and crop image to target dimensions."""
    # Convert to RGB if necessary
    if img.mode in ('RGBA', 'LA', 'P'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
        img = background
    
    # Calculate aspect ratios
    img_ratio = img.width / img.height
    target_ratio = target_width / target_height
    
    # Resize to fit, then crop
    if img_ratio > target_ratio:
        # Image is wider - fit height and crop width
        new_height = target_height
        new_width = int(img_ratio * new_height)
    else:
        # Image is taller - fit width and crop height
        new_width = target_width
        new_height = int(new_width / img_ratio)
    
    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # Center crop
    left = (new_width - target_width) // 2
    top = (new_height - target_height) // 2
    img = img.crop((left, top, left + target_width, top + target_height))
    
    return img

def save_image_to_buffer(img, buffer, format_type):
    """Save PIL Image to BytesIO buffer."""
    if format_type == 'webp':
        img.save(buffer, format='WEBP', quality=90)
    elif format_type in ('jpg', 'jpeg'):
        img.save(buffer, format='JPEG', quality=95, optimize=True)
    elif format_type == 'png':
        img.save(buffer, format='PNG', optimize=True)
    else:
        img.save(buffer, format='JPEG', quality=95)

def save_image_to_file(img, filepath, format_type):
    """Save PIL Image to file."""
    if format_type == 'webp':
        img.save(filepath, format='WEBP', quality=90)
    elif format_type in ('jpg', 'jpeg'):
        img.save(filepath, format='JPEG', quality=95, optimize=True)
    elif format_type == 'png':
        img.save(filepath, format='PNG', optimize=True)
    else:
        img.save(filepath, format='JPEG', quality=95)

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    try:
        api_key = get_api_key()
        return jsonify({
            'status': 'healthy',
            'api_key_configured': True
        })
    except ValueError:
        return jsonify({
            'status': 'unhealthy',
            'api_key_configured': False,
            'error': 'PIXABAY_API_KEY not set'
        }), 500

if __name__ == '__main__':
    print("=" * 60)
    print("Pixabay Hero Image Fetcher API Server")
    print("=" * 60)
    print(f"Server starting on http://localhost:5000")
    print(f"Media folder: {MEDIA_FOLDER}")
    print("\nMake sure PIXABAY_API_KEY environment variable is set:")
    print("  $Env:PIXABAY_API_KEY = 'your-api-key-here'")
    print("\nEndpoints:")
    print("  POST /api/search - Search for images")
    print("  POST /api/download - Download an image")
    print("  POST /api/save - Save to Media folder")
    print("  GET  /api/health - Health check")
    print("\nOpen the HTML frontend in your browser:")
    print("  pixabay-fetcher.html")
    print("=" * 60)
    
    app.run(debug=True, port=5000)
