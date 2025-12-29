import os
import logging
from msgraph import GraphServiceClient
from azure.identity import DeviceCodeCredential, ClientSecretCredential
from msgraph.generated.models.message import Message
from msgraph.generated.models.item_body import ItemBody
from msgraph.generated.models.body_type import BodyType
from msgraph.generated.models.recipient import Recipient
from msgraph.generated.models.email_address import EmailAddress
from msgraph.generated.users.item.send_mail.send_mail_post_request_body import SendMailPostRequestBody
from typing import List, Dict, Any
import asyncio

logger = logging.getLogger(__name__)

# Scopes for Microsoft Graph
SCOPES_DEVICE = [
    'https://graph.microsoft.com/Mail.ReadWrite',
    'https://graph.microsoft.com/Mail.Send',
    'https://graph.microsoft.com/Calendars.Read'
]

SCOPES_CLIENT = [
    'https://graph.microsoft.com/.default'
]

# Global client to persist authentication
_graph_client = None
_cache = None
_device_code_info = None

def get_graph_client():
    """Gets authenticated Microsoft Graph client."""
    global _graph_client, _cache
    if _graph_client is not None:
        return _graph_client

    client_id = os.getenv('AZURE_CLIENT_ID')
    tenant_id = os.getenv('AZURE_TENANT_ID')

    if not client_id or not tenant_id:
        raise Exception("AZURE_CLIENT_ID and AZURE_TENANT_ID environment variables must be set")

    # Use persistent cache for token storage
    from azure.identity import DeviceCodeCredential
    import atexit
    from msal import SerializableTokenCache
    import json

    cache_file = os.path.join(os.path.dirname(__file__), '..', '..', 'token_cache.json')

    class PersistentTokenCache(SerializableTokenCache):
        def __init__(self, cache_file):
            super().__init__()
            self.cache_file = cache_file
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r') as f:
                        self.deserialize(json.load(f))
                    logger.info(f"Token cache loaded from {cache_file}")
                except Exception as e:
                    logger.warning(f"Failed to load token cache: {e}")
            else:
                logger.info("No existing token cache found")

        def add(self, event, **kwargs):
            super().add(event, **kwargs)
            self._save()

        def _save(self):
            try:
                with open(self.cache_file, 'w') as f:
                    json.dump(self.serialize(), f)
                logger.info(f"Token cache saved to {self.cache_file}")
            except Exception as e:
                logger.error(f"Failed to save token cache: {e}")

    _cache = PersistentTokenCache(cache_file)

    def device_code_callback(info):
        global _device_code_info
        _device_code_info = info
        logger.info(f"Device code: {info['user_code']}, URL: {info['verification_uri']}")

    credential = DeviceCodeCredential(
        client_id=client_id,
        tenant_id=tenant_id,
        cache=_cache,
        device_code_callback=device_code_callback
    )
    scopes = SCOPES_DEVICE

    _graph_client = GraphServiceClient(credentials=credential, scopes=scopes)
    return _graph_client

async def read_emails(max_results: int = 10) -> List[Dict[str, Any]]:
    """Reads the latest emails from Outlook."""
    try:
        client = get_graph_client()
        messages = await client.me.messages.get()
        if messages and messages.value:
            emails = []
            for msg in messages.value[:max_results]:
                email = {
                    'id': msg.id,
                    'subject': msg.subject,
                    'from': msg.from_.email_address.address if msg.from_ else None,
                    'to': [recipient.email_address.address for recipient in msg.to_recipients] if msg.to_recipients else [],
                    'received_date_time': msg.received_date_time.isoformat() if msg.received_date_time else None,
                    'body_preview': msg.body_preview,
                    'is_read': msg.is_read
                }
                emails.append(email)
            logger.info(f"Retrieved {len(emails)} emails")
            # Force save cache if updated
            global _cache
            if _cache and _cache.has_state_changed:
                _cache._save()
            return emails
        return []
    except Exception as e:
        logger.error(f'An error occurred: {e}')
        raise Exception(f'Failed to read emails: {e}')

async def send_email(to: str, subject: str, body: str) -> Dict[str, Any]:
    """Sends an email via Outlook."""
    try:
        client = get_graph_client()

        # Create message
        message = Message()
        message.subject = subject

        # Set body
        message.body = ItemBody()
        message.body.content_type = BodyType.Text
        message.body.content = body

        # Set recipient
        recipient = Recipient()
        recipient.email_address = EmailAddress()
        recipient.email_address.address = to
        message.to_recipients = [recipient]

        # Send the message
        request_body = SendMailPostRequestBody()
        request_body.message = message
        request_body.save_to_sent_items = True
        sent_message = await client.me.send_mail.post(request_body)

        logger.info('Email sent successfully')
        # Force save cache if updated
        global _cache
        if _cache and _cache.has_state_changed:
            _cache._save()
        return {"message": "Email sent successfully"}
    except Exception as e:
        logger.error(f'An error occurred: {e}')
        raise Exception(f'Failed to send email: {e}')

async def read_calendar_events(max_results: int = 10) -> List[Dict[str, Any]]:
    """Reads upcoming calendar events from Outlook."""
    try:
        client = get_graph_client()
        events = await client.me.events.get()
        if events and events.value:
            calendar_events = []
            for event in events.value[:max_results]:
                calendar_event = {
                    'id': event.id,
                    'subject': event.subject,
                    'start': event.start.date_time if event.start else None,
                    'end': event.end.date_time if event.end else None,
                    'location': event.location.display_name if event.location else None,
                    'body_preview': event.body_preview
                }
                calendar_events.append(calendar_event)
            logger.info(f"Retrieved {len(calendar_events)} calendar events")
            # Force save cache if updated
            global _cache
            if _cache and _cache.has_state_changed:
                _cache._save()
            return calendar_events
        return []
    except Exception as e:
        logger.error(f'An error occurred: {e}')
        raise Exception(f'Failed to read calendar events: {e}')

def get_device_code_info():
    """Get the current device code information."""
    global _device_code_info
    return _device_code_info
