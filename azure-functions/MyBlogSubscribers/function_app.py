"""
Azure Functions app for blog subscriber management and weekly newsletter distribution.

Functions:
- SubscribeEmail: HTTP trigger for email subscription via web form
- weekly_newsletter: Timer trigger for automated weekly newsletter sending
"""
import json
import logging
import os
import sys

import azure.functions as func
from email_subscriber import (
    subscribe_email as subscribe_email_logic,
    SubscriptionError,
)
from weekly_job import send_weekly_newsletter
from validation import validate_email, normalize_email, MAX_EMAIL_LENGTH


def validate_storage_config() -> None:
    """
    Validate required Azure Storage environment variables on startup.
    
    Checks for presence of STORAGE_CONNECTION_STRING and validates its format.
    Exits the function app with clear error if configuration is invalid.
    
    Raises:
        SystemExit: If required Storage configuration is missing or invalid
    """
    storage_conn_str = os.environ.get('STORAGE_CONNECTION_STRING', '').strip()
    
    if not storage_conn_str:
        error_msg = (
            "FATAL: STORAGE_CONNECTION_STRING environment variable is not set. "
            "Subscriber management and newsletter functionality will not work. "
            "Please configure STORAGE_CONNECTION_STRING in Application Settings."
        )
        logging.critical(error_msg, extra={'config_check': 'storage', 'status': 'missing'})
        print(error_msg, file=sys.stderr)
        sys.exit(1)
    
    # Basic format validation (must contain required components)
    required_components = ['AccountName=', 'AccountKey=', 'EndpointSuffix=']
    missing_components = [comp for comp in required_components if comp not in storage_conn_str]
    
    if missing_components:
        error_msg = (
            f"FATAL: STORAGE_CONNECTION_STRING appears invalid. "
            f"Missing components: {', '.join(missing_components)}. "
            f"Expected format: DefaultEndpointsProtocol=https;AccountName=<name>;AccountKey=<key>;EndpointSuffix=core.windows.net"
        )
        logging.critical(
            error_msg,
            extra={
                'config_check': 'storage',
                'status': 'invalid_format',
                'missing_components': missing_components
            }
        )
        print(error_msg, file=sys.stderr)
        sys.exit(1)
    
    logging.info(
        "Azure Storage configuration validated successfully",
        extra={
            'config_check': 'storage',
            'status': 'valid',
            'connection_string_length': len(storage_conn_str)
        }
    )


def validate_brevo_config() -> None:
    """
    Validate required Brevo environment variables on startup.
    
    Checks for presence of BREVO_API_KEY and validates its format.
    Exits the function app with clear error if configuration is invalid.
    
    Raises:
        SystemExit: If required Brevo configuration is missing or invalid
    """
    brevo_api_key = os.environ.get('BREVO_API_KEY', '').strip()
    
    if not brevo_api_key:
        error_msg = (
            "FATAL: BREVO_API_KEY environment variable is not set. "
            "Newsletter functionality will not work. "
            "Please configure BREVO_API_KEY in Application Settings."
        )
        logging.critical(error_msg, extra={'config_check': 'brevo', 'status': 'missing'})
        print(error_msg, file=sys.stderr)
        sys.exit(1)
    
    # Basic format validation (Brevo API keys start with 'xkeysib-')
    if not brevo_api_key.startswith('xkeysib-'):
        error_msg = (
            "FATAL: BREVO_API_KEY appears invalid (should start with 'xkeysib-'). "
            "Please verify the API key in Application Settings."
        )
        logging.critical(
            error_msg,
            extra={
                'config_check': 'brevo',
                'status': 'invalid_format',
                'key_prefix': brevo_api_key[:10] if len(brevo_api_key) >= 10 else brevo_api_key
            }
        )
        print(error_msg, file=sys.stderr)
        sys.exit(1)
    
    logging.info(
        "Brevo configuration validated successfully",
        extra={
            'config_check': 'brevo',
            'status': 'valid',
            'key_length': len(brevo_api_key)
        }
    )


# Validate required configurations on startup
validate_storage_config()
validate_brevo_config()

# CORS Configuration - MUST be explicitly set in production (no insecure wildcard default)
ALLOWED_ORIGIN = os.environ.get('CORS_ALLOWED_ORIGIN')
if not ALLOWED_ORIGIN:
    logging.warning(
        "CORS_ALLOWED_ORIGIN not configured - using restrictive default. "
        "Set to your domain in production (e.g., 'https://quantuminvestor.net')"
    )
    ALLOWED_ORIGIN = 'https://quantuminvestor.net'  # Safe default

app = func.FunctionApp()


def get_cors_headers():
    """
    Get standardized CORS headers with security headers.
    
    Returns:
        dict: HTTP headers with CORS and security configurations
    """
    return {
        'Access-Control-Allow-Origin': ALLOWED_ORIGIN,
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Content-Type': 'application/json',
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY'
    }


