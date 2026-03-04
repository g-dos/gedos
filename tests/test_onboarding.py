"""Tests for CLI onboarding and LLM setup flow."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from interfaces import cli as cli_module


def test_llm_detection_checks_ollama_correctly():
    with patch("interfaces.cli.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout="Ollama is running")) as run_cmd:
        assert cli_module._ollama_running() is True

    run_cmd.assert_called_once()
    assert run_cmd.call_args.args[0] == ["curl", "-s", "http://localhost:11434"]


def test_missing_ollama_shows_correct_instructions():
    with patch("interfaces.cli._ollama_running", return_value=False):
        with patch("interfaces.cli._ollama_has_model", return_value=False):
            with patch("builtins.input", side_effect=["2", "anthropic-test-key"]):
                with patch("interfaces.cli.write_env_value"):
                    with patch("builtins.print") as print_mock:
                        cli_module._ensure_llm_available()

    rendered = "".join(call.args[0] for call in print_mock.call_args_list if call.args)
    assert "No LLM configured" in rendered
    assert "Install Ollama" in rendered
    assert "Use Claude API" in rendered


def test_api_key_saved_to_env_when_provided():
    with patch("interfaces.cli._ollama_running", return_value=False):
        with patch("interfaces.cli._ollama_has_model", return_value=False):
            with patch("builtins.input", side_effect=["2", "anthropic-test-key"]):
                with patch("interfaces.cli.write_env_value") as write_env:
                    cli_module._ensure_llm_available()

    assert write_env.call_args_list[0].args == ("LLM_PROVIDER", "claude")
    assert write_env.call_args_list[1].args == ("ANTHROPIC_API_KEY", "anthropic-test-key")


def test_name_and_refer_as_saved_to_user_context():
    inputs = ["Santiago", "", "2", "Master Santiago", "1", "", "n"]

    with patch("interfaces.cli._ensure_llm_available"):
        with patch("builtins.input", side_effect=inputs):
            with patch("interfaces.cli._ensure_gedos_md", return_value=MagicMock()):
                with patch("interfaces.cli.add_context") as add_context:
                    with patch("interfaces.cli.update_config"):
                        with patch("interfaces.cli.set_permission_level"):
                            with patch("builtins.print"):
                                cli_module._run_onboarding()

    add_context.assert_called_once_with(
        "cli_profile",
        {"user_id": cli_module.CLI_USER_ID, "name": "Santiago", "refer_as": "Master Santiago"},
        user_id=cli_module.CLI_USER_ID,
    )


def test_permission_level_saved_correctly():
    inputs = ["Santiago", "", "1", "3", "", "n"]

    with patch("interfaces.cli._ensure_llm_available"):
        with patch("builtins.input", side_effect=inputs):
            with patch("interfaces.cli._ensure_gedos_md", return_value=MagicMock()):
                with patch("interfaces.cli.add_context"):
                    with patch("interfaces.cli.update_config") as update_config:
                        with patch("interfaces.cli.set_permission_level") as set_permission:
                            with patch("builtins.print"):
                                cli_module._run_onboarding()

    update_config.assert_called_once_with({"security": {"strict_shell": False}})
    set_permission.assert_called_once_with(cli_module.CLI_USER_ID, "full_access")


def test_telegram_token_saved_to_env_when_provided():
    inputs = ["Santiago", "", "1", "1", "telegram-token", "n"]

    with patch("interfaces.cli._ensure_llm_available"):
        with patch("builtins.input", side_effect=inputs):
            with patch("interfaces.cli._ensure_gedos_md", return_value=MagicMock()):
                with patch("interfaces.cli.add_context"):
                    with patch("interfaces.cli.update_config"):
                        with patch("interfaces.cli.set_permission_level"):
                            with patch("interfaces.cli.write_env_value") as write_env:
                                with patch("builtins.print"):
                                    cli_module._run_onboarding()

    write_env.assert_called_once_with("TELEGRAM_BOT_TOKEN", "telegram-token")
