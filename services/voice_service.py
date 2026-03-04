"""
Voice Service – Download audio → upload to Blob → transcribe → classify intent.

Pipeline:
  1. Download audio bytes from Twilio media URL
  2. Upload to Azure Blob Storage (same pattern as invoice images)
  3. Transcribe with Azure Speech REST API (server-side OGG decode)
  4. Send transcript to LLM for intent classification
  5. Return (transcript, intent_result)
"""
import logging

from ai.speech_to_text import SpeechToText
from ai.llm_parser import LLMParser
from messaging.twilio_service import TwilioService
from storage.blob_storage import BlobStorage

logger = logging.getLogger(__name__)


def _ext_from_mime(content_type: str) -> str:
    """Derive a file extension from a MIME type."""
    ct = (content_type or "").lower()
    if "ogg" in ct:
        return "ogg"
    if "mp3" in ct or "mpeg" in ct:
        return "mp3"
    if "mp4" in ct or "m4a" in ct:
        return "m4a"
    if "wav" in ct:
        return "wav"
    return "bin"


class VoiceService:
    """Orchestrator for voice-message handling."""

    def __init__(self):
        self.stt = SpeechToText()
        self.llm = LLMParser()
        self.twilio = TwilioService()
        self.blob = BlobStorage()

    def process_voice_message(
        self,
        media_url: str,
        content_type: str = "audio/ogg",
        sender: str = "",
    ) -> tuple[str, dict]:
        """
        Full voice pipeline.

        Returns
        -------
        (transcript, intent_result)
            transcript : str – the raw speech-to-text output
            intent_result : dict – LLM intent classification (intent, confidence, entities, reply)
        """
        # 1. Download from Twilio
        logger.info("VoiceService: downloading audio from %s", media_url)
        audio_bytes = self.twilio.download_media(media_url)

        # 2. Upload to Blob Storage (mirrors invoice image pattern)
        ext = _ext_from_mime(content_type)
        blob_url = self.blob.upload_voice_note(audio_bytes, sender, ext)
        logger.info("VoiceService: voice note saved to blob: %s", blob_url)

        # 3. Transcribe via REST API (no GStreamer needed)
        logger.info("VoiceService: transcribing %d bytes (%s)", len(audio_bytes), content_type)
        transcript = self.stt.transcribe(audio_bytes, content_type)

        if not transcript:
            logger.warning("VoiceService: empty transcription")
            return "", {
                "intent": "unknown",
                "confidence": 0.0,
                "entities": {},
                "reply": (
                    "Sorry, I couldn't understand the voice message. "
                    "Please try again or type your message."
                ),
            }

        logger.info("VoiceService: classifying transcript via LLM")
        intent_result = self.llm.parse_intent(transcript)
        return transcript, intent_result
