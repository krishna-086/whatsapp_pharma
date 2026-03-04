"""
Speech to Text – Azure Cognitive Services Speech SDK integration.

Ported from legacy_reference/function_app.py transcribe_audio().
Uses PushAudioInputStream + continuous recognition so it handles
voice messages of any length and format (OGG_OPUS, MP3, MP4, WAV).
"""
import logging
import os
import threading

import azure.cognitiveservices.speech as speechsdk

logger = logging.getLogger(__name__)


class SpeechToText:
    """Wrapper for Azure Speech-to-Text operations."""

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
        Transcribe raw audio bytes to text.

        Parameters
        ----------
        audio_bytes : bytes
            The raw audio payload (OGG, MP3, MP4, WAV, etc.).
        content_type : str
            MIME type of the audio (e.g. ``audio/ogg``, ``audio/mpeg``).
        language : str
            BCP-47 language code, default ``en-US``.

        Returns
        -------
        str
            Transcribed text (may be empty on failure).
        """
        logger.info("SpeechToText.transcribe  content_type=%s  bytes=%d",
                     content_type, len(audio_bytes))

        speech_config = speechsdk.SpeechConfig(
            subscription=self.speech_key,
            region=self.speech_region,
        )
        speech_config.speech_recognition_language = language

        # Map MIME type → SDK compressed-stream container format
        container_format = self._mime_to_container_format(content_type)

        if container_format is not None:
            compressed_fmt = speechsdk.audio.AudioStreamFormat(
                compressed_stream_format=container_format
            )
            push_stream = speechsdk.audio.PushAudioInputStream(
                stream_format=compressed_fmt
            )
        else:
            # Plain WAV – use default PCM stream
            push_stream = speechsdk.audio.PushAudioInputStream()

        push_stream.write(audio_bytes)
        push_stream.close()

        audio_config = speechsdk.audio.AudioConfig(stream=push_stream)
        recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config,
            audio_config=audio_config,
        )

        # Continuous recognition collects all utterances
        done = threading.Event()
        all_results: list[str] = []

        def recognized_cb(evt):
            if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                all_results.append(evt.result.text)

        def session_stopped_cb(_evt):
            done.set()

        def canceled_cb(evt):
            details = evt.result.cancellation_details
            logger.warning("Speech recognition canceled: %s / %s",
                           details.reason, details.error_details)
            done.set()

        recognizer.recognized.connect(recognized_cb)
        recognizer.session_stopped.connect(session_stopped_cb)
        recognizer.canceled.connect(canceled_cb)

        recognizer.start_continuous_recognition()
        done.wait(timeout=120)
        recognizer.stop_continuous_recognition()

        transcript = " ".join(all_results) if all_results else ""
        logger.info("Transcription result (%d chars): %s",
                     len(transcript), transcript[:120])
        return transcript

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _mime_to_container_format(content_type: str):
        """Map a MIME type to an ``AudioStreamContainerFormat`` enum, or None for WAV."""
        ct = (content_type or "").lower()
        if "ogg" in ct:
            return speechsdk.AudioStreamContainerFormat.OGG_OPUS
        if "mp3" in ct or "mpeg" in ct:
            return speechsdk.AudioStreamContainerFormat.MP3
        if "mp4" in ct or "m4a" in ct:
            return speechsdk.AudioStreamContainerFormat.MP4
        if "wav" in ct:
            return None  # WAV is native PCM, no container needed
        return speechsdk.AudioStreamContainerFormat.ANY
