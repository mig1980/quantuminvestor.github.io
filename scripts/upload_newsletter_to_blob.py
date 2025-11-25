"""
Upload Newsletter HTML to Azure Blob Storage

Uploads generated newsletter HTML files to Azure Blob Storage for consumption
by the weekly newsletter Azure Function.

Usage:
    python scripts/upload_newsletter_to_blob.py <week_number>
    python scripts/upload_newsletter_to_blob.py 6
    python scripts/upload_newsletter_to_blob.py --latest
"""

import logging
import os
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def get_latest_week_number() -> int:
    """Auto-detect latest week from newsletters directory"""
    base_dir = Path(__file__).parent.parent
    newsletters_dir = base_dir / "newsletters"

    if not newsletters_dir.exists():
        raise FileNotFoundError(f"Newsletters directory not found: {newsletters_dir}")

    week_numbers = []
    for file in newsletters_dir.glob("week*_newsletter.html"):
        # Extract week number from filename: week6_newsletter.html -> 6
        try:
            week_str = file.stem.split("_")[0].replace("week", "")
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
    logging.info(f"Uploading newsletter for Week {week_num}")

    # Get connection string
    connection_string = os.environ.get("STORAGE_CONNECTION_STRING")
    if not connection_string:
        raise ValueError("STORAGE_CONNECTION_STRING environment variable not set")

    # Validate local file exists
    base_dir = Path(__file__).parent.parent
    local_path = base_dir / "newsletters" / f"week{week_num}_newsletter.html"

    if not local_path.exists():
        raise FileNotFoundError(f"Newsletter HTML not found: {local_path}")

    # Read HTML content
    with open(local_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    file_size = len(html_content)
    logging.info(f"Read {file_size:,} bytes from {local_path.name}")

    # Validate HTML structure
    if not html_content.strip():
        raise ValueError("Newsletter HTML is empty")

    html_lower = html_content.lower()
    if "<html" not in html_lower or "<body" not in html_lower:
        raise ValueError("Newsletter HTML missing required structure (<html> and/or <body>)")

    # Azure Blob Storage configuration
    container_name = "newsletters"
    blob_name = f"week{week_num}.html"

    try:
        # Import Azure SDK
        from azure.storage.blob import BlobServiceClient, ContentSettings

        # Create BlobServiceClient
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)

        logging.info(f"Uploading to {container_name}/{blob_name}")

        # Check if blob already exists
        blob_exists = blob_client.exists()

        if blob_exists and not overwrite:
            raise ValueError(
                f"Blob already exists: {container_name}/{blob_name}\n" f"Use --overwrite flag to replace existing blob"
            )

        # Upload blob
        blob_client.upload_blob(
            html_content,
            overwrite=overwrite,
            content_settings=ContentSettings(content_type="text/html; charset=utf-8"),
        )

        # Get blob URL
        blob_url = blob_client.url

        logging.info(f"Upload complete: {file_size:,} bytes → {blob_name}")

        return {
            "status": "success",
            "week": week_num,
            "blob_url": blob_url,
            "blob_name": blob_name,
            "container": container_name,
            "size_bytes": file_size,
            "overwritten": blob_exists,
        }

    except ImportError:
        raise ImportError("Azure Storage SDK not installed. Install with:\n" "pip install azure-storage-blob")
    except Exception as e:
        logging.error(f"Upload failed: {type(e).__name__}: {e}")
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
    if args.latest or (args.week and args.week.lower() == "--latest"):
        week_num = get_latest_week_number()
        logging.info(f"Auto-detected latest week: {week_num}")
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
        description="Upload newsletter HTML to Azure Blob Storage",
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
        """,
    )

    parser.add_argument(
        "week",
        type=str,
        nargs="?",
        help="Week number to upload (e.g., 6) or --latest for auto-detect",
    )
    parser.add_argument("--latest", action="store_true", help="Auto-detect and upload the latest week")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing blob if it exists")

    args = parser.parse_args()

    try:
        # Resolve week number (raises ValueError if invalid)
        week_num = resolve_week_number(args)

        # Upload newsletter
        result = upload_newsletter_to_blob(week_num, overwrite=args.overwrite)

        # Print success message
        print("\n" + "=" * 70)
        print("☁️  UPLOAD COMPLETE")
        print("=" * 70)
        print(f"✅ Newsletter uploaded successfully")
        print(f"📅 Week: {result['week']}")
        print(f"📦 Blob: {result['container']}/{result['blob_name']}")
        print(f"📏 Size: {result['size_bytes']:,} bytes ({result['size_bytes']/1024:.1f} KB)")
        print(f"🔗 URL: {result['blob_url']}")
        if result["overwritten"]:
            print(f"⚠️  Previous version overwritten")
        print("\n🔍 NEXT STEPS:")
        print(f"1. Verify blob in Azure Portal: Storage Account → Containers → newsletters")
        print(f"2. Test Azure Function: Manually trigger weekly_newsletter function")
        print(f"3. Check Function logs for successful newsletter download")
        print("=" * 70)

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
