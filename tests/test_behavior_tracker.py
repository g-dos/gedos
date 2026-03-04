"""Unit tests for behavior tracking and pattern learning logic."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import core.behavior_tracker as behavior_tracker
import core.memory as memory


class _FakeQuery:
    """Very small query stub for unit tests."""

    def __init__(self, items):
        self._items = items

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return list(self._items)


class _FakeSession:
    """Minimal session stub for memory-layer unit tests."""

    def __init__(self, items):
        self.items = list(items)
        self.deleted = []
        self.commits = 0

    def query(self, model):
        return _FakeQuery(self.items)

    def delete(self, item):
        self.deleted.append(item)

    def commit(self):
        self.commits += 1


def test_pattern_created_after_three_occurrences_of_same_command(monkeypatch):
    calls = []
    pattern = SimpleNamespace(id="pattern-1", action="git pull")

    def fake_upsert(user_id, pattern_type, trigger, action, seen_at):
        calls.append((user_id, pattern_type, trigger, action))
        return pattern, len(calls) >= 3

    monkeypatch.setattr(behavior_tracker, "_upsert_pattern", fake_upsert)
    monkeypatch.setattr(behavior_tracker, "decay_patterns", lambda user_id: 0)

    first = behavior_tracker.observe("git pull", "user1", {"time": datetime(2026, 3, 2, 9, 0, 0)})
    second = behavior_tracker.observe("git pull", "user1", {"time": datetime(2026, 3, 2, 9, 0, 0)})
    third = behavior_tracker.observe("git pull", "user1", {"time": datetime(2026, 3, 2, 9, 0, 0)})

    assert first == []
    assert second == []
    assert third == [pattern]


def test_pattern_confidence_increases_with_each_occurrence():
    assert memory._pattern_confidence(1) < memory._pattern_confidence(2)
    assert memory._pattern_confidence(2) < memory._pattern_confidence(3)


def test_pattern_confidence_caps_at_one_point_zero():
    assert memory._pattern_confidence(10) == 1.0
    assert memory._pattern_confidence(999) == 1.0


def test_pattern_decays_after_thirty_days_inactivity():
    pattern = SimpleNamespace(
        user_id="user1",
        confidence=0.6,
        last_seen=datetime.utcnow() - timedelta(days=31),
        occurrences=5,
        active=True,
    )
    session = _FakeSession([pattern])

    changed = memory.decay_patterns("user1", session=session)

    assert changed == 1
    assert pattern.confidence == 0.5
    assert pattern.active is True
    assert session.commits == 1


def test_pattern_removed_when_confidence_drops_below_zero_point_one():
    pattern = SimpleNamespace(
        user_id="user1",
        confidence=0.05,
        last_seen=datetime.utcnow() - timedelta(days=31),
        occurrences=3,
        active=True,
    )
    session = _FakeSession([pattern])

    changed = memory.decay_patterns("user1", session=session)

    assert changed == 1
    assert pattern in session.deleted
    assert session.commits == 1


def test_max_fifty_patterns_per_user_enforced():
    patterns = [
        SimpleNamespace(user_id="user1", confidence=1.0 - (idx * 0.01), last_seen=datetime.utcnow(), active=True)
        for idx in range(51)
    ]
    session = _FakeSession(patterns)

    memory._trim_active_patterns("user1", session)

    assert sum(1 for pattern in patterns if pattern.active) == 50
    assert patterns[-1].active is False


def test_observe_identifies_time_based_pattern_correctly(monkeypatch):
    recorded = []
    monkeypatch.setattr(behavior_tracker, "_upsert_pattern", lambda *args: recorded.append(args) or (SimpleNamespace(), False))
    monkeypatch.setattr(behavior_tracker, "decay_patterns", lambda user_id: 0)

    behavior_tracker.observe("git pull", "user1", {"time": datetime(2026, 3, 2, 9, 0, 0)})

    assert ("user1", "time_based", "time:monday@09:00", "git pull", datetime(2026, 3, 2, 9, 0, 0)) in recorded


def test_observe_identifies_context_based_pattern_correctly(monkeypatch):
    recorded = []
    monkeypatch.setattr(behavior_tracker, "_upsert_pattern", lambda *args: recorded.append(args) or (SimpleNamespace(), False))
    monkeypatch.setattr(behavior_tracker, "decay_patterns", lambda user_id: 0)

    behavior_tracker.observe(
        "pytest",
        "user1",
        {"time": datetime(2026, 3, 2, 9, 0, 0), "current_app": "Visual Studio Code"},
    )

    assert any(call[1] == "context_based" and call[2] == "app:visual studio code" and call[3] == "pytest" for call in recorded)


def test_observe_identifies_workflow_based_pattern_correctly(monkeypatch):
    recorded = []
    monkeypatch.setattr(behavior_tracker, "_upsert_pattern", lambda *args: recorded.append(args) or (SimpleNamespace(), False))
    monkeypatch.setattr(behavior_tracker, "decay_patterns", lambda user_id: 0)

    behavior_tracker.observe(
        "git push",
        "user1",
        {"time": datetime(2026, 3, 2, 9, 0, 0), "preceding_task": "git commit"},
    )

    assert any(call[1] == "workflow_based" and call[2] == "after:git commit" and call[3] == "git push" for call in recorded)


def test_suppressed_pattern_is_never_suggested_again(monkeypatch):
    active = SimpleNamespace(id="pattern-1", suppressed=False)
    suppressed = SimpleNamespace(id="pattern-2", suppressed=True)
    monkeypatch.setattr(behavior_tracker, "memory_get_patterns", lambda user_id, include_suppressed=True: [active, suppressed])

    result = behavior_tracker.get_active_patterns("user1")

    assert result == [active]
