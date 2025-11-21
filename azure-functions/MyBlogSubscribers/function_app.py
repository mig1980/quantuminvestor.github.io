import azure.functions as func
import json
import logging
import os
import re
from datetime import datetime
from azure.data.tables import TableClient, TableEntity
from azure.core.exceptions import ResourceExistsError

app = func.FunctionApp()

@app.route(route="SubscribeEmail", methods=["POST", "OPTIONS"], auth_level=func.AuthLevel.FUNCTION)
def subscribe_email(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    # CORS headers
    headers = {
        'Access-Control-Allow-Origin': '*',  # Change to your domain in production
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Content-Type': 'application/json'
    }

    # Handle preflight OPTIONS request
    if req.method == 'OPTIONS':
        return func.HttpResponse(
            status_code=204,
            headers=headers
        )

    # Get email from request body
    try:
        req_body = req.get_json()
        email = req_body.get('email')
    except ValueError:
        return func.HttpResponse(
            json.dumps({'message': 'Invalid request body'}),
            status_code=400,
            headers=headers
        )

    # Validate email presence
    if not email:
        return func.HttpResponse(
            json.dumps({'message': 'Email is required'}),
            status_code=400,
            headers=headers
        )

    # Validate email format
    email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    if not re.match(email_regex, email):
        return func.HttpResponse(
            json.dumps({'message': 'Invalid email format'}),
            status_code=400,
            headers=headers
        )

    try:
        # Get credentials from environment variables
        connection_string = os.environ.get('STORAGE_CONNECTION_STRING')
        
        if not connection_string:
            logging.error('STORAGE_CONNECTION_STRING not configured')
            return func.HttpResponse(
                json.dumps({'message': 'Service configuration error'}),
                status_code=500,
                headers=headers
            )
        
        table_name = 'subscribers'

        # Create table client
        table_client = TableClient.from_connection_string(
            conn_str=connection_string,
            table_name=table_name
        )

        # Create entity
        entity = TableEntity()
        entity['PartitionKey'] = 'subscriber'
        entity['RowKey'] = email.lower()
        entity['email'] = email.lower()
        entity['subscribedAt'] = datetime.utcnow().isoformat()
        entity['isActive'] = True

        # Try to insert entity
        table_client.create_entity(entity=entity)

        return func.HttpResponse(
            json.dumps({
                'message': 'Thank you for subscribing! You\'ll receive weekly updates.'
            }),
            status_code=200,
            headers=headers
        )

    except ResourceExistsError:
        # Email already exists
        return func.HttpResponse(
            json.dumps({
                'message': 'You\'re already subscribed!'
            }),
            status_code=200,
            headers=headers
        )

    except Exception as e:
        logging.error(f'Error: {str(e)}')
        return func.HttpResponse(
            json.dumps({
                'message': 'An error occurred. Please try again later.'
            }),
            status_code=500,
            headers=headers
        )