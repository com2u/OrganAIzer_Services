import os
import logging
import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from typing import List, Dict, Any
import base64
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

# If modifying these scopes, delete the file token.json.
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/calendar.readonly'
]

def get_credentials():
    """Gets valid user credentials from storage or initiates OAuth flow."""
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    token_path = os.path.join(os.path.dirname(__file__), '..', 'token.json')
    creds_path = os.path.join(os.path.dirname(__file__), '..', 'credentials.json')

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(creds_path):
                raise Exception("credentials.json not found. Please download it from Google Cloud Console.")
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(token_path, 'w') as token:
            token.write(creds.to_json())

    return creds

def get_gmail_service():
    """Builds and returns Gmail API service."""
    creds = get_credentials()
    return build('gmail', 'v1', credentials=creds)

def get_calendar_service():
    """Builds and returns Calendar API service."""
    creds = get_credentials()
    return build('calendar', 'v3', credentials=creds)

def read_emails(max_results: int = 10) -> List[Dict[str, Any]]:
    """Reads the latest emails from Gmail."""
    try:
        service = get_gmail_service()
        results = service.users().messages().list(userId='me', maxResults=max_results).execute()
        messages = results.get('messages', [])

        emails = []
        for msg in messages:
            msg_data = service.users().messages().get(userId='me', id=msg['id']).execute()
            email = {
                'id': msg['id'],
                'threadId': msg['threadId'],
                'labelIds': msg_data.get('labelIds', []),
                'snippet': msg_data.get('snippet', ''),
                'subject': '',
                'from': '',
                'to': '',
                'date': ''
            }
            headers = msg_data['payload']['headers']
            for header in headers:
                if header['name'] == 'Subject':
                    email['subject'] = header['value']
                elif header['name'] == 'From':
                    email['from'] = header['value']
                elif header['name'] == 'To':
                    email['to'] = header['value']
                elif header['name'] == 'Date':
                    email['date'] = header['value']
            emails.append(email)

        logger.info(f"Retrieved {len(emails)} emails")
        return emails
    except HttpError as error:
        logger.error(f'An error occurred: {error}')
        raise Exception(f'Failed to read emails: {error}')

def send_email(to: str, subject: str, body: str) -> Dict[str, Any]:
    """Sends an email via Gmail."""
    try:
        service = get_gmail_service()
        message = MIMEText(body)
        message['to'] = to
        message['subject'] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        message_body = {'raw': raw}

        sent_message = service.users().messages().send(userId='me', body=message_body).execute()
        logger.info(f'Email sent: {sent_message["id"]}')
        return sent_message
    except HttpError as error:
        logger.error(f'An error occurred: {error}')
        raise Exception(f'Failed to send email: {error}')

def read_calendar_events(max_results: int = 10) -> List[Dict[str, Any]]:
    """Reads upcoming calendar events."""
    try:
        service = get_calendar_service()
        now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
        events_result = service.events().list(calendarId='primary', timeMin=now,
                                              maxResults=max_results, singleEvents=True,
                                              orderBy='startTime').execute()
        events = events_result.get('items', [])

        calendar_events = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            calendar_events.append({
                'id': event['id'],
                'summary': event.get('summary', 'No title'),
                'start': start,
                'end': end,
                'description': event.get('description', ''),
                'location': event.get('location', '')
            })

        logger.info(f"Retrieved {len(calendar_events)} calendar events")
        return calendar_events
    except HttpError as error:
        logger.error(f'An error occurred: {error}')
        raise Exception(f'Failed to read calendar events: {error}')

# Note: For web app, OAuth flow needs to be handled differently, not with run_local_server.
# This is for local testing. For production, implement proper OAuth flow with redirect URIs.