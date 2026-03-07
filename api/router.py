"""
API Router – Central message dispatcher for the WhatsApp webhook.

Receives a parsed Twilio message dict and routes it:
  • Image  (non-audio media)  → InvoiceService.process_invoice_image()
  • Audio  (voice note)       → VoiceService  → STT → LLM intent
  • Text   (YES / NO)         → InventoryService.handle_confirmation()
  • Text   (invoice command)  → InvoiceService.handle_command()
  • Text   (free text)        → NLPService  → LLM intent → inventory or chat
"""
import logging

from messaging.twilio_service import TwilioService
from services.invoice_service import InvoiceService
from services.voice_service import VoiceService
from services.nlp_service import NLPService
from services.inventory_service import InventoryService

logger = logging.getLogger(__name__)

# Lazily initialised singletons (created on first request)
_twilio: TwilioService | None = None
_invoice: InvoiceService | None = None
_voice: VoiceService | None = None
_nlp: NLPService | None = None
_inventory: InventoryService | None = None

# Intents that the InventoryService can handle
_INVENTORY_INTENTS = {"sell_item", "add_item", "delete_item", "update_item", "query_stock", "query_expiry", "query_low_stock"}

# Greetings that trigger the welcome message
_GREETINGS = {"HI", "HELLO", "HEY", "START"}

WELCOME_MESSAGE = (
    "Welcome to Pharma AI Assistant 💊\n"
    "\n"
    "You can manage your pharmacy using WhatsApp.\n"
    "\n"
    "Dashboard:\n"
    "https://tinyurl.com/37au9f2d\n"
    "\n"
    "Available Features:\n"
    "\n"
    "📄 Supplier Invoice Extraction\n"
    "Send supplier invoice images to automatically update stock.\n"
    "\n"
    "🎤 Billing Through Voice or Text\n"
    "Example:\n"
    '"Sell 2 dolo"\n'
    "or send a voice note.\n"
    "\n"
    "📦 Inventory Queries\n"
    "Examples:\n"
    "* show stock\n"
    "* show dolo stock\n"
    "* medicines expiring soon\n"
    "* sell 2 dolo\n"
    "\n"
    "Just send a message to begin 🚀"
)


def _init_services():
    """Initialise service singletons once (cold-start)."""
    global _twilio, _invoice, _voice, _nlp, _inventory
    if _twilio is None:
        _twilio = TwilioService()
    if _invoice is None:
        _invoice = InvoiceService()
    if _voice is None:
        _voice = VoiceService()
    if _nlp is None:
        _nlp = NLPService()
    if _inventory is None:
        _inventory = InventoryService()


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

    # ── 0. Greeting → welcome message ──────────────────────────────
    if text and text.strip().upper() in _GREETINGS:
        _reply(sender, WELCOME_MESSAGE)
        return "OK"

    # ── 1. Media messages ────────────────────────────────────────────
    if num_media > 0 and media_url:

        # ── 1a. AUDIO → Voice pipeline ──────────────────────────────
        if media_type.startswith("audio/"):
            return _handle_audio(sender, media_url, media_type, text)

        # ── 1b. IMAGE (or other) → Invoice OCR ──────────────────────
        return _handle_image(sender, media_url, text)

    # ── 2. Text-only messages ────────────────────────────────────────

    # 2a. YES / NO → check for pending inventory confirmation first
    if text:
        upper = text.strip().upper()
        if upper in ("YES", "Y", "NO", "N", "CANCEL"):
            conf_reply = _inventory.handle_confirmation(sender, text)
            if conf_reply is not None:
                _reply(sender, conf_reply)
                return "OK"

    # 2b. Try invoice-session commands (SHOW / OK / EDIT / CONFIRM)
    if text:
        upper = text.strip().upper()
        if upper in ("SHOW", "OK", "CONFIRM") or upper.startswith("EDIT"):
            reply = _invoice.handle_command(sender, text)
            if reply is not None:
                _reply(sender, reply)
                return "OK"

    # 2c. General text → NLP / LLM → route to inventory or chat
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

    intent = intent_result.get("intent", "general_chat")
    entities = intent_result.get("entities", {})

    # If the voice message is actually an invoice command, handle it
    upper = transcript.strip().upper()
    if upper in ("SHOW", "OK", "CONFIRM") or upper.startswith("EDIT"):
        cmd_reply = _invoice.handle_command(sender, transcript)
        if cmd_reply:
            _reply(sender, cmd_reply)
            return "OK"

    # YES / NO confirmation via voice
    if upper in ("YES", "Y", "NO", "N", "CANCEL"):
        conf_reply = _inventory.handle_confirmation(sender, transcript)
        if conf_reply is not None:
            _reply(sender, conf_reply)
            return "OK"

    # If the voice is an inventory intent
    if intent in _INVENTORY_INTENTS:
        inv_reply = _inventory.handle_intent(sender, intent, entities)
        if inv_reply:
            _reply(sender, f'🎙 "{transcript}"\n\n{inv_reply}')
            return "OK"

    # If intent is "send_invoice", prompt for an image
    if intent == "send_invoice":
        _reply(sender, f'🎙 "{transcript}"\n\n📷 Please send the invoice image and I\'ll extract the details.')
        return "OK"

    # Otherwise relay the LLM reply
    llm_reply = intent_result.get("reply", "")
    if llm_reply:
        _reply(sender, f'🎙 "{transcript}"\n\n{llm_reply}')

    return "OK"


def _handle_text(sender: str, text: str) -> str:
    """Classify text via LLM → route to inventory service or chat."""
    logger.info("Router._handle_text for %s: %s", sender, text[:60])

    result = _nlp.parse_message(text)
    intent = result.get("intent", "general_chat")
    entities = result.get("entities", {})

    # Intent-specific shortcuts
    if intent == "send_invoice":
        _reply(sender, "📷 Please send the invoice image and I'll extract the details.")
        return "OK"

    if intent == "edit_invoice":
        cmd_reply = _invoice.handle_command(sender, text)
        if cmd_reply:
            _reply(sender, cmd_reply)
            return "OK"
        _reply(sender, result.get("reply", "No active invoice session. Please send an image first."))
        return "OK"

    # ── Inventory intents → InventoryService ────────────────────────
    if intent in _INVENTORY_INTENTS:
        inv_reply = _inventory.handle_intent(sender, intent, entities)
        if inv_reply:
            _reply(sender, inv_reply)
            return "OK"

    # Default: relay the LLM reply (general_chat)
    llm_reply = result.get("reply", "I'm here to help! Send an invoice image or ask me anything.")
    _reply(sender, llm_reply)
    return "OK"
