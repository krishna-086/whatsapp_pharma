"""
NLP Service – Text-message handling via LLM intent classification.

For pure text messages (no media), this service:
  1. Classifies intent with LLM
  2. Returns the LLM's suggested reply + structured intent data

If the text looks like an invoice-session command (SHOW / OK / EDIT / CONFIRM),
the router will handle it directly before calling this service.
"""
import logging

from ai.llm_parser import LLMParser

logger = logging.getLogger(__name__)


class NLPService:
    """Service for parsing natural-language pharmacy commands."""

    def __init__(self):
        self.llm = LLMParser()

    def parse_message(self, text: str) -> dict:
        """
        Classify a text message via the LLM and return the full result.

        Returns dict with keys: intent, confidence, entities, reply.
        """
        logger.info("NLPService.parse_message: %s", text[:80])
        return self.llm.parse_intent(text)

    def generate_response(self, context: str, user_message: str) -> str:
        """
        Generate a free-form chat reply given some context.
        """
        return self.llm.generate_reply(context, user_message)
