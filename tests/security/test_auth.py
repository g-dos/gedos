"""Security tests for Telegram authorization."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import core.memory as memory
import interfaces.telegram_bot as telegram_bot


def _update(chat_id: int, text: str = "/start"):
    message = SimpleNamespace(text=text, reply_text=AsyncMock())
    return SimpleNamespace(
        message=message,
        effective_user=SimpleNamespace(id=chat_id),
        effective_chat=SimpleNamespace(id=chat_id),
    )


@pytest.mark.asyncio
async def test_unauthorized_chat_id_is_ignored_silently(monkeypatch):
    monkeypatch.setattr(telegram_bot, "memory_init_db", lambda: None)
    monkeypatch.setattr(telegram_bot, "get_owner", lambda: SimpleNamespace(chat_id="111"))
    monkeypatch.setattr(telegram_bot, "list_allowed_chats", lambda: [])
    monkeypatch.setattr(telegram_bot, "get_allowed_chat_ids", lambda: set())

    update = _update(222, "/help")
    await telegram_bot.cmd_help(update, None)

    update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_owner_is_set_on_first_start(monkeypatch):
    owner_calls = []
    monkeypatch.setattr(telegram_bot, "memory_init_db", lambda: None)
    monkeypatch.setattr(telegram_bot, "get_owner", lambda: None)
    monkeypatch.setattr(telegram_bot, "set_owner", lambda chat_id: owner_calls.append(chat_id))
    monkeypatch.setattr(telegram_bot, "add_conversation", lambda *args, **kwargs: None)
    monkeypatch.setattr(memory, "init_db", lambda: None)
    monkeypatch.setattr(memory, "get_recent_conversations", lambda *args, **kwargs: [])

    update = _update(111, "/start")
    await telegram_bot.cmd_start(update, None)

    assert owner_calls == ["111"]
    update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_second_start_from_different_chat_id_is_rejected(monkeypatch):
    monkeypatch.setattr(telegram_bot, "memory_init_db", lambda: None)
    monkeypatch.setattr(telegram_bot, "get_owner", lambda: SimpleNamespace(chat_id="111"))
    monkeypatch.setattr(telegram_bot, "list_allowed_chats", lambda: [])
    monkeypatch.setattr(telegram_bot, "get_allowed_chat_ids", lambda: set())

    update = _update(222, "/start")
    await telegram_bot.cmd_start(update, None)

    update.message.reply_text.assert_not_called()


def test_allowed_chat_ids_from_env_is_respected(monkeypatch):
    monkeypatch.setattr(telegram_bot, "memory_init_db", lambda: None)
    monkeypatch.setattr(telegram_bot, "get_owner", lambda: SimpleNamespace(chat_id="111"))
    monkeypatch.setattr(telegram_bot, "list_allowed_chats", lambda: [])
    monkeypatch.setenv("ALLOWED_CHAT_IDS", "222,333")

    allowed = telegram_bot._authorized_chat_ids()

    assert allowed == {"111", "222", "333"}
