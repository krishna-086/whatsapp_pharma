"""
LLM Parser – Azure OpenAI integration for intent classification & chat.

Capabilities:
  - parse_intent()         → classify user message into an action
  - extract_medicine_info() → pull structured medicine data from text
  - generate_reply()       → general chat completion
"""
import json
import logging
import os

from openai import AzureOpenAI

logger = logging.getLogger(__name__)

# System prompt that defines the pharmacy assistant persona
SYSTEM_PROMPT = """\
You are PharmaBot, an AI pharmacy inventory assistant on WhatsApp.
You help pharmacists manage invoices, inventory, and medicine information.

When the user sends a message, classify their INTENT as exactly one of:
  • "send_invoice"   – they want to scan/upload an invoice image
  • "edit_invoice"   – they want to edit fields on an invoice (EDIT / OK / SHOW / CONFIRM)
  • "sell_item"      – they sold / dispensed medicine and want to record the sale
                        (e.g. "sold 2 of belladonna", "dispensed 5 paracetamol")
  • "add_item"       – they want to add stock / restock an item
                        (e.g. "add 50 belladonna at 120", "received 100 aspirin")
  • "delete_item"    – they want to remove an item from inventory
  • "update_item"    – they want to update/change a field on an existing inventory item
                        (e.g. "update mrp of belladonna to 170", "change price of aspirin to 50")
  • "query_stock"    – they want to check stock / availability / price
  • "general_chat"   – general greeting, question, or anything else

Extract entities whenever possible:
  • name / medicine_name – the item name (e.g. "Belladonna 30C")
  • quantity / qty – numeric quantity
  • mrp / price – maximum retail price (MRP). Always map any price to "mrp".
  • batch_no – batch/lot number
  • expiry_date – expiry date

IMPORTANT – Multi-item requests:
When the user mentions MULTIPLE items in a single message (e.g. "sold 2 belladonna and 1 aspirin"),
return an "items" array inside "entities":

Respond ONLY with a valid JSON object. Examples:

Multi-item:
{
  "intent": "sell_item",
  "confidence": 0.95,
  "entities": {
    "items": [
      {"name": "Belladonna 30", "quantity": 2},
      {"name": "Aspirin", "quantity": 1}
    ]
  },
  "reply": "..."
}

For SINGLE-item requests:
{
  "intent": "<one of the intents above>",
  "confidence": <0.0-1.0>,
  "entities": {
    "name": "<item name if mentioned>",
    "quantity": <number or null>,
    "mrp": <number or null>,
    "batch_no": "<string or null>",
    "expiry_date": "<string or null>"
  },
  "reply": "<short, friendly WhatsApp reply to the user>"
}
"""


class LLMParser:
    """Azure OpenAI wrapper for intent parsing & conversational replies."""

    def __init__(self):
        self.endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
        self.api_key = os.environ.get("AZURE_OPENAI_KEY", "")
        self.deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1")
        self.api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
        self._client = None

    def _get_client(self) -> AzureOpenAI:
        if self._client is None:
            self._client = AzureOpenAI(
                azure_endpoint=self.endpoint,
                api_key=self.api_key,
                api_version=self.api_version,
            )
        return self._client

    # ------------------------------------------------------------------
    #  Intent classification
    # ------------------------------------------------------------------

    def parse_intent(self, text: str) -> dict:
        """
        Classify the user's message into an intent + entities + reply.

        Returns dict with keys: intent, confidence, entities, reply.
        """
        logger.info("LLM parse_intent: %s", text[:80])
        client = self._get_client()

        response = client.chat.completions.create(
            model=self.deployment,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0.1,
            max_tokens=512,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content or "{}"
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("LLM returned non-JSON: %s", raw)
            result = {
                "intent": "general_chat",
                "confidence": 0.5,
                "entities": {},
                "reply": raw,
            }

        # Ensure all expected keys exist
        result.setdefault("intent", "general_chat")
        result.setdefault("confidence", 0.5)
        result.setdefault("entities", {})
        result.setdefault("reply", "")
        return result

    # ------------------------------------------------------------------
    #  Structured medicine extraction
    # ------------------------------------------------------------------

    def extract_medicine_info(self, text: str) -> dict:
        """
        Extract structured medicine names, quantities, dosage from text.
        """
        logger.info("LLM extract_medicine_info")
        client = self._get_client()

        extraction_prompt = (
            "Extract all medicine names, quantities, and dosage from the following text. "
            "Return JSON: {\"medicines\": [{\"name\": ..., \"quantity\": ..., \"dosage\": ...}]}\n\n"
            f"Text: {text}"
        )
        response = client.chat.completions.create(
            model=self.deployment,
            messages=[
                {"role": "system", "content": "You are a pharmacy data extraction assistant. Return JSON only."},
                {"role": "user", "content": extraction_prompt},
            ],
            temperature=0.0,
            max_tokens=1024,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content or "{}"
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"medicines": []}

    # ------------------------------------------------------------------
    #  General chat completion
    # ------------------------------------------------------------------

    def generate_reply(self, context: str, user_message: str) -> str:
        """
        Generate a free-form contextual reply (not intent-classified).
        Useful when the caller already knows the intent and just needs a
        human-friendly answer.
        """
        logger.info("LLM generate_reply")
        client = self._get_client()

        response = client.chat.completions.create(
            model=self.deployment,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are PharmaBot, a helpful WhatsApp pharmacy assistant. "
                        "Keep replies concise and friendly. "
                        f"Context: {context}"
                    ),
                },
                {"role": "user", "content": user_message},
            ],
            temperature=0.7,
            max_tokens=512,
        )

        return (response.choices[0].message.content or "").strip()
