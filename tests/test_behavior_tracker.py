"""Tests for learned behavior tracking."""

from datetime import datetime

from pathlib import Path

from sqlalchemy.orm import sessionmaker

import core.behavior_tracker as behavior_tracker
import core.memory as memory


def _setup_tracker_db(monkeypatch, tmp_path: Path):
    engine = memory.get_engine(str(tmp_path / "behavior.sqlite"))
    memory.init_db(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(memory, "get_session", lambda engine_override=None: session_factory())
    return session_factory


def test_observe_confirms_time_and_workflow_patterns_after_three_occurrences(monkeypatch, tmp_path):
    session_factory = _setup_tracker_db(monkeypatch, tmp_path)

    monday_nine = datetime(2026, 3, 2, 9, 0, 0)
    for _ in range(3):
        behavior_tracker.observe(
            "git pull",
            "user1",
            {
                "time": monday_nine,
                "current_app": "Visual Studio Code",
                "preceding_task": "open vscode",
            },
        )

    with session_factory() as session:
        patterns = memory.get_patterns("user1", session=session)
        types = {pattern.type for pattern in patterns}
        triggers = {pattern.trigger for pattern in patterns}

    assert "time_based" in types
    assert "context_based" in types
    assert "workflow_based" in types
    assert "time:monday@09:00" in triggers
    assert "app:visual studio code" in triggers
    assert "after:open vscode" in triggers
    assert all(pattern.occurrences >= 3 for pattern in patterns)


def test_observe_ignores_missing_user_or_empty_task(monkeypatch, tmp_path):
    session_factory = _setup_tracker_db(monkeypatch, tmp_path)

    behavior_tracker.observe("", "user1", {"time": datetime(2026, 3, 2, 9, 0, 0)})
    behavior_tracker.observe("git pull", None, {"time": datetime(2026, 3, 2, 9, 0, 0)})

    with session_factory() as session:
        assert memory.get_patterns("user1", session=session) == []
