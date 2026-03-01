"""Smoke tests for core.memory (in-memory SQLite)."""

import pytest
from core.memory import (
    Base,
    Conversation,
    Task,
    Context,
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
    prune_old_conversations,
)


@pytest.fixture()
def db_session():
    """In-memory SQLite for each test."""
    engine = get_engine(":memory:")
    Base.metadata.create_all(engine)
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


def test_prune_old_conversations(db_session):
    add_conversation("user1", "old msg", session=db_session)
    deleted = prune_old_conversations(retention_days=0, session=db_session)
    assert deleted >= 0
