"""
Speech to Text – Azure Speech REST API integration.

Uses the Speech-to-Text REST API for short audio instead of the SDK.
The REST endpoint handles OGG/OPUS/MP3 decoding **server-side**, so
there is no need for GStreamer on the host machine.

Endpoint:
  POST https://{region}.stt.speech.microsoft.com/speech/recognition/
       conversation/cognitiveservices/v1?language={lang}
Headers:
  Ocp-Apim-Subscription-Key : {key}
  Content-Type              : audio/ogg; codecs=opus  (or other MIME)
Body:
  Raw audio bytes

Limitation: the REST “short audio” endpoint supports up to ~60 s.
WhatsApp voice notes are almost always < 60 s.
"""
import logging
import os

import requests

logger = logging.getLogger(__name__)

# Mapping from Twilio MIME types → Content-Type header the REST API expects
_MIME_MAP = {
    "audio/ogg": "audio/ogg; codecs=opus",
    "audio/ogg; codecs=opus": "audio/ogg; codecs=opus",
    "audio/mpeg": "audio/mpeg",
    "audio/mp3": "audio/mpeg",
    "audio/mp4": "audio/mp4",
    "audio/wav": "audio/wav",
    "audio/x-wav": "audio/wav",
}


class SpeechToText:
    """Azure Speech-to-Text via REST API (no SDK / no GStreamer)."""

    def __init__(self):
        self.speech_key = os.environ.get("AZURE_SPEECH_KEY", "")
        self.speech_region = os.environ.get("AZURE_SPEECH_REGION", "")

    # ------------------------------------------------------------------
    #  Core transcription
    # ------------------------------------------------------------------

    def transcribe(
        self,
        audio_bytes: bytes,
        content_type: str = "audio/ogg",
        language: str = "en-US",
    ) -> str:
        """
        Transcribe raw audio bytes to text via the Speech REST API.

        Parameters
        ----------
        audio_bytes : bytes
            Raw audio payload (OGG, MP3, WAV, etc.).
        content_type : str
            MIME type of the audio.
        language : str
            BCP-47 language code, default ``en-US``.

        Returns
        -------
        str   Transcribed text (empty string on failure).
        """
        logger.info(
            "SpeechToText.transcribe  content_type=%s  bytes=%d  lang=%s",
            content_type, len(audio_bytes), language,
        )

        url = (
            f"https://{self.speech_region}.stt.speech.microsoft.com/"
            f"speech/recognition/conversation/cognitiveservices/v1"
            f"?language={language}&format=detailed"
        )

        ct_header = _MIME_MAP.get(content_type.lower(), content_type)

        headers = {
            "Ocp-Apim-Subscription-Key": self.speech_key,
            "Content-Type": ct_header,
            "Accept": "application/json",
        }

        try:
            resp = requests.post(url, headers=headers, data=audio_bytes, timeout=60)
            resp.raise_for_status()
            result = resp.json()
        except requests.RequestException as exc:
            logger.error("Speech REST API error: %s", exc)
            return ""

        status = result.get("RecognitionStatus", "")
        if status == "Success":
            # "detailed" format returns NBest[]; pick the top result
            nbest = result.get("NBest", [])
            if nbest:
                transcript = nbest[0].get("Display", "")
            else:
                transcript = result.get("DisplayText", "")
            logger.info("Transcription (%d chars): %s", len(transcript), transcript[:120])
            return transcript

        logger.warning("Recognition status: %s  body=%s", status, result)
        return ""
