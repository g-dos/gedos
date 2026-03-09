from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

from core.memory import get_engine, init_db
from core.memory_semantic import SEMANTIC_MEMORY_AVAILABLE, SemanticMemory
from core.orchestrator import run_task_with_langgraph
from core.proactive_engine import notify, register_sink, unregister_sink
from tools.voice import synthesize_speech


def test_smoke_cli_task():
    with patch("core.orchestrator.run_single_step_task", return_value={"success": True, "result": "hello", "agent_used": "terminal"}):
        result = run_task_with_langgraph(task="echo hello", user_id="smoke_test", context={})
    output = str(result.get("result", ""))
    assert output.strip()
    assert "Traceback" not in output


def test_smoke_memory_init(tmp_path: Path):
    db_path = tmp_path / "smoke.db"
    engine = get_engine(str(db_path))
    init_db(engine)
    assert db_path.exists()


def test_smoke_semantic_memory_init(tmp_path: Path):
    if not SEMANTIC_MEMORY_AVAILABLE:
        return
    mem = SemanticMemory(user_id="smoke", persist_dir=str(tmp_path / "semantic"))
    mem.add("test entry")
    result = mem.search("test")
    assert isinstance(result, list)


def test_smoke_voice_pipeline():
    with patch("tools.voice._KOKORO_IMPORTED", True), patch(
        "tools.voice.kokoro_available", return_value=True
    ), patch("tools.voice.synthesize_kokoro", return_value=b"fake-audio"):
        result = synthesize_speech("hello", "en")
    assert result is None or isinstance(result, bytes)

    class FakeTTS:
        def __init__(self, text, lang):  # noqa: ARG002
            pass

        def write_to_fp(self, fp):
            fp.write(b"fake-mp3")

    class FakeAudio:
        def export(self, fp, format, codec):  # noqa: A003
            fp.write(b"fake-ogg")

    fake_gtts = ModuleType("gtts")
    fake_gtts.gTTS = FakeTTS
    fake_pydub = ModuleType("pydub")
    fake_pydub.AudioSegment = type(
        "FakeAudioSegment",
        (),
        {"from_file": staticmethod(lambda fp, format: FakeAudio())},
    )
    with patch("tools.voice._KOKORO_IMPORTED", True), patch(
        "tools.voice.kokoro_available", return_value=True
    ), patch("tools.voice.synthesize_kokoro", return_value=None), patch.dict(
        sys.modules, {"gtts": fake_gtts, "pydub": fake_pydub}
    ):
        fallback = synthesize_speech("hello", "en")
    assert fallback is None or isinstance(fallback, bytes)


def test_smoke_proactive_engine():
    sink = MagicMock()
    sink_name = "smoke_sink"
    try:
        register_sink(sink_name, sink)
        sent = notify(user_id="smoke", message="test", category="system", priority="low")
        assert sent is True
        sink.assert_called_once()
    finally:
        unregister_sink(sink_name)
