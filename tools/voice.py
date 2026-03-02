"""
GEDOS Voice — local transcription of Telegram voice messages using Whisper.
"""

import logging
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
