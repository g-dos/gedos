"""
Kokoro TTS wrapper for Gedos (local, offline, high-quality voice synthesis).

Requirements:
    pip install kokoro soundfile numpy

This module is optional. If Kokoro or related dependencies are unavailable,
all public functions fail gracefully and return safe fallbacks.
"""

from __future__ import annotations

import logging
from io import BytesIO
from typing import Optional

try:
    import kokoro

    KOKORO_AVAILABLE = True
except Exception:
    kokoro = None  # type: ignore[assignment]
    KOKORO_AVAILABLE = False

logger = logging.getLogger(__name__)

KOKORO_VOICE_MAP = {
    "pt": "bf_emma",   # best available for Portuguese
    "en": "af_heart",  # default English voice
    "es": "ef_dora",   # Spanish
}
DEFAULT_VOICE = "af_heart"
DEFAULT_LANG_CODE = "a"  # Kokoro lang code for English/default

_LANG_CODE_MAP = {
    "en": "a",
    "pt": "a",
    "es": "e",
}


def kokoro_available() -> bool:
    """Return whether Kokoro is available in the current runtime."""
    return KOKORO_AVAILABLE


def _as_audio_array(chunk) -> Optional["object"]:
    """Best-effort extraction of the audio sample array from generator chunks."""
    if chunk is None:
        return None

    try:
        import numpy as np
    except Exception:
        return None

    if isinstance(chunk, np.ndarray):
        return chunk

    if isinstance(chunk, (tuple, list)):
        for item in reversed(chunk):
            if isinstance(item, np.ndarray):
                return item
        for item in reversed(chunk):
            if isinstance(item, (list, tuple)) and item:
                arr = np.asarray(item)
                if arr.size > 0:
                    return arr
        return None

    if isinstance(chunk, (bytes, bytearray)):
        return None

    try:
        arr = np.asarray(chunk)
        if arr.size > 0:
            return arr
    except Exception:
        return None
    return None


def synthesize_kokoro(text: str, language: str = "en") -> bytes | None:
    """
    Synthesize speech with Kokoro and return OGG/Opus bytes for Telegram.

    Returns None on dependency/runtime errors.
    """
    if not KOKORO_AVAILABLE:
        return None

    payload = (text or "").strip()
    if not payload:
        return None

    normalized_lang = (language or "en").strip().lower()[:2] or "en"
    voice = KOKORO_VOICE_MAP.get(normalized_lang, DEFAULT_VOICE)
    lang_code = _LANG_CODE_MAP.get(normalized_lang, DEFAULT_LANG_CODE)

    try:
        import numpy as np
        import soundfile as sf
        from pydub import AudioSegment

        pipeline = kokoro.KPipeline(lang_code=lang_code)
        generator = pipeline(payload, voice=voice, speed=1.1, split_pattern=r"\n+")

        chunks = []
        for chunk in generator:
            arr = _as_audio_array(chunk)
            if arr is not None:
                chunks.append(np.asarray(arr, dtype=np.float32))

        if not chunks:
            return None

        merged = np.concatenate(chunks)
        if merged.size == 0:
            return None

        wav_buffer = BytesIO()
        sf.write(wav_buffer, merged, samplerate=24000, format="WAV", subtype="PCM_16")
        wav_buffer.seek(0)

        ogg_buffer = BytesIO()
        audio = AudioSegment.from_file(wav_buffer, format="wav")
        audio.export(ogg_buffer, format="ogg", codec="libopus")
        return ogg_buffer.getvalue()
    except Exception:
        logger.exception("Kokoro synthesis failed")
        return None

