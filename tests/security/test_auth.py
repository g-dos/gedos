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
    monkeypatch.setattr(telegram_bot, "_claim_pairing_code", lambda: "PAIR-1234")
    monkeypatch.setattr(telegram_bot, "_invalidate_generated_pairing_code", lambda: None)
    monkeypatch.setattr(memory, "init_db", lambda: None)
    monkeypatch.setattr(memory, "get_recent_conversations", lambda *args, **kwargs: [])

    update = _update(111, "/start PAIR-1234")
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


@pytest.mark.asyncio
async def test_generated_pairing_code_required_when_env_missing(monkeypatch):
    owner_calls = []
    monkeypatch.setattr(telegram_bot, "memory_init_db", lambda: None)
    monkeypatch.setattr(telegram_bot, "get_owner", lambda: None)
    monkeypatch.setattr(telegram_bot, "set_owner", lambda chat_id: owner_calls.append(chat_id))
    monkeypatch.setattr(telegram_bot.secrets, "token_hex", lambda _: "abcd1234")
    monkeypatch.setattr("builtins.print", lambda *args, **kwargs: None)
    monkeypatch.setattr(telegram_bot, "_generated_pairing_code", None)

    update = _update(111, "/start")
    await telegram_bot.cmd_start(update, None)

    assert owner_calls == []
    update.message.reply_text.assert_called_once()
    assert telegram_bot._generated_pairing_code == "ABCD-1234"


@pytest.mark.asyncio
async def test_unauthorized_flood_logs_once_per_minute(monkeypatch):
    warnings = []
    monkeypatch.setattr(telegram_bot, "memory_init_db", lambda: None)
    monkeypatch.setattr(telegram_bot, "get_owner", lambda: SimpleNamespace(chat_id="111"))
    monkeypatch.setattr(telegram_bot, "list_allowed_chats", lambda: [])
    monkeypatch.setattr(telegram_bot, "get_allowed_chat_ids", lambda: set())
    monkeypatch.setattr(telegram_bot, "_unauthorized_chat_log_at", {})
    monkeypatch.setattr(telegram_bot.logger, "warning", lambda *args, **kwargs: warnings.append((args, kwargs)))

    first = _update(222, "/help")
    second = _update(222, "/help")
    await telegram_bot.cmd_help(first, None)
    await telegram_bot.cmd_help(second, None)

    assert first.message.reply_text.call_count == 0
    assert second.message.reply_text.call_count == 0
    assert len(warnings) == 1


@pytest.mark.asyncio
async def test_memory_history_is_scoped_to_chat_id(monkeypatch):
    monkeypatch.setattr(telegram_bot, "memory_init_db", lambda: None)
    monkeypatch.setattr(telegram_bot, "get_owner", lambda: SimpleNamespace(chat_id="111"))
    monkeypatch.setattr(telegram_bot, "list_allowed_chats", lambda: [])
    monkeypatch.setattr(telegram_bot, "get_allowed_chat_ids", lambda: set())

    requested = {}

    def _recent_tasks(*, limit, user_id):
        requested["limit"] = limit
        requested["user_id"] = user_id
        return []

    monkeypatch.setattr(telegram_bot, "get_recent_tasks", _recent_tasks)

    update = _update(111, "/memory")
    await telegram_bot.cmd_memory(update, None)

    assert requested == {"limit": 10, "user_id": "111"}
    update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_forget_all_clears_requesting_chat(monkeypatch):
    cleared = []
    monkeypatch.setattr(telegram_bot, "memory_init_db", lambda: None)
    monkeypatch.setattr(telegram_bot, "get_owner", lambda: SimpleNamespace(chat_id="111"))
    monkeypatch.setattr(telegram_bot, "list_allowed_chats", lambda: [])
    monkeypatch.setattr(telegram_bot, "get_allowed_chat_ids", lambda: set())
    monkeypatch.setattr(telegram_bot, "delete_all_patterns", lambda user_id: cleared.append(user_id) or 1)

    update = _update(111, "/forget all")
    await telegram_bot.cmd_forget(update, None)

    assert cleared == ["111"]
    update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_patterns_lists_active_patterns(monkeypatch):
    pattern = SimpleNamespace(
        id="pattern-1",
        confidence=0.92,
        trigger="time:friday@17:00",
        action="git push origin main",
    )
    monkeypatch.setattr(telegram_bot, "memory_init_db", lambda: None)
    monkeypatch.setattr(telegram_bot, "get_owner", lambda: SimpleNamespace(chat_id="111"))
    monkeypatch.setattr(telegram_bot, "list_allowed_chats", lambda: [])
    monkeypatch.setattr(telegram_bot, "get_allowed_chat_ids", lambda: set())
    monkeypatch.setattr(telegram_bot, "get_patterns", lambda user_id: [pattern])

    update = _update(111, "/patterns")
    await telegram_bot.cmd_patterns(update, None)

    update.message.reply_text.assert_called_once()
    response = update.message.reply_text.call_args[0][0]
    assert "learned patterns" in response.lower()
    assert "git push origin main" in response.lower()
