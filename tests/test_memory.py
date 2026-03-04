"""Smoke tests for core.memory (in-memory SQLite)."""

from datetime import timedelta

import pytest
from core.memory import (
    Conversation,
    Task,
    Context,
    Pattern,
    get_engine,
    init_db,
    get_session,
    add_conversation,
    get_recent_conversations,
    add_task,
    update_task,
    get_recent_tasks,
    add_context,
    get_recent_context,
    get_voice_output,
    prune_old_conversations,
    add_or_update_pattern,
    get_patterns,
    increment_pattern,
    decay_patterns,
    delete_pattern,
    delete_all_patterns,
    set_voice_output,
)


@pytest.fixture()
def db_session(tmp_path):
    """In-memory SQLite for each test."""
    engine = get_engine(str(tmp_path / "memory.sqlite"))
    init_db(engine)
    from sqlalchemy.orm import sessionmaker
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


def test_add_and_get_conversation(db_session):
    c = add_conversation("user1", "hello", response="hi", session=db_session)
    assert c.id is not None
    assert c.user_id == "user1"
    convos = get_recent_conversations("user1", limit=5, session=db_session)
    assert len(convos) == 1
    assert convos[0].message == "hello"


def test_add_and_update_task(db_session):
    t = add_task("run ls", status="running", agent_used="terminal", session=db_session)
    assert t.status == "running"
    updated = update_task(t.id, status="completed", result="file1\nfile2", session=db_session)
    assert updated.status == "completed"
    assert updated.result == "file1\nfile2"


def test_get_recent_tasks(db_session):
    add_task("task1", session=db_session)
    add_task("task2", session=db_session)
    tasks = get_recent_tasks(limit=10, session=db_session)
    assert len(tasks) >= 2


def test_add_and_get_context(db_session):
    add_context("app_state", {"app": "Terminal"}, session=db_session)
    ctx = get_recent_context("app_state", limit=5, session=db_session)
    assert len(ctx) >= 1
    assert any(c.data.get("app") == "Terminal" for c in ctx)


def test_voice_output_preference_defaults_false_and_can_be_enabled(db_session):
    assert get_voice_output("user1", session=db_session) is False

    pref = set_voice_output("user1", True, session=db_session)

    assert pref.voice_output_enabled is True
    assert get_voice_output("user1", session=db_session) is True


def test_prune_old_conversations(db_session):
    add_conversation("user1", "old msg", session=db_session)
    deleted = prune_old_conversations(retention_days=0, session=db_session)
    assert deleted >= 0


def test_pattern_crud_and_decay(db_session):
    pattern = add_or_update_pattern(
        {
            "id": "pattern-1",
            "user_id": "user1",
            "type": "time_based",
            "trigger": "time:monday@09:00",
            "action": "git pull",
            "occurrences": 2,
        },
        session=db_session,
    )
    assert pattern.active is False

    updated = increment_pattern("pattern-1", session=db_session)
    assert updated is not None
    assert updated.occurrences == 3
    assert updated.active is True

    patterns = get_patterns("user1", session=db_session)
    assert len(patterns) == 1
    assert patterns[0].action == "git pull"

    updated.last_seen = updated.last_seen - timedelta(days=31)
    db_session.commit()
    changed = decay_patterns("user1", session=db_session)
    assert changed == 1

    deleted = delete_pattern("pattern-1", "user1", session=db_session)
    assert deleted is True
    assert get_patterns("user1", session=db_session) == []


def test_delete_all_patterns_also_removes_pattern_rows(db_session):
    add_task("task", user_id="user1", session=db_session)
    add_or_update_pattern(
        {
            "id": "pattern-2",
            "user_id": "user1",
            "type": "workflow_based",
            "trigger": "after:pytest",
            "action": "git commit",
            "occurrences": 3,
            "active": True,
        },
        session=db_session,
    )

    deleted = delete_all_patterns("user1", session=db_session)

    assert deleted >= 2
    assert db_session.query(Pattern).filter(Pattern.user_id == "user1").count() == 0
