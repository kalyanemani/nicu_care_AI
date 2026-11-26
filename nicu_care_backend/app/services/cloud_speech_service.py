"""
Google Cloud Speech & Text-to-Speech (STT / TTS) Integration Service.
Provides high-fidelity multilingual pediatric voice synthesis and transcription for:
- Telugu (te-IN)
- Hindi (hi-IN)
- Tamil (ta-IN)
- English (en-US / en-IN)

Operates within the GCP Free Tier (4 million characters TTS/month, 60 minutes STT/month).
Gracefully falls back when GCP credentials or packages are not active.
"""

import os
import base64
import logging
from typing import Optional, Tuple

logger = logging.getLogger("cloud_speech_service")

# Check if google-cloud-texttospeech and google-cloud-speech are installed
TTS_AVAILABLE = False
STT_AVAILABLE = False
try:
    from google.cloud import texttospeech
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

try:
    from google.cloud import speech
    STT_AVAILABLE = True
except ImportError:
    STT_AVAILABLE = False


class CloudSpeechService:
    """Manages GCP Speech-to-Text and Text-to-Speech operations."""

    VOICE_MAP = {
        "te-IN": {"language_code": "te-IN", "name": "te-IN-Standard-A"},
        "hi-IN": {"language_code": "hi-IN", "name": "hi-IN-Neural2-A"},
        "ta-IN": {"language_code": "ta-IN", "name": "ta-IN-Standard-A"},
        "en-US": {"language_code": "en-US", "name": "en-US-Journey-F"},
        "en-IN": {"language_code": "en-IN", "name": "en-IN-Standard-A"},
    }

    def __init__(self):
        self._tts_client = None
        self._stt_client = None
        self._init_clients()

    def _init_clients(self):
        if TTS_AVAILABLE:
            try:
                self._tts_client = texttospeech.TextToSpeechClient()
                logger.info("Cloud Text-to-Speech client initialized.")
            except Exception as e:
                logger.info(f"Cloud TTS offline ({e}), using client-side Web Speech.")
                self._tts_client = None

        if STT_AVAILABLE:
            try:
                self._stt_client = speech.SpeechClient()
                logger.info("Cloud Speech-to-Text client initialized.")
            except Exception as e:
                logger.info(f"Cloud STT offline ({e}), using client-side Web Speech.")
                self._stt_client = None

    @property
    def is_tts_available(self) -> bool:
        return self._tts_client is not None

    @property
    def is_stt_available(self) -> bool:
        return self._stt_client is not None

    def synthesize_speech(self, text: str, target_lang: str = "en-US") -> Optional[str]:
        """
        Synthesizes text into base64-encoded MP3 audio using Cloud Text-to-Speech.
        Returns None if client is unavailable or text is empty.
        """
        if not self.is_tts_available or not text or not text.strip():
            return None

        # Short clean text (first sentence or max 250 chars) for prompt voice reply
        clean_text = text.strip()[:300]
        voice_config = self.VOICE_MAP.get(target_lang, self.VOICE_MAP["en-US"])

        try:
            s_input = texttospeech.SynthesisInput(text=clean_text)
            voice = texttospeech.VoiceSelectionParams(
                language_code=voice_config["language_code"],
                name=voice_config["name"]
            )
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=0.95,  # Gentle, calm pace for maternal reassurance
                pitch=0.0
            )

            response = self._tts_client.synthesize_speech(
                input=s_input,
                voice=voice,
                audio_config=audio_config
            )

            if response.audio_content:
                return base64.b64encode(response.audio_content).decode("utf-8")
        except Exception as e:
            logger.warning(f"Cloud TTS synthesis failed: {e}")

        return None

    def transcribe_audio(self, audio_bytes: bytes, target_lang: str = "en-US") -> Optional[str]:
        """
        Transcribes speech audio into text using Cloud Speech-to-Text.
        """
        if not self.is_stt_available or not audio_bytes:
            return None

        lang_code = self.VOICE_MAP.get(target_lang, {}).get("language_code", "en-US")

        try:
            audio = speech.RecognitionAudio(content=audio_bytes)
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                language_code=lang_code,
                enable_automatic_punctuation=True,
            )

            response = self._stt_client.recognize(config=config, audio=audio)
            transcripts = [res.alternatives[0].transcript for res in response.results if res.alternatives]
            if transcripts:
                return " ".join(transcripts)
        except Exception as e:
            logger.warning(f"Cloud STT transcription failed: {e}")

        return None


# Global singleton
cloud_speech_service = CloudSpeechService()
