"""Tests for CLI mode behavior and command handling."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import gedos
from core import config as config_module
from interfaces import cli as cli_module


def test_load_gedos_profile_parses_yaml_like_sections():
    profile_path = MagicMock()
    profile_path.exists.return_value = True
    profile_path.read_text.return_value = (
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
        "- rm -rf /\n"
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


def test_onboarding_runs_on_first_launch():
    with patch("interfaces.cli.init_db"):
        with patch("interfaces.cli._latest_cli_profile", side_effect=[{"name": ""}, {"name": "Santiago"}]):
            with patch("interfaces.cli._is_first_run", return_value=True):
                with patch("interfaces.cli._run_onboarding") as onboarding:
                    with patch("builtins.print") as print_mock:
                        cli_module.run_cli(initial_command="/exit")

    onboarding.assert_called_once()
    print_mock.assert_any_call("Goodbye.")


def test_onboarding_skipped_for_returning_user():
    with patch("interfaces.cli.init_db"):
        with patch("interfaces.cli._latest_cli_profile", return_value={"name": "Santiago"}):
            with patch("interfaces.cli._is_first_run", return_value=False):
                with patch("interfaces.cli._run_onboarding") as onboarding:
                    with patch("builtins.print") as print_mock:
                        cli_module.run_cli(initial_command="/exit")

    onboarding.assert_not_called()
    print_mock.assert_any_call("Hey Santiago 👋")
    print_mock.assert_any_call("Goodbye.")


def test_ensure_gedos_md_creates_template_without_real_writes():
    fake_parent = MagicMock()
    fake_path = MagicMock()
    fake_path.parent = fake_parent
    fake_path.exists.return_value = False

    with patch("interfaces.cli.get_gedos_md_path", return_value=fake_path):
        created = cli_module._ensure_gedos_md("Santiago", "you", "default")

    assert created is fake_path
    fake_parent.mkdir.assert_called_once_with(parents=True, exist_ok=True)
    fake_path.write_text.assert_called_once()
    rendered = fake_path.write_text.call_args.args[0]
    assert "name: Santiago" in rendered
    assert "refer_as: you" in rendered
    assert "level: default" in rendered


def test_gedos_md_name_and_refer_as_are_applied_to_llm_context():
    with patch("core.llm.load_gedos_profile", return_value={"name": "Santiago", "refer_as": "Chief Santiago", "response_style": "concise"}):
        with patch("core.llm.get_llm_config", return_value={"provider": "ollama", "model": "llama3.3", "base_url": "http://localhost:11434"}):
            with patch("core.llm._complete_ollama", return_value="ok") as complete_ollama:
                result = config_module  # keep import used in file
                _ = result  # silence linters in tests
                from core import llm as llm_module

                response = llm_module.complete("hello", language="en")

    assert response == "ok"
    kwargs = complete_ollama.call_args.kwargs
    assert "User name: Santiago" in kwargs["system"]
    assert "Refer to the user as: Chief Santiago" in kwargs["system"]


def test_exit_command_exits_cli_loop_cleanly():
    with patch("interfaces.cli.init_db"):
        with patch("interfaces.cli._latest_cli_profile", return_value={"name": "Santiago"}):
            with patch("interfaces.cli._is_first_run", return_value=False):
                with patch("builtins.print") as print_mock:
                    cli_module.run_cli(initial_command="/exit")

    print_mock.assert_any_call("Goodbye.")


def test_help_output_contains_all_expected_sections():
    with patch("interfaces.cli._latest_cli_profile", return_value={"name": "Santiago"}):
        help_text = cli_module._help_text()

    expected_sections = [
        "TASKS",
        "WEB",
        "LLM",
        "SCHEDULE",
        "MEMORY",
        "COPILOT",
        "GITHUB",
        "VOICE",
        "SYSTEM",
        "MCP",
        "PILOT MODE",
    ]
    for section in expected_sections:
        assert section in help_text
    assert "Hey Santiago" in help_text


def test_permissions_default_sets_correct_permission_level():
    with patch("interfaces.cli.update_config") as update_config:
        with patch("interfaces.cli.set_permission_level") as set_permission:
            response, voice_enabled = cli_module._run_command("/permissions default", False)

    update_config.assert_called_once_with({"security": {"strict_shell": True}})
    set_permission.assert_called_once_with(cli_module.CLI_USER_ID, "default")
    assert response == "Permission level set to Default."
    assert voice_enabled is False


def test_permissions_full_requires_confirmation():
    with patch("builtins.input", return_value="nope"):
        with patch("interfaces.cli._set_permission") as set_permission:
            response, voice_enabled = cli_module._run_command("/permissions full", False)

    set_permission.assert_not_called()
    assert response == "Permission change cancelled."
    assert voice_enabled is False


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
