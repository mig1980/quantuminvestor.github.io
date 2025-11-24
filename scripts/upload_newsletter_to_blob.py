"""
Upload Newsletter HTML to Azure Blob Storage

Uploads generated newsletter HTML files to Azure Blob Storage for consumption
by the weekly newsletter Azure Function.

Usage:
    python scripts/upload_newsletter_to_blob.py <week_number>
    python scripts/upload_newsletter_to_blob.py 6
    python scripts/upload_newsletter_to_blob.py --latest
"""

import os
import sys
import logging
import time
from pathlib import Path
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def retry_with_backoff(max_retries=3, initial_delay=1.0, backoff_factor=2.0):
    """
    Decorator that implements exponential backoff retry logic.
    Consistent with generate_newsletter_narrative.py and weekly_job.py patterns.
    
    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds (default: 1.0)
        backoff_factor: Multiplier for delay on each retry (default: 2.0)
    
    Returns:
        Decorator function that wraps the target function with retry logic
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (ValueError, FileNotFoundError, KeyError):
                    # Don't retry on validation errors or missing config
                    raise
                except Exception as e:
                    last_exception = e
                    error_type = type(e).__name__
                    
                    if attempt < max_retries - 1:
                        logging.warning(
                            f"{func.__name__} attempt {attempt + 1}/{max_retries} failed: {error_type}: {str(e)}. "
                            f"Retrying in {delay}s...",
                            extra={'attempt': attempt + 1, 'error_type': error_type}
                        )
                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        logging.error(
                            f"{func.__name__} failed after {max_retries} attempts",
                            extra={'error_type': error_type},
                            exc_info=True
                        )
            
            raise last_exception
        return wrapper
    return decorator


def get_latest_week_number() -> int:
    """Auto-detect latest week from newsletters directory"""
    base_dir = Path(__file__).parent.parent
    newsletters_dir = base_dir / 'newsletters'
    
    if not newsletters_dir.exists():
        raise FileNotFoundError(f"Newsletters directory not found: {newsletters_dir}")
    
    week_numbers = []
    for file in newsletters_dir.glob('week*_newsletter.html'):
        # Extract week number from filename: week6_newsletter.html -> 6
        try:
            week_str = file.stem.split('_')[0].replace('week', '')
            week_numbers.append(int(week_str))
        except (ValueError, IndexError):
            continue
    
    if not week_numbers:
        raise ValueError("No newsletter HTML files found in newsletters directory")
    
    return max(week_numbers)


def upload_newsletter_to_blob(week_num: int, overwrite: bool = False) -> dict:
    """
    Upload newsletter HTML to Azure Blob Storage.
    
    Args:
        week_num: Week number to upload
        overwrite: If True, overwrite existing blob; if False, fail on existing blob
        
    Returns:
        dict: Upload result with status and details
        
    Raises:
        FileNotFoundError: If newsletter HTML not found locally
        ValueError: If STORAGE_CONNECTION_STRING not configured
        Exception: If upload fails after retries
    """
    logging.info(f"Uploading newsletter for Week {week_num}", extra={'week': week_num})
    
    # Get connection string
    connection_string = os.environ.get('STORAGE_CONNECTION_STRING')
    if not connection_string:
        error_msg = "STORAGE_CONNECTION_STRING environment variable not set"
        logging.error(error_msg)
        raise ValueError(error_msg)
    
    # Validate local file exists
    base_dir = Path(__file__).parent.parent
    local_path = base_dir / 'newsletters' / f'week{week_num}_newsletter.html'
    
    if not local_path.exists():
        error_msg = f"Newsletter HTML not found: {local_path}"
        logging.error(error_msg, extra={'week': week_num, 'path': str(local_path)})
        raise FileNotFoundError(error_msg)
    
    # Read HTML content
    with open(local_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    file_size = len(html_content)
    logging.info(
        f"Read local file: {file_size} bytes",
        extra={'week': week_num, 'size_bytes': file_size, 'path': str(local_path)}
    )
    
    # Validate HTML structure
    if not html_content.strip():
        raise ValueError("Newsletter HTML is empty")
    
    html_lower = html_content.lower()
    if '<html' not in html_lower or '<body' not in html_lower:
        raise ValueError("Newsletter HTML missing required structure (<html> and/or <body>)")
    
    # Azure Blob Storage configuration
    container_name = "newsletters"
    blob_name = f"week{week_num}.html"
    
    try:
        # Import Azure SDK
        from azure.storage.blob import BlobServiceClient, ContentSettings
        from azure.core.exceptions import ServiceRequestError, HttpResponseError
        
        # Create BlobServiceClient
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
        
        logging.info(
            f"Uploading to Azure Blob Storage: {container_name}/{blob_name}",
            extra={'week': week_num, 'container': container_name, 'blob': blob_name}
        )
        
        # Check if blob already exists (with retry for transient network errors)
        @retry_with_backoff(max_retries=3, initial_delay=0.5)
        def check_blob_exists():
            return blob_client.exists()
        
        blob_exists = check_blob_exists()
        
        if blob_exists and not overwrite:
            error_msg = (
                f"Blob already exists: {container_name}/{blob_name}\n"
                f"Use --overwrite flag to replace existing blob"
            )
            logging.error(error_msg, extra={'week': week_num, 'blob': blob_name})
            raise ValueError(error_msg)
        
        # Upload with retry logic
        @retry_with_backoff(max_retries=3, initial_delay=1.0)
        def upload_blob():
            return blob_client.upload_blob(
                html_content,
                overwrite=overwrite,
                content_settings=ContentSettings(content_type='text/html; charset=utf-8')
            )
        
        result = upload_blob()
        
        # Get blob URL
        blob_url = blob_client.url
        
        logging.info(
            f"Successfully uploaded newsletter to blob storage ({file_size} bytes)",
            extra={
                'week': week_num,
                'blob_url': blob_url,
                'size_bytes': file_size,
                'overwritten': blob_exists
            }
        )
        
        return {
            'status': 'success',
            'week': week_num,
            'blob_url': blob_url,
            'blob_name': blob_name,
            'container': container_name,
            'size_bytes': file_size,
            'overwritten': blob_exists
        }
        
    except ImportError as e:
        error_msg = (
            "Azure Storage SDK not installed. Install with:\n"
            "pip install azure-storage-blob"
        )
        logging.error(error_msg, exc_info=True)
        raise ImportError(error_msg)
    
    except (ServiceRequestError, HttpResponseError) as e:
        # Azure-specific errors (should be caught by retry logic, but handle here as fallback)
        status = getattr(e, 'status_code', 'unknown')
        error_msg = f"Azure Blob Storage error: {type(e).__name__} (status: {status}): {str(e)}"
        logging.error(
            error_msg,
            extra={'week': week_num, 'container': container_name, 'blob': blob_name, 'status_code': status},
            exc_info=True
        )
        raise IOError(error_msg)
    
    except Exception as e:
        error_msg = f"Failed to upload newsletter to blob storage: {type(e).__name__}: {str(e)}"
        logging.error(
            error_msg,
            extra={'week': week_num, 'container': container_name, 'blob': blob_name},
            exc_info=True
        )
        raise


def resolve_week_number(args) -> int:
    """
    Resolve week number from command-line arguments.
    Extracted from main() for better testability and separation of concerns.
    
    Args:
        args: Parsed argparse.Namespace object
        
    Returns:
        int: Validated week number
        
    Raises:
        ValueError: If week number is invalid
    """
    if args.latest or (args.week and args.week.lower() == '--latest'):
        week_num = get_latest_week_number()
        logging.info(f"Auto-detected latest week: {week_num}", extra={'week': week_num, 'auto_detected': True})
        return week_num
    elif args.week:
        try:
            week_num = int(args.week)
            if week_num < 1:
                raise ValueError(f"Week number must be positive (got {week_num})")
            return week_num
        except ValueError as e:
            raise ValueError(f"Invalid week number '{args.week}': {str(e)}")
    else:
        raise ValueError("Week number required (provide number or --latest flag)")


def main():
    """Main execution function"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Upload newsletter HTML to Azure Blob Storage',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Upload specific week:
    python scripts/upload_newsletter_to_blob.py 6
  
  Upload latest week (auto-detect):
    python scripts/upload_newsletter_to_blob.py --latest
  
  Overwrite existing blob:
    python scripts/upload_newsletter_to_blob.py 6 --overwrite

