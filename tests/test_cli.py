"""Tests for CLI mode and GEDOS.md parsing."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import gedos
from core import config as config_module
from interfaces import cli as cli_module


def test_load_gedos_profile_parses_yaml_like_sections(tmp_path):
    profile_path = tmp_path / "GEDOS.md"
    profile_path.write_text(
        "# GEDOS.md\n"
        "## About you\n"
        "name: Santiago\n"
        "refer_as: Master Santiago\n"
        "## Preferences\n"
        "language: pt\n"
        "response_style: concise\n"
        "## Permissions\n"
        "level: full_access\n"
        "## Context\n"
        "I work on macOS automation.\n"
        "## Blocked commands\n"
        "- rm -rf /\n",
        encoding="utf-8",
    )

    with patch("core.config.get_gedos_md_path", return_value=profile_path):
        profile = config_module.load_gedos_profile()

    assert profile["name"] == "Santiago"
    assert profile["refer_as"] == "Master Santiago"
    assert profile["language"] == "pt"
    assert profile["response_style"] == "concise"
    assert profile["level"] == "full_access"
    assert "macOS automation" in profile["context"]
    assert profile["blocked_commands"] == ["rm -rf /"]


def test_runtime_mode_uses_cli_when_no_token():
    args = SimpleNamespace(mcp=False)

    with patch("gedos.has_telegram_token", return_value=False):
        assert gedos._runtime_mode(args, {}) == "cli"


def test_runtime_mode_uses_telegram_when_token_exists():
    args = SimpleNamespace(mcp=False)

    with patch("gedos.has_telegram_token", return_value=True):
        assert gedos._runtime_mode(args, {}) == "telegram"


def test_ensure_gedos_md_creates_template(tmp_path):
    profile_path = tmp_path / ".gedos" / "GEDOS.md"

    with patch("interfaces.cli.get_gedos_md_path", return_value=profile_path):
        created = cli_module._ensure_gedos_md("Santiago", "you", "default")

    assert created == profile_path
    content = profile_path.read_text(encoding="utf-8")
    assert "name: Santiago" in content
    assert "refer_as: you" in content
    assert "level: default" in content


def test_cli_run_command_routes_task_through_orchestrator():
    with patch("interfaces.cli.run_task_with_langgraph", return_value={"result": "Done"}):
        response, voice_enabled = cli_module._run_command("/task ls", False)

    assert response == "Done"
    assert voice_enabled is False


def test_cli_voice_on_plays_local_audio():
    with patch("interfaces.cli.play_voice_response_locally") as play_voice:
        response, voice_enabled = cli_module._run_command("/voice on", False)

    play_voice.assert_called_once()
    assert response.startswith("Voice mode enabled")
    assert voice_enabled is True
