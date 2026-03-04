"""
GEDOS Memory Layer — SQLite + SQLAlchemy persistence.
Stores conversations, tasks, and context across sessions.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import JSON, Boolean, DateTime, String, Text, create_engine, text
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


class ScheduledTask(Base):
    """Scheduled tasks (one-time and recurring)."""

    __tablename__ = "scheduled_tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    task_description: Mapped[str] = mapped_column(Text, nullable=False)
    frequency: Mapped[str] = mapped_column(String(32), nullable=False)  # once, daily, weekly
    schedule_time: Mapped[str] = mapped_column(String(16), nullable=False)  # HH:MM format
    schedule_date: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)  # YYYY-MM-DD for once (e.g. tomorrow)
    day_of_week: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)  # monday, tuesday, etc (for weekly)
    is_active: Mapped[bool] = mapped_column(default=True)
    job_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # APScheduler job ID
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_run: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Owner(Base):
    """Authorized Telegram owner chat."""

    __tablename__ = "owners"

    chat_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AllowedChat(Base):
    """Additional authorized Telegram chats."""

    __tablename__ = "allowed_chats"

    chat_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


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
    # Migration: add schedule_date to scheduled_tasks if missing
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE scheduled_tasks ADD COLUMN schedule_date VARCHAR(16)"))
            conn.commit()
    except Exception:
        pass  # Column may already exist
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


def get_user_timezone(user_id: str, session: Optional[Session] = None) -> Optional[str]:
    """Get stored timezone for a user. Returns None if not set."""
    entries = get_recent_context(type_name="user_timezone", limit=50, session=session)
    for e in entries:
        if e.data.get("user_id") == str(user_id):
            return e.data.get("timezone")
    return None


def set_user_timezone(user_id: str, timezone: str, session: Optional[Session] = None) -> Context:
    """Store timezone preference for a user."""
    return add_context("user_timezone", {"user_id": str(user_id), "timezone": timezone}, session=session)


def get_user_language(user_id: str, session: Optional[Session] = None) -> Optional[str]:
    """Get cached language for a user. Returns None if not set."""
    entries = get_recent_context(type_name="user_language", limit=50, session=session)
    for e in entries:
        if e.data.get("user_id") == str(user_id):
            return e.data.get("language")
    return None


def set_user_language(user_id: str, language: str, session: Optional[Session] = None) -> Context:
    """Store language preference for a user."""
    return add_context("user_language", {"user_id": str(user_id), "language": language}, session=session)


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


# --- Owner/Auth CRUD ---


def get_owner(session: Optional[Session] = None) -> Optional[Owner]:
    """Return the configured owner chat, if any."""
    own_session = session is None
    if own_session:
        session = get_session()
    try:
        return session.query(Owner).order_by(Owner.created_at.asc()).first()
    finally:
        if own_session:
            session.close()


def set_owner(chat_id: str, session: Optional[Session] = None) -> Owner:
    """Persist the bot owner chat."""
    own_session = session is None
    if own_session:
        session = get_session()
    try:
        owner = get_owner(session=session)
        if owner:
            return owner
        owner = Owner(chat_id=str(chat_id))
        session.add(owner)
        session.commit()
        session.refresh(owner)
        return owner
    finally:
        if own_session:
            session.close()


def list_allowed_chats(session: Optional[Session] = None) -> list[AllowedChat]:
    """Return explicitly allowed chats."""
    own_session = session is None
    if own_session:
        session = get_session()
    try:
        return list(session.query(AllowedChat).order_by(AllowedChat.created_at.asc()).all())
    finally:
        if own_session:
            session.close()


def add_allowed_chat(chat_id: str, session: Optional[Session] = None) -> AllowedChat:
    """Allow an additional chat id."""
    own_session = session is None
    if own_session:
        session = get_session()
    try:
        existing = session.get(AllowedChat, str(chat_id))
        if existing:
            return existing
        allowed = AllowedChat(chat_id=str(chat_id))
        session.add(allowed)
        session.commit()
        session.refresh(allowed)
        return allowed
    finally:
        if own_session:
            session.close()


def remove_allowed_chat(chat_id: str, session: Optional[Session] = None) -> bool:
    """Revoke an allowed chat id."""
    own_session = session is None
    if own_session:
        session = get_session()
    try:
        entry = session.get(AllowedChat, str(chat_id))
        if not entry:
            return False
        session.delete(entry)
        session.commit()
        return True
    finally:
        if own_session:
            session.close()


# --- ScheduledTask CRUD ---


def add_scheduled_task(
    user_id: str,
    task_description: str,
    frequency: str,
    schedule_time: str,
    day_of_week: Optional[str] = None,
    schedule_date: Optional[str] = None,
    job_id: Optional[str] = None,
    session: Optional[Session] = None
) -> ScheduledTask:
    """Create a new scheduled task record."""
    own_session = session is None
    if own_session:
        session = get_session()
    try:
        task = ScheduledTask(
            user_id=user_id,
            task_description=task_description,
            frequency=frequency,
            schedule_time=schedule_time,
            day_of_week=day_of_week,
            schedule_date=schedule_date,
            job_id=job_id
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        return task
    finally:
        if own_session:
            session.close()


def get_scheduled_tasks(user_id: Optional[str] = None, active_only: bool = True, session: Optional[Session] = None) -> list[ScheduledTask]:
    """Get scheduled tasks, optionally filtered by user and active status."""
    own_session = session is None
    if own_session:
        session = get_session()
    try:
        q = session.query(ScheduledTask)
        if user_id:
            q = q.filter(ScheduledTask.user_id == user_id)
        if active_only:
            q = q.filter(ScheduledTask.is_active == True)
        return list(q.order_by(ScheduledTask.created_at.desc()).all())
    finally:
        if own_session:
            session.close()


def get_scheduled_task_by_id(task_id: int, session: Optional[Session] = None) -> Optional[ScheduledTask]:
    """Get a scheduled task by ID."""
    own_session = session is None
    if own_session:
        session = get_session()
    try:
        return session.get(ScheduledTask, task_id)
    finally:
        if own_session:
            session.close()


def update_scheduled_task(
    task_id: int,
    is_active: Optional[bool] = None,
    job_id: Optional[str] = None,
    last_run: Optional[datetime] = None,
    session: Optional[Session] = None
) -> Optional[ScheduledTask]:
    """Update a scheduled task."""
    own_session = session is None
    if own_session:
        session = get_session()
    try:
        task = session.get(ScheduledTask, task_id)
        if not task:
            return None
        if is_active is not None:
            task.is_active = is_active
        if job_id is not None:
            task.job_id = job_id
        if last_run is not None:
            task.last_run = last_run
        session.commit()
        session.refresh(task)
        return task
    finally:
        if own_session:
            session.close()


def delete_scheduled_task(task_id: int, session: Optional[Session] = None) -> bool:
    """Delete a scheduled task. Returns True if deleted, False if not found."""
    own_session = session is None
    if own_session:
        session = get_session()
    try:
        task = session.get(ScheduledTask, task_id)
        if not task:
            return False
        session.delete(task)
        session.commit()
        return True
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
