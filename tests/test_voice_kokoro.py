from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

from tools import voice
from tools import voice_kokoro


class _FakeArray:
    def __init__(self, data):
        self.data = list(data)
        self.size = len(self.data)


def _fake_numpy_module() -> ModuleType:
    fake_np = ModuleType("numpy")
    fake_np.ndarray = _FakeArray
    fake_np.float32 = "float32"

    def asarray(data, dtype=None):  # noqa: ARG001
        if isinstance(data, _FakeArray):
            return data
        if isinstance(data, (list, tuple)):
            return _FakeArray(data)
        return _FakeArray([data])

    def concatenate(chunks):
        merged = []
        for chunk in chunks:
            merged.extend(getattr(chunk, "data", []))
        return _FakeArray(merged)

    def zeros(size, dtype=None):  # noqa: ARG001
        return _FakeArray([0.0] * int(size))

    fake_np.asarray = asarray
    fake_np.concatenate = concatenate
    fake_np.zeros = zeros
    return fake_np


def _fake_soundfile_module() -> ModuleType:
    fake_sf = ModuleType("soundfile")

    def write(fp, data, samplerate, format, subtype):  # noqa: ARG001
        fp.write(b"fake-wav")

    fake_sf.write = write
    return fake_sf


def _fake_pydub_module() -> ModuleType:
    fake_pydub = ModuleType("pydub")

    class _FakeAudio:
        def export(self, fp, format, codec):  # noqa: A003
            assert format == "ogg"
            assert codec == "libopus"
            fp.write(b"fake-ogg")

    fake_pydub.AudioSegment = type(
        "FakeAudioSegment",
        (),
        {"from_file": staticmethod(lambda fp, format: _FakeAudio())},  # noqa: A002
    )
    return fake_pydub


def test_kokoro_unavailable_returns_none() -> None:
    with patch.object(voice_kokoro, "KOKORO_AVAILABLE", False):
        assert voice_kokoro.synthesize_kokoro("hello", "en") is None


def test_kokoro_available_returns_bytes() -> None:
    fake_np = _fake_numpy_module()
    fake_sf = _fake_soundfile_module()
    fake_pydub = _fake_pydub_module()
    fake_chunk = fake_np.zeros(8)

    class FakePipeline:
        def __init__(self, lang_code):  # noqa: ARG002
            pass

        def __call__(self, text, voice, speed, split_pattern):  # noqa: ARG002
            return iter([fake_chunk])

    fake_kokoro = SimpleNamespace(KPipeline=FakePipeline)

    with patch.object(voice_kokoro, "KOKORO_AVAILABLE", True), patch.object(
        voice_kokoro, "kokoro", fake_kokoro
    ), patch.dict(sys.modules, {"numpy": fake_np, "soundfile": fake_sf, "pydub": fake_pydub}):
        result = voice_kokoro.synthesize_kokoro("hello", "en")

    assert isinstance(result, bytes)
    assert result == b"fake-ogg"


def test_kokoro_exception_returns_none() -> None:
    class FailingPipeline:
        def __init__(self, lang_code):  # noqa: ARG002
            raise RuntimeError("boom")

    fake_kokoro = SimpleNamespace(KPipeline=FailingPipeline)

    with patch.object(voice_kokoro, "KOKORO_AVAILABLE", True), patch.object(
        voice_kokoro, "kokoro", fake_kokoro
    ):
        result = voice_kokoro.synthesize_kokoro("hello", "en")

    assert result is None


def test_kokoro_voice_map_portuguese() -> None:
    calls: list[tuple[str, str]] = []
    fake_np = _fake_numpy_module()
    fake_sf = _fake_soundfile_module()
    fake_pydub = _fake_pydub_module()
    fake_chunk = fake_np.zeros(4)

    class FakePipeline:
        def __init__(self, lang_code):
            calls.append(("init", lang_code))

        def __call__(self, text, voice, speed, split_pattern):  # noqa: ARG002
            calls.append(("voice", voice))
            return iter([fake_chunk])

    fake_kokoro = SimpleNamespace(KPipeline=FakePipeline)

    with patch.object(voice_kokoro, "KOKORO_AVAILABLE", True), patch.object(
        voice_kokoro, "kokoro", fake_kokoro
    ), patch.dict(sys.modules, {"numpy": fake_np, "soundfile": fake_sf, "pydub": fake_pydub}):
        result = voice_kokoro.synthesize_kokoro("olá", "pt")

    assert result == b"fake-ogg"
    assert ("voice", voice_kokoro.KOKORO_VOICE_MAP["pt"]) in calls


def test_synthesize_speech_uses_kokoro_when_available() -> None:
    with patch.object(voice, "_KOKORO_IMPORTED", True), patch.object(
        voice, "kokoro_available", return_value=True
    ), patch.object(voice, "synthesize_kokoro", return_value=b"fake_audio") as kokoro_mock:
        gtts_module = ModuleType("gtts")
        gtts_module.gTTS = MagicMock()
        pydub_module = ModuleType("pydub")
        pydub_module.AudioSegment = MagicMock()
        with patch.dict(sys.modules, {"gtts": gtts_module, "pydub": pydub_module}):
            result = voice.synthesize_speech("hello", "en")

    assert result == b"fake_audio"
    kokoro_mock.assert_called_once_with("hello", "en")
    gtts_module.gTTS.assert_not_called()


def test_synthesize_speech_falls_back_to_gtts() -> None:
    class FakeTTS:
        def __init__(self, text, lang):  # noqa: ARG002
            pass

        def write_to_fp(self, fp):
            fp.write(b"fake-mp3")

    class FakeAudio:
        def export(self, fp, format, codec):  # noqa: A003
            assert format == "ogg"
            assert codec == "libopus"
            fp.write(b"fallback-ogg")

    fake_gtts = ModuleType("gtts")
    fake_gtts.gTTS = FakeTTS
    fake_pydub = ModuleType("pydub")
    fake_pydub.AudioSegment = type(
        "FakeAudioSegment",
        (),
        {"from_file": staticmethod(lambda fp, format: FakeAudio())},  # noqa: A002
    )

    with patch.object(voice, "_KOKORO_IMPORTED", True), patch.object(
        voice, "kokoro_available", return_value=True
    ), patch.object(voice, "synthesize_kokoro", return_value=None), patch.dict(
        sys.modules, {"gtts": fake_gtts, "pydub": fake_pydub}
    ):
        result = voice.synthesize_speech("hello", "en")

    assert result == b"fallback-ogg"
