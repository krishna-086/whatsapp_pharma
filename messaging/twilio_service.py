"""
Twilio Service - WhatsApp messaging via Twilio API.

Provides:
  - parse_twilio_form()   – decode URL-encoded webhook body
  - download_media()      – fetch media bytes from Twilio CDN
  - send_message()        – send a text reply
  - send_media()          – send a media reply
"""
import logging
import os
from urllib.parse import parse_qs

import requests
from twilio.rest import Client
import azure.functions as func

logger = logging.getLogger(__name__)


class TwilioService:
    """Wrapper for Twilio WhatsApp messaging operations."""

    def __init__(self):
        self.account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        self.auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        self.whatsapp_from = os.environ.get("TWILIO_WHATSAPP_FROM", "")
        self._client = None

    def get_client(self) -> Client:
        if self._client is None:
            self._client = Client(self.account_sid, self.auth_token)
        return self._client

    # ------------------------------------------------------------------
    #  Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def parse_twilio_form(req: func.HttpRequest) -> dict:
        """Parse Twilio's URL-encoded POST body into a flat dict."""
        body = req.get_body().decode("utf-8", errors="ignore")
        data = parse_qs(body)
        return {k: v[0] for k, v in data.items()}

    @staticmethod
    def parse_incoming_message(data: dict) -> dict:
        """Normalise parsed form data into a clean message dict."""
        return {
            "from": data.get("From", ""),
            "body": (data.get("Body") or "").strip(),
            "num_media": int(data.get("NumMedia") or "0"),
            "media_url": data.get("MediaUrl0", ""),
            "media_type": (data.get("MediaContentType0") or "").lower(),
        }

    # ------------------------------------------------------------------
    #  Media download
    # ------------------------------------------------------------------

    def download_media(self, media_url: str) -> bytes:
        """Download media bytes from a Twilio media URL (image/audio)."""
        resp = requests.get(
            media_url,
            auth=(self.account_sid, self.auth_token),
            timeout=30,
        )
        resp.raise_for_status()
        return resp.content

    # ------------------------------------------------------------------
    #  Sending
    # ------------------------------------------------------------------

    def send_message(self, to: str, body: str):
        """Send a WhatsApp text message. *to* should include 'whatsapp:' prefix."""
        logger.info("Sending WhatsApp message to %s", to)
        client = self.get_client()
        message = client.messages.create(
            from_=self.whatsapp_from,
            body=body,
            to=to,
        )
        return {"sid": message.sid, "status": message.status}

    def send_media(self, to: str, media_url: str, body: str = ""):
        """Send a WhatsApp message with a media attachment."""
        logger.info("Sending WhatsApp media to %s", to)
        client = self.get_client()
        message = client.messages.create(
            from_=self.whatsapp_from,
            body=body,
            media_url=[media_url],
            to=to,
        )
        return {"sid": message.sid, "status": message.status}
