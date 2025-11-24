"""
Weekly email job - sends newsletter to all active subscribers.
Triggered every Friday at 12:00 PM UTC (adjust schedule as needed).
"""
import os
import re
import logging
import time
from typing import Dict, Any
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError as RequestsConnectionError
from email_subscriber import get_active_subscribers, SubscriptionError
from mailer import send_bulk_email, MailerError
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ServiceRequestError, HttpResponseError

# GitHub repository configuration - MUST be set in production
GITHUB_OWNER = os.environ.get('GITHUB_OWNER')
GITHUB_REPO = os.environ.get('GITHUB_REPO')
GITHUB_POSTS_PATH = os.environ.get('GITHUB_POSTS_PATH', 'Posts')  # Path can have sensible default

if not GITHUB_OWNER or not GITHUB_REPO:
    error_msg = (
        "GITHUB_OWNER and GITHUB_REPO environment variables must be set. "
        "Configure in Azure Function App Settings."
    )
    logging.critical(error_msg, extra={'config_check': 'github', 'status': 'missing'})
    raise ValueError(error_msg)


def retry_with_backoff(max_retries=3, initial_delay=1.0, backoff_factor=2.0):
    """
    Decorator that implements exponential backoff retry logic.
    
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
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (RequestException, ServiceRequestError, HttpResponseError, ConnectionError) as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        # Check if error is retryable
                        is_retryable = False
                        
                        if isinstance(e, (Timeout, RequestsConnectionError, ServiceRequestError)):
                            # Network errors are always retryable
                            is_retryable = True
                        elif isinstance(e, (RequestException, HttpResponseError)):
                            # Check HTTP status code
                            status = getattr(e, 'status_code', getattr(e.response, 'status_code', 0) if hasattr(e, 'response') else 0)
                            # Retry on server errors (5xx) or rate limiting (429)
                            is_retryable = status >= 500 or status == 429
                        
                        if is_retryable:
                            logging.warning(
                                f"{func.__name__} failed on attempt {attempt + 1}/{max_retries + 1}: "
                                f"{type(e).__name__}: {str(e)}. Retrying in {delay:.1f}s..."
                            )
                            time.sleep(delay)
                            delay *= backoff_factor
                            continue
                    
                    # Non-retryable error or max retries reached
                    logging.error(
                        f"{func.__name__} failed after {max_retries + 1} attempts: "
                        f"{type(e).__name__}: {str(e)}"
                    )
                    raise last_exception
                except Exception as e:
                    # Non-retryable exceptions
                    raise e
            
            # Should never reach here, but just in case
            raise last_exception
        
        return wrapper
    return decorator


@retry_with_backoff(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
def _fetch_github_contents(api_url: str, timeout: int = 10):
    """
    Internal function to fetch GitHub API contents with retry logic.
    """
    response = requests.get(api_url, timeout=timeout)
    response.raise_for_status()
    return response.json()


def get_latest_week_number() -> int:
    """
    Auto-detect the latest week number from GitHub Posts folder.
    Includes automatic retry on transient failures.
    
    Fetches file list from GitHub API and scans for: GenAi-Managed-Stocks-Portfolio-Week-X.html
    
    Returns:
        int: Latest week number (e.g., 6)
        
    Raises:
        FileNotFoundError: If no weekly posts found or GitHub API fails after retries
    """
    # GitHub API URL to list files in Posts directory
    api_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{GITHUB_POSTS_PATH}"
    
    try:
        logging.info(
            f"Fetching Posts directory from GitHub: {GITHUB_OWNER}/{GITHUB_REPO}/{GITHUB_POSTS_PATH}",
            extra={'github_url': api_url}
        )
        
        files_data = _fetch_github_contents(api_url, timeout=10)
        
        # Extract filenames
        filenames = [item['name'] for item in files_data if item.get('type') == 'file']
        
        # Find weekly portfolio posts
        pattern = r'GenAi-Managed-Stocks-Portfolio-Week-(\d+)\.html'
        week_files = [f for f in filenames if re.match(pattern, f)]
        
        if not week_files:
            error_msg = (
                f"No weekly portfolio posts found in GitHub {GITHUB_OWNER}/{GITHUB_REPO}/{GITHUB_POSTS_PATH}. "
                f"Found {len(filenames)} total files."
            )
            logging.error(error_msg, extra={'files_found': len(filenames)})
            raise FileNotFoundError(error_msg)
        
        # Extract week numbers and return the highest
        week_numbers = [int(re.search(pattern, f).group(1)) for f in week_files]
        latest_week = max(week_numbers)
        
        logging.info(
            f"Latest week detected from GitHub: Week {latest_week} (found {len(week_files)} posts)",
            extra={'latest_week': latest_week, 'total_posts': len(week_files)}
        )
        return latest_week
        
    except RequestException as e:
        error_msg = f"Failed to fetch Posts directory from GitHub: {type(e).__name__}: {str(e)}"
        logging.error(
            error_msg,
            extra={'github_url': api_url, 'error_type': type(e).__name__}
        )
        raise FileNotFoundError(error_msg)
    except (KeyError, ValueError, AttributeError) as e:
        error_msg = f"Failed to parse GitHub API response: {type(e).__name__}: {str(e)}"
        logging.error(
            error_msg,
            extra={'github_url': api_url, 'error_type': type(e).__name__}
        )
        raise FileNotFoundError(error_msg)


@retry_with_backoff(max_retries=3, initial_delay=0.5, backoff_factor=2.0)
def _download_blob_with_retry(blob_client):
    """
    Internal function to download blob with retry logic.
    """
    if not blob_client.exists():
        raise FileNotFoundError("Blob does not exist")
    download_stream = blob_client.download_blob()
    return download_stream.readall().decode('utf-8')


def get_weekly_email_content() -> Dict[str, str]:
    """
    Download pre-generated newsletter HTML from Azure Blob Storage.
    Includes automatic retry on transient failures.
    
    Looks for: newsletters/week{X}.html in Blob Storage
    
    Returns:
        dict: Dictionary with 'subject' and 'html_body'
        
    Raises:
        FileNotFoundError: If newsletter HTML not found (prevents sending emails)
        ValueError: If newsletter HTML is invalid or empty
        IOError: If Blob Storage access fails after retries
    """
    # Auto-detect latest week from GitHub Posts
    try:
        week_number = get_latest_week_number()
    except FileNotFoundError as e:
        logging.error(f"Failed to detect latest week number: {str(e)}")
        raise
    
    # Get Blob Storage connection string
    connection_string = os.environ.get('STORAGE_CONNECTION_STRING')
    if not connection_string:
        error_msg = "STORAGE_CONNECTION_STRING not configured"
        logging.error(error_msg)
        raise IOError(error_msg)
    
    blob_name = f"week{week_number}.html"
    container_name = "newsletters"
    
    try:
        # Create BlobServiceClient
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
        
        logging.info(
            f"Downloading newsletter from Blob Storage: {container_name}/{blob_name}",
            extra={'week': week_number, 'container': container_name, 'blob': blob_name}
        )
        
        # Download blob content with retry logic
        try:
            html_body = _download_blob_with_retry(blob_client)
        except FileNotFoundError:
            error_msg = (
                f"Newsletter file not found in Azure Blob Storage\n"
                f"Container: {container_name}\n"
                f"Blob: {blob_name}\n"
                f"Action required: Generate and upload newsletter HTML for week {week_number}"
            )
            logging.error(
                error_msg,
                extra={'week': week_number, 'container': container_name, 'blob': blob_name}
            )
            raise FileNotFoundError(error_msg)
        
        logging.info(
            f"Successfully downloaded newsletter from Blob Storage ({len(html_body)} bytes)",
            extra={'week': week_number, 'size_bytes': len(html_body)}
        )
        
    except FileNotFoundError:
        # Re-raise FileNotFoundError as-is (already logged above)
        raise
    except UnicodeDecodeError as e:
        error_msg = (
            f"Newsletter file encoding error: {container_name}/{blob_name}\n"
            f"Error: {str(e)}\n"
            f"Action required: Ensure file is saved as UTF-8"
        )
        logging.error(
            error_msg,
            extra={'week': week_number, 'container': container_name, 'blob': blob_name, 'error_type': 'encoding'}
        )
        raise ValueError(error_msg)
    except Exception as e:
        error_msg = (
            f"Failed to download newsletter from Blob Storage: {container_name}/{blob_name}\n"
            f"Error: {type(e).__name__}: {str(e)}\n"
            f"Action required: Check Blob Storage connection and blob existence"
        )
        logging.error(
            error_msg,
            extra={'week': week_number, 'container': container_name, 'blob': blob_name, 'error_type': type(e).__name__}
        )
        raise IOError(error_msg)
    
    # Validate HTML content
    if not html_body or not html_body.strip():
        error_msg = (
            f"Newsletter file is empty: {container_name}/{blob_name}\n"
            f"Action required: Generate valid newsletter HTML content"
        )
        logging.error(
            error_msg,
            extra={'week': week_number, 'container': container_name, 'blob': blob_name}
        )
        raise ValueError(error_msg)
    
    # Basic HTML structure validation
    html_lower = html_body.lower()
    if '<html' not in html_lower or '<body' not in html_lower:
        error_msg = (
            f"Newsletter file missing required HTML structure: {container_name}/{blob_name}\n"
            f"Missing: <html> and/or <body> tags\n"
            f"Action required: Ensure newsletter is valid HTML email"
        )
        logging.error(
            error_msg,
            extra={'week': week_number, 'container': container_name, 'blob': blob_name}
        )
        raise ValueError(error_msg)
    
    logging.info(
        f"Successfully validated newsletter HTML ({len(html_body)} bytes)",
        extra={'week': week_number, 'size_bytes': len(html_body)}
    )
    
    subject = f"📊 Week {week_number} Portfolio Update"
    
    return {
        "subject": subject,
        "html_body": html_body
    }


def send_weekly_newsletter() -> Dict[str, Any]:
    """
    Main function to send weekly newsletter to all active subscribers.
    Includes comprehensive error handling and structured logging.
    
    Returns:
        dict: Summary of email sending results with detailed status information
    """
    logging.info("Weekly newsletter job started")
    
    try:
        # Get all active subscribers
        logging.info("Fetching active subscribers...")
        subscribers = get_active_subscribers()
        
        if not subscribers:
            logging.info("No active subscribers found - newsletter job completed with no sends")
            return {
                "status": "completed",
                "message": "No active subscribers",
                "total": 0,
                "sent": 0,
                "failed": 0
            }
        
        logging.info(
            f"Found {len(subscribers)} active subscribers",
            extra={'subscriber_count': len(subscribers)}
        )
        
        # Get email content
        logging.info("Fetching newsletter content...")
        email_content = get_weekly_email_content()
        
        logging.info(
            f"Newsletter content ready - Subject: '{email_content['subject']}'",
            extra={'subject': email_content['subject'], 'content_size': len(email_content['html_body'])}
        )
        
        # Send to all subscribers
        logging.info(f"Starting bulk email send to {len(subscribers)} subscribers...")
        result = send_bulk_email(
            recipients=subscribers,
            subject=email_content["subject"],
            html_body=email_content["html_body"]
        )
        
        success_rate = (result['sent'] / result['total'] * 100) if result['total'] > 0 else 0
        
        logging.info(
            f"Weekly newsletter job completed: {result['sent']}/{result['total']} sent successfully ({success_rate:.1f}%)",
            extra={
                'total': result['total'],
                'sent': result['sent'],
                'failed': result['failed'],
                'success_rate': success_rate
            }
        )
        
        return {
            "status": "completed",
            "message": f"Newsletter sent to {result['sent']} subscribers",
            **result
        }
        
    except FileNotFoundError as e:
        logging.error(
            f"Newsletter file error: {str(e)}",
            extra={'error_type': 'missing_newsletter'}
        )
        return {
            "status": "error",
            "error_type": "missing_newsletter",
            "message": str(e),
            "total": 0,
            "sent": 0,
            "failed": 0
        }
    except ValueError as e:
        logging.error(
            f"Newsletter validation error: {str(e)}",
            extra={'error_type': 'invalid_newsletter'}
        )
        return {
            "status": "error",
            "error_type": "invalid_newsletter",
            "message": str(e),
            "total": 0,
            "sent": 0,
            "failed": 0
        }
    except IOError as e:
        logging.error(
            f"Newsletter file access error: {str(e)}",
            extra={'error_type': 'file_access_error'}
        )
        return {
            "status": "error",
            "error_type": "file_access_error",
            "message": str(e),
            "total": 0,
            "sent": 0,
            "failed": 0
        }
    except SubscriptionError as e:
        logging.error(
            f"Subscription error: {str(e)}",
            extra={'error_type': 'subscription_error'}
        )
        return {
            "status": "error",
            "error_type": "subscription_error",
            "message": f"Failed to get subscribers: {str(e)}",
            "total": 0,
            "sent": 0,
            "failed": 0
        }
    except MailerError as e:
        logging.error(
            f"Mailer error: {str(e)}",
            extra={'error_type': 'mailer_error'}
        )
        return {
            "status": "error",
            "error_type": "mailer_error",
            "message": f"Failed to send emails: {str(e)}",
            "total": 0,
            "sent": 0,
            "failed": 0
        }
    except Exception as e:
        logging.error(
            f"Unexpected error in weekly newsletter job: {type(e).__name__}: {str(e)}",
            extra={'error_type': 'unexpected_error', 'exception_type': type(e).__name__},
            exc_info=True  # Include stack trace for unexpected errors
        )
        return {
            "status": "error",
            "error_type": "unexpected_error",
            "message": f"Unexpected error: {str(e)}",
            "total": 0,
            "sent": 0,
            "failed": 0
        }
