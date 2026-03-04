"""Unit tests for /patterns and pattern-related Telegram flows."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import interfaces.telegram_bot as telegram_bot


def _update(chat_id: int, text: str):
    message = SimpleNamespace(text=text, reply_text=AsyncMock())
    return SimpleNamespace(
        message=message,
        effective_user=SimpleNamespace(id=chat_id),
        effective_chat=SimpleNamespace(id=chat_id),
    )


@pytest.fixture(autouse=True)
def _authorized(monkeypatch):
    monkeypatch.setattr(telegram_bot, "_ignore_if_unauthorized", lambda update, allow_unpaired_start=False: False)
    monkeypatch.setattr(telegram_bot, "_user_lang", lambda update, text=None: "en")
    telegram_bot._pattern_index_per_user.clear()
    telegram_bot._pending_pattern_decision.clear()


@pytest.mark.asyncio
async def test_patterns_returns_formatted_list_sorted_by_confidence(monkeypatch):
    low = SimpleNamespace(id="p-low", confidence=0.68, trigger="time:monday@09:00", action="git pull")
    high = SimpleNamespace(id="p-high", confidence=0.92, trigger="time:friday@17:00", action="git push origin main")
    monkeypatch.setattr(telegram_bot, "get_patterns", lambda user_id: [low, high])

    update = _update(111, "/patterns")
    await telegram_bot.cmd_patterns(update, None)

    response = update.message.reply_text.call_args[0][0]
    assert "learned patterns (2)" in response.lower()
    assert response.index("git push origin main") < response.index("git pull")


@pytest.mark.asyncio
async def test_patterns_returns_friendly_message_when_no_patterns_exist(monkeypatch):
    monkeypatch.setattr(telegram_bot, "get_patterns", lambda user_id: [])

    update = _update(111, "/patterns")
    await telegram_bot.cmd_patterns(update, None)

    assert "no patterns learned yet" in update.message.reply_text.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_forget_id_removes_correct_pattern(monkeypatch):
    removed = []
    telegram_bot._pattern_index_per_user[111] = ["pattern-a", "pattern-b"]
    monkeypatch.setattr(telegram_bot, "delete_pattern", lambda pattern_id, user_id: removed.append((pattern_id, user_id)) or True)

    update = _update(111, "/forget 2")
    await telegram_bot.cmd_forget(update, None)

    assert removed == [("pattern-b", "111")]
    assert telegram_bot._pattern_index_per_user[111] == ["pattern-a"]


@pytest.mark.asyncio
async def test_forget_all_clears_all_patterns_for_user_id_only(monkeypatch):
    cleared = []
    monkeypatch.setattr(telegram_bot, "delete_all_patterns", lambda user_id: cleared.append(user_id) or 4)

    update = _update(111, "/forget all")
    await telegram_bot.cmd_forget(update, None)

    assert cleared == ["111"]


@pytest.mark.asyncio
async def test_pattern_notification_sent_on_third_occurrence():
    pattern = SimpleNamespace(id="pattern-3", trigger="after:git commit", action="git push")
    update = _update(111, "/task git push")

    await telegram_bot._maybe_notify_new_patterns(update, "en", [pattern])

    assert update.message.reply_text.call_count == 1
    assert "noticed a pattern" in update.message.reply_text.call_args[0][0].lower()
    assert telegram_bot._pending_pattern_decision[111]["pattern_id"] == "pattern-3"


@pytest.mark.asyncio
async def test_never_suggest_suppresses_pattern_permanently(monkeypatch):
    updates = []
    telegram_bot._pending_pattern_decision[111] = {"pattern_id": "pattern-4", "chat_id": "111"}
    monkeypatch.setattr(
        telegram_bot,
        "update_pattern_preferences",
        lambda pattern_id, user_id, **kwargs: updates.append((pattern_id, user_id, kwargs)) or SimpleNamespace(id=pattern_id),
    )

    update = _update(111, "/never")
    await telegram_bot.cmd_never(update, None)

    assert updates == [("pattern-4", "111", {"suppressed": True, "automated": False})]
    assert 111 not in telegram_bot._pending_pattern_decision
    assert "won't suggest" in update.message.reply_text.call_args[0][0].lower()
