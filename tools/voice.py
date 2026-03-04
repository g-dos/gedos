"""
GEDOS Voice — local transcription of Telegram voice messages using Whisper.
"""

import logging
from io import BytesIO
from pathlib import Path
from typing import Optional, Union

logger = logging.getLogger(__name__)

_WHISPER_NOT_INSTALLED_MSG = (
    "Whisper is not installed. To enable voice input, run:\n"
    "pip install openai-whisper\n\n"
    "Note: FFmpeg must also be installed (e.g. brew install ffmpeg on macOS)."
)


def transcribe_audio(audio_path: Union[str, Path], language_hint: Optional[str] = None) -> tuple[str, Optional[str]]:
    """
    Transcribe an audio file using local OpenAI Whisper.

    Args:
        audio_path: Path to the audio file (supports .ogg, .mp3, .wav, etc.)

    Returns:
        Tuple of (transcribed_text, error_message).
        If successful: (text, None).
        If failed: ("", error_message).
    """
    try:
        import whisper
    except ImportError:
        logger.warning("openai-whisper not installed")
        return ("", _WHISPER_NOT_INSTALLED_MSG)

    audio_path = Path(audio_path)
    if not audio_path.exists():
        return ("", f"Audio file not found: {audio_path}")

    try:
        model = whisper.load_model("base")
        kwargs = {"fp16": False}
        if language_hint:
            kwargs["language"] = language_hint
        result = model.transcribe(str(audio_path), **kwargs)
        text = (result.get("text") or "").strip()
        if not text:
            return ("", "Transcription returned empty text. Try speaking more clearly.")
        return (text, None)
    except Exception as e:
        logger.exception("Whisper transcription failed")
        error_msg = str(e)
        if "ffmpeg" in error_msg.lower() or "not found" in error_msg.lower():
            return ("", "FFmpeg not found. Install it: brew install ffmpeg (macOS)")
        return ("", f"Transcription failed: {error_msg[:200]}")


def synthesize_speech(text: str, language: str) -> Optional[bytes]:
    """
    Synthesize Telegram-compatible voice output using gTTS + pydub.

    Args:
        text: Text to convert into speech.
        language: Language code accepted by gTTS (e.g. en, pt, es).

    Returns:
        OGG audio bytes on success, otherwise None.
    """
    if not text or not text.strip():
        return None

    try:
        from gtts import gTTS
        from pydub import AudioSegment
    except ImportError:
        logger.warning("Voice output dependencies not installed")
        return None

    normalized_language = (language or "en").strip().lower()[:2] or "en"
    mp3_buffer = BytesIO()
    ogg_buffer = BytesIO()

    try:
        gTTS(text=text.strip(), lang=normalized_language).write_to_fp(mp3_buffer)
        mp3_buffer.seek(0)
        audio = AudioSegment.from_file(mp3_buffer, format="mp3")
        audio.export(ogg_buffer, format="ogg", codec="libopus")
        return ogg_buffer.getvalue()
    except Exception:
        logger.exception("Voice synthesis failed")
        return None