@app.route(route="SubscribeEmail", methods=["POST", "OPTIONS"], auth_level=func.AuthLevel.ANONYMOUS)
def subscribe_email(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP trigger function for email subscription.
    
    Handles POST requests to subscribe email addresses and OPTIONS preflight requests.
    Validates email format and delegates to email_subscriber module.
    
    Args:
        req: HTTP request object containing email in JSON body
        
    Returns:
        HTTP response with subscription status
    """
    request_id = req.headers.get('x-request-id', 'unknown')
    
    logging.info(
        'SubscribeEmail function triggered',
        extra={
            'request_id': request_id,
            'method': req.method,
            'url': req.url
        }
    )

    # CORS headers with security headers
    headers = get_cors_headers()

    # Handle preflight OPTIONS request
    if req.method == 'OPTIONS':
        logging.debug(
            'CORS preflight request handled',
            extra={'request_id': request_id}
        )
        return func.HttpResponse(
            status_code=204,
            headers=headers
        )

    # Get email from request body
    try:
        req_body = req.get_json()
        email = req_body.get('email')
    except ValueError as e:
        logging.warning(
            'Invalid JSON in request body',
            extra={
                'request_id': request_id,
                'error': str(e),
                'content_type': req.headers.get('Content-Type')
            }
        )
        return func.HttpResponse(
            json.dumps({'message': 'Invalid request body'}),
            status_code=400,
            headers=headers
        )

    # Validate email using centralized validation
    is_valid, error_message = validate_email(email, strip_whitespace=True)
    
    if not is_valid:
        # Determine error category for logging
        if not email or not email.strip():
            error_category = 'missing'
        elif len(email.strip()) > MAX_EMAIL_LENGTH:
            error_category = 'too_long'
        else:
            error_category = 'invalid_format'
        
        logging.warning(
            f'Email validation failed: {error_message}',
            extra={
                'request_id': request_id,
                'error_message': error_message,
                'error_category': error_category,
                'email_length': len(email.strip()) if email else 0
            }
        )
        return func.HttpResponse(
            json.dumps({'message': error_message}),
            status_code=400,
            headers=headers
        )
    
    # Normalize email for storage
    email = normalize_email(email)

    try:
        result = subscribe_email_logic(email)
        status = result.get('status', 'unknown')
        message = result.get('message', 'Subscription processed.')
        
        # Determine if this was a new subscription or duplicate
        is_new = status == 'created'
        
        logging.info(
            f'Subscription {"created" if is_new else "already exists"}: {email}',
            extra={
                'request_id': request_id,
                'email': email,  # Already normalized
                'status': status,
                'is_new_subscriber': is_new
            }
        )

        return func.HttpResponse(
            json.dumps({'message': message}),
            status_code=200,
            headers=headers
        )

    except SubscriptionError as e:
        logging.error(
            f'Subscription configuration error: {str(e)}',
            extra={
                'request_id': request_id,
                'email': email,
                'error_type': 'configuration'
            }
        )
        return func.HttpResponse(
            json.dumps({'message': 'Service configuration error'}),
            status_code=500,
            headers=headers
        )

    except Exception as e:
        logging.error(
            f'Unexpected error during subscription: {type(e).__name__}: {str(e)}',
            extra={
                'request_id': request_id,
                'email': email,
                'error_type': type(e).__name__
            },
            exc_info=True  # Include stack trace for debugging
        )
        return func.HttpResponse(
            json.dumps({
                'message': 'An error occurred. Please try again later.'
            }),
            status_code=500,
            headers=headers
        )


@app.timer_trigger(schedule="0 0 12 * * FRI", arg_name="mytimer", run_on_startup=False)
def weekly_newsletter(mytimer: func.TimerRequest) -> None:
    """
    Timer trigger function that sends weekly newsletter every Friday at 12:00 PM UTC.
    
    Schedule format: "seconds minutes hours day month dayOfWeek"
    Current: 0 0 12 * * FRI = Every Friday at 12:00 PM UTC
    
    Adjust schedule as needed:
    - "0 0 9 * * MON" = Every Monday at 9:00 AM UTC
    - "0 30 14 * * *" = Every day at 2:30 PM UTC
    
    Args:
        mytimer: Timer request object with schedule information
    """
    logging.info(
        'Weekly newsletter timer trigger started',
        extra={
            'schedule': '0 0 12 * * FRI (Friday 12:00 PM UTC)',
            'past_due': mytimer.past_due
        }
    )
    
    if mytimer.past_due:
        logging.warning(
            'Timer is past due - executing delayed newsletter send',
            extra={'past_due': True}
        )
    
    try:
        # Send the newsletter
        result = send_weekly_newsletter()
        
        # Log detailed results
        status = result.get('status', 'unknown')
        if status == 'completed':
            logging.info(
                f"Weekly newsletter completed successfully: {result.get('sent', 0)}/{result.get('total', 0)} sent",
                extra={
                    'status': status,
                    'total_subscribers': result.get('total', 0),
                    'sent': result.get('sent', 0),
                    'failed': result.get('failed', 0),
                    'message': result.get('message', '')
                }
            )
        elif status == 'error':
            logging.error(
                f"Weekly newsletter failed: {result.get('error_type', 'unknown')} - {result.get('message', 'No details')}",
                extra={
                    'status': status,
                    'error_type': result.get('error_type', 'unknown'),
                    'message': result.get('message', '')
                }
            )
        else:
            logging.warning(
                f"Weekly newsletter completed with unexpected status: {status}",
                extra={'status': status, 'result': result}
            )
    
    except Exception as e:
        logging.error(
            f"Unexpected error in weekly newsletter timer trigger: {type(e).__name__}: {str(e)}",
            extra={'error_type': type(e).__name__},
            exc_info=True
        )