Environment Variables:
  STORAGE_CONNECTION_STRING  Azure Storage connection string (required)
        """
    )
    
    parser.add_argument(
        'week',
        type=str,
        nargs='?',
        help='Week number to upload (e.g., 6) or --latest for auto-detect'
    )
    parser.add_argument(
        '--latest',
        action='store_true',
        help='Auto-detect and upload the latest week'
    )
    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='Overwrite existing blob if it exists'
    )
    
    args = parser.parse_args()
    
    try:
        # Resolve week number (raises ValueError if invalid)
        week_num = resolve_week_number(args)
        
        # Upload newsletter
        result = upload_newsletter_to_blob(week_num, overwrite=args.overwrite)
        
        # Print success message
        print("\n" + "="*70)
        print("☁️  UPLOAD COMPLETE")
        print("="*70)
        print(f"✅ Newsletter uploaded successfully")
        print(f"📅 Week: {result['week']}")
        print(f"📦 Blob: {result['container']}/{result['blob_name']}")
        print(f"📏 Size: {result['size_bytes']:,} bytes ({result['size_bytes']/1024:.1f} KB)")
        print(f"🔗 URL: {result['blob_url']}")
        if result['overwritten']:
            print(f"⚠️  Previous version overwritten")
        print("\n🔍 NEXT STEPS:")
        print(f"1. Verify blob in Azure Portal: Storage Account → Containers → newsletters")
        print(f"2. Test Azure Function: Manually trigger weekly_newsletter function")
        print(f"3. Check Function logs for successful newsletter download")
        print("="*70)
        
    except ValueError as e:
        # Covers both week number validation and upload errors
        if "Week number required" in str(e) or "Invalid week number" in str(e):
            parser.print_help()
        else:
            logging.error(f"Configuration/validation error: {e}")
            print(f"\n❌ Error: {e}")
            if "STORAGE_CONNECTION_STRING" in str(e):
                print("\n💡 Solution: Set the environment variable")
                print("   $env:STORAGE_CONNECTION_STRING = 'your-connection-string'")
            elif "overwrite" in str(e).lower():
                print("\n💡 Solution: Use --overwrite flag to replace existing blob")
        sys.exit(1)
    
    except FileNotFoundError as e:
        logging.error(f"File not found: {e}")
        print(f"\n❌ Error: {e}")
        print("\n💡 Solution: Run Stage 2 to generate newsletter HTML")
        print(f"   python scripts/generate_newsletter_html.py {getattr(args, 'week', 'N') or 'N'}")
        sys.exit(1)
    
    except ImportError as e:
        logging.error(f"Dependency error: {e}")
        print(f"\n❌ Error: {e}")
        print("\n💡 Solution: Install Azure Storage SDK")
        print("   pip install azure-storage-blob")
        sys.exit(1)
    
    except Exception as e:
        logging.error(f"Upload failed: {type(e).__name__}: {str(e)}", exc_info=True)
        print(f"\n❌ Error: Upload failed")
        print(f"   {type(e).__name__}: {str(e)}")
        print("\n💡 Troubleshooting checklist:")
        print("   1. Verify STORAGE_CONNECTION_STRING is correct")
        print("   2. Confirm Storage Account has 'newsletters' container")
        print("   3. Check network connectivity to Azure")
        print("   4. Review logs above for detailed error information")
        sys.exit(1)


if __name__ == "__main__":
    main()
