"""
API Router – Central message dispatcher for the WhatsApp webhook.

Receives a parsed Twilio message dict and routes it:
  • Image  (non-audio media)  → InvoiceService.process_invoice_image()
  • Audio  (voice note)       → VoiceService  → STT → LLM intent
  • Text   (invoice command)  → InvoiceService.handle_command()
  • Text   (free text)        → NLPService  → LLM intent / chat
"""
import logging

from messaging.twilio_service import TwilioService
from services.invoice_service import InvoiceService
from services.voice_service import VoiceService
from services.nlp_service import NLPService

logger = logging.getLogger(__name__)

# Lazily initialised singletons (created on first request)
_twilio: TwilioService | None = None
_invoice: InvoiceService | None = None
_voice: VoiceService | None = None
_nlp: NLPService | None = None


def _init_services():
    """Initialise service singletons once (cold-start)."""
    global _twilio, _invoice, _voice, _nlp
    if _twilio is None:
        _twilio = TwilioService()
    if _invoice is None:
        _invoice = InvoiceService()
    if _voice is None:
        _voice = VoiceService()
    if _nlp is None:
        _nlp = NLPService()


def _reply(sender: str, text: str):
    """Convenience: send a WhatsApp message back to the sender."""
    _twilio.send_message(sender, text)


# ------------------------------------------------------------------
#  Main entry point
# ------------------------------------------------------------------

def route_message(message: dict) -> str:
    """
    Route a single incoming WhatsApp message.

    Parameters
    ----------
    message : dict
        Output of ``TwilioService.parse_incoming_message()``.
        Keys: from, body, num_media, media_url, media_type.

    Returns
    -------
    str   "OK" on success (Twilio expects a 200 with any body).
    """
    _init_services()

    sender = message["from"]             # e.g. "whatsapp:+91..."
    text = message["body"]
    num_media = message["num_media"]
    media_url = message["media_url"]
    media_type = message["media_type"]    # e.g. "image/jpeg", "audio/ogg"

    logger.info("Router: sender=%s  text=%s  media=%d  type=%s",
                sender, text[:60] if text else "", num_media, media_type)

    # ── 1. Media messages ────────────────────────────────────────────
    if num_media > 0 and media_url:

        # ── 1a. AUDIO → Voice pipeline ──────────────────────────────
        if media_type.startswith("audio/"):
            return _handle_audio(sender, media_url, media_type, text)

        # ── 1b. IMAGE (or other) → Invoice OCR ──────────────────────
        return _handle_image(sender, media_url, text)

    # ── 2. Text-only messages ────────────────────────────────────────

    # 2a. Try invoice-session commands first (SHOW / OK / EDIT / CONFIRM)
    if text:
        upper = text.strip().upper()
        if upper in ("SHOW", "OK", "CONFIRM") or upper.startswith("EDIT"):
            reply = _invoice.handle_command(sender, text)
            if reply is not None:
                _reply(sender, reply)
                return "OK"

    # 2b. General text → NLP / LLM
    if text:
        return _handle_text(sender, text)

    # 2c. Empty message (edge case)
    _reply(sender, "Please send an invoice image, a voice note, or a text message.")
    return "OK"


# ------------------------------------------------------------------
#  Sub-handlers
# ------------------------------------------------------------------

def _handle_image(sender: str, media_url: str, text: str) -> str:
    """Download image → run invoice OCR → reply with extracted data."""
    logger.info("Router._handle_image for %s", sender)

    image_bytes = _twilio.download_media(media_url)
    invoice, flags = _invoice.process_invoice_image(image_bytes, sender)
    reply_text = _invoice.render(invoice, flags)
    _reply(sender, reply_text)
    return "OK"


def _handle_audio(sender: str, media_url: str, content_type: str, text: str) -> str:
    """Download audio → transcribe → classify intent → reply."""
    logger.info("Router._handle_audio for %s", sender)

    transcript, intent_result = _voice.process_voice_message(media_url, content_type, sender)

    if not transcript:
        _reply(sender, intent_result.get("reply", "Could not transcribe audio."))
        return "OK"

    # Echo the transcription
    _reply(sender, f'🎙 Voice transcription:\n"{transcript}"')

    intent = intent_result.get("intent", "general_chat")

    # If the voice message is actually an invoice command, handle it
    upper = transcript.strip().upper()
    if upper in ("SHOW", "OK", "CONFIRM") or upper.startswith("EDIT"):
        cmd_reply = _invoice.handle_command(sender, transcript)
        if cmd_reply:
            _reply(sender, cmd_reply)
            return "OK"

    # If intent is "send_invoice", prompt for an image
    if intent == "send_invoice":
        _reply(sender, "📷 Please send the invoice image and I'll extract the details.")
        return "OK"

    # Otherwise relay the LLM reply
    llm_reply = intent_result.get("reply", "")
    if llm_reply:
        _reply(sender, llm_reply)

    return "OK"


def _handle_text(sender: str, text: str) -> str:
    """Classify text via LLM → reply."""
    logger.info("Router._handle_text for %s: %s", sender, text[:60])

    result = _nlp.parse_message(text)
    intent = result.get("intent", "general_chat")

    # Intent-specific shortcuts
    if intent == "send_invoice":
        _reply(sender, "📷 Please send the invoice image and I'll extract the details.")
        return "OK"

    if intent == "edit_invoice":
        # The user might be describing an edit in natural language
        cmd_reply = _invoice.handle_command(sender, text)
        if cmd_reply:
            _reply(sender, cmd_reply)
            return "OK"
        # If no active session, let LLM reply handle it
        _reply(sender, result.get("reply", "No active invoice session. Please send an image first."))
        return "OK"

    # Default: relay the LLM reply
    llm_reply = result.get("reply", "I'm here to help! Send an invoice image or ask me anything.")
    _reply(sender, llm_reply)
    return "OK"
