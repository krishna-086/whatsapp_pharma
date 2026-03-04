"""
Azure Functions entry point – WhatsApp webhook for PharmaBot.

This file is deliberately thin.  All logic lives in api/router.py
and the service / AI modules it dispatches to.
"""
import logging

import azure.functions as func

from messaging.twilio_service import TwilioService
from api.router import route_message

app = func.FunctionApp()
logger = logging.getLogger(__name__)


@app.route(route="whatsapp_webhook", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def whatsapp_webhook(req: func.HttpRequest) -> func.HttpResponse:
    """Twilio WhatsApp webhook – POST with URL-encoded form body."""
    try:
        # 1. Parse the raw Twilio form data
        twilio = TwilioService()
        data = twilio.parse_twilio_form(req)
        message = twilio.parse_incoming_message(data)

        logger.info("Webhook received: sender=%s  media=%d  type=%s  body=%s",
                     message["from"], message["num_media"],
                     message["media_type"], (message["body"] or "")[:60])

        # 2. Route to the correct service
        route_message(message)

        # 3. Twilio expects a 200 OK (we already replied via REST API)
        return func.HttpResponse("OK", status_code=200)

    except Exception as exc:
        logging.exception("Webhook error")
        return func.HttpResponse(f"Error: {exc}", status_code=500)