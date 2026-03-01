"""
GEDOS Memory Layer — SQLite + SQLAlchemy persistence.
Stores conversations, tasks, and context across sessions.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import JSON, DateTime, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""

    pass


class Conversation(Base):
    """Telegram chat history."""

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Task(Base):
    """Planned and executed tasks."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending, running, completed, failed
    agent_used: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # terminal, gui, web
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Context(Base):
    """App state, screen content, learnings."""

    __tablename__ = "context"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(64), nullable=False)  # app_state, screen_content, learning
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


def get_engine(database_path: Optional[str] = None):
    """Create SQLite engine. Uses config if database_path is None."""
    if database_path is None:
        try:
            from core.config import load_config
            config = load_config()
            db_path = (config.get("memory") or {}).get("database_path", "gedos.db")
        except Exception:
            db_path = "gedos.db"
    else:
        db_path = database_path
    path = Path(db_path)
    if not path.is_absolute():
        root = Path(__file__).resolve().parent.parent
        path = root / path
    path.parent.mkdir(parents=True, exist_ok=True)
    url = f"sqlite:///{path}"
    return create_engine(url, echo=False)


def init_db(engine=None):
    """Create all tables if they do not exist."""
    if engine is None:
        engine = get_engine()
    Base.metadata.create_all(engine)
    logger.info("Memory DB initialized")


def get_session(engine=None) -> Session:
    """Return a new session. Caller should close or use as context manager."""
    if engine is None:
        engine = get_engine()
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return SessionLocal()


# --- Conversation CRUD ---


def add_conversation(user_id: str, message: str, response: Optional[str] = None, session: Optional[Session] = None) -> Conversation:
    """Persist a conversation turn."""
    own_session = session is None
    if own_session:
        session = get_session()
    try:
        c = Conversation(user_id=user_id, message=message, response=response)
        session.add(c)
        session.commit()
        session.refresh(c)
        return c
    finally:
        if own_session:
            session.close()


def get_recent_conversations(user_id: str, limit: int = 20, session: Optional[Session] = None) -> list[Conversation]:
    """Get recent conversations for a user."""
    own_session = session is None
    if own_session:
        session = get_session()
    try:
        return list(
            session.query(Conversation)
            .filter(Conversation.user_id == user_id)
            .order_by(Conversation.timestamp.desc())
            .limit(limit)
            .all()
        )
    finally:
        if own_session:
            session.close()


# --- Task CRUD ---


def add_task(description: str, status: str = "pending", agent_used: Optional[str] = None, result: Optional[str] = None, session: Optional[Session] = None) -> Task:
    """Create a new task record."""
    own_session = session is None
    if own_session:
        session = get_session()
    try:
        t = Task(description=description, status=status, agent_used=agent_used, result=result)
        session.add(t)
        session.commit()
        session.refresh(t)
        return t
    finally:
        if own_session:
            session.close()


def update_task(task_id: int, status: Optional[str] = None, agent_used: Optional[str] = None, result: Optional[str] = None, session: Optional[Session] = None) -> Optional[Task]:
    """Update an existing task."""
    own_session = session is None
    if own_session:
        session = get_session()
    try:
        t = session.get(Task, task_id)
        if not t:
            return None
        if status is not None:
            t.status = status
        if agent_used is not None:
            t.agent_used = agent_used
        if result is not None:
            t.result = result
        session.commit()
        session.refresh(t)
        return t
    finally:
        if own_session:
            session.close()


def get_recent_tasks(limit: int = 20, session: Optional[Session] = None) -> list[Task]:
    """Get recent tasks for history/memory view."""
    own_session = session is None
    if own_session:
        session = get_session()
    try:
        return list(session.query(Task).order_by(Task.created_at.desc()).limit(limit).all())
    finally:
        if own_session:
            session.close()


# --- Context CRUD ---


def add_context(type_name: str, data: dict[str, Any], session: Optional[Session] = None) -> Context:
    """Store context (app state, screen content, learning)."""
    own_session = session is None
    if own_session:
        session = get_session()
    try:
        c = Context(type=type_name, data=data)
        session.add(c)
        session.commit()
        session.refresh(c)
        return c
    finally:
        if own_session:
            session.close()


def get_recent_context(type_name: Optional[str] = None, limit: int = 10, session: Optional[Session] = None) -> list[Context]:
    """Get recent context entries, optionally filtered by type."""
    own_session = session is None
    if own_session:
        session = get_session()
    try:
        q = session.query(Context)
        if type_name:
            q = q.filter(Context.type == type_name)
        return list(q.order_by(Context.timestamp.desc()).limit(limit).all())
    finally:
        if own_session:
            session.close()


def prune_old_conversations(retention_days: int = 30, session: Optional[Session] = None) -> int:
    """Delete conversations older than retention_days. Returns count deleted."""
    own_session = session is None
    if own_session:
        session = get_session()
    try:
        cutoff = datetime.utcnow() - timedelta(days=retention_days)
        deleted = session.query(Conversation).filter(Conversation.timestamp < cutoff).delete()
        session.commit()
        return deleted
    finally:
        if own_session:
            session.close()
