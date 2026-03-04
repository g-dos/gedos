"""Tests for the CI healer core."""

from pathlib import Path
from types import SimpleNamespace

import pytest

import core.ci_healer as ci_healer


def _context() -> ci_healer.CIFailureContext:
    return ci_healer.CIFailureContext(
        repo_full_name="g-dos/gedos",
        branch="main",
        commit_sha="abc123def456",
        workflow_name="CI",
        failure_logs_url="https://example.com/logs",
    )


def test_failure_log_parsing_extracts_file_and_error_correctly():
    log_text = (
        'Traceback (most recent call last):\n'
        '  File "core/example.py", line 27, in <module>\n'
        "    boom()\n"
        "ValueError: broken\n"
    )

    parsed = ci_healer._parse_failure_details(log_text)

    assert parsed is not None
    assert parsed.file_path == "core/example.py"
    assert parsed.line_number == 27
    assert parsed.error_type == "ValueError"


def test_llm_fix_is_applied_to_correct_file(monkeypatch, tmp_path):
    target = tmp_path / "core" / "example.py"
    target.parent.mkdir(parents=True)
    target.write_text("print('broken')\n", encoding="utf-8")
    repo_dir = tmp_path
    write_calls = []

    monkeypatch.setattr(ci_healer, "_github_config", lambda: {"auto_fix": True, "auto_pr": True, "notify_on_failure": True, "webhook_port": 9876})
    monkeypatch.setattr(ci_healer, "_latest_telegram_chat_id", lambda: "123")
    monkeypatch.setattr(ci_healer, "_latest_telegram_language", lambda chat_id: "en")
    monkeypatch.setattr(ci_healer, "_fetch_failure_logs", lambda context: "ValueError: broken")
    monkeypatch.setattr(
        ci_healer,
        "_parse_failure_details",
        lambda logs: ci_healer.ParsedFailure(
            file_path="core/example.py",
            line_number=27,
            error_type="ValueError",
            log_excerpt=logs,
        ),
    )
    monkeypatch.setattr(ci_healer, "_prepare_checkout", lambda context: (SimpleNamespace(), repo_dir))
    monkeypatch.setattr(ci_healer, "_resolve_target_file", lambda repo, failure: target)
    monkeypatch.setattr(ci_healer, "_suggest_fixed_file_content", lambda *args: "print('fixed')\n")
    monkeypatch.setattr(ci_healer, "_run_validation_tests", lambda repo: True)
    monkeypatch.setattr(ci_healer, "_create_pr", lambda *args: (12, "https://example.com/pr/12"))
    monkeypatch.setattr(ci_healer, "_notify_user", lambda message: None)

    def fake_write(path: Path, content: str) -> bool:
        write_calls.append((path, content))
        path.write_text(content, encoding="utf-8")
        return True

    monkeypatch.setattr(ci_healer, "_write_file_via_terminal_agent", fake_write)

    ci_healer.handle_ci_failure(_context())

    assert write_calls == [(target, "print('fixed')\n")]
    assert target.read_text(encoding="utf-8") == "print('fixed')\n"


def test_if_local_tests_pass_after_fix_pr_is_opened(monkeypatch, tmp_path):
    target = tmp_path / "module.py"
    target.write_text("bad = True\n", encoding="utf-8")
    repo_dir = tmp_path
    pr_calls = []
    notifications = []

    monkeypatch.setattr(ci_healer, "_github_config", lambda: {"auto_fix": True, "auto_pr": True, "notify_on_failure": True, "webhook_port": 9876})
    monkeypatch.setattr(ci_healer, "_latest_telegram_chat_id", lambda: "123")
    monkeypatch.setattr(ci_healer, "_latest_telegram_language", lambda chat_id: "en")
    monkeypatch.setattr(ci_healer, "_fetch_failure_logs", lambda context: "RuntimeError: boom")
    monkeypatch.setattr(
        ci_healer,
        "_parse_failure_details",
        lambda logs: ci_healer.ParsedFailure(file_path="module.py", line_number=9, error_type="RuntimeError", log_excerpt=logs),
    )
    monkeypatch.setattr(ci_healer, "_prepare_checkout", lambda context: (SimpleNamespace(), repo_dir))
    monkeypatch.setattr(ci_healer, "_resolve_target_file", lambda repo, failure: target)
    monkeypatch.setattr(ci_healer, "_suggest_fixed_file_content", lambda *args: "bad = False\n")
    monkeypatch.setattr(ci_healer, "_write_file_via_terminal_agent", lambda path, content: path.write_text(content, encoding="utf-8") or True)
    monkeypatch.setattr(ci_healer, "_run_validation_tests", lambda repo: True)
    monkeypatch.setattr(ci_healer, "_notify_user", lambda message: notifications.append(message))

    def fake_create_pr(*args):
        pr_calls.append(args)
        return 7, "https://example.com/pr/7"

    monkeypatch.setattr(ci_healer, "_create_pr", fake_create_pr)

    ci_healer.handle_ci_failure(_context())

    assert len(pr_calls) == 1
    assert notifications
    assert "PR #7 opened" in notifications[0]


def test_if_local_tests_fail_after_fix_user_notified_no_pr_opened(monkeypatch, tmp_path):
    target = tmp_path / "module.py"
    target.write_text("bad = True\n", encoding="utf-8")
    repo_dir = tmp_path
    notifications = []
    pr_called = {"value": False}

    monkeypatch.setattr(ci_healer, "_github_config", lambda: {"auto_fix": True, "auto_pr": True, "notify_on_failure": True, "webhook_port": 9876})
    monkeypatch.setattr(ci_healer, "_latest_telegram_chat_id", lambda: "123")
    monkeypatch.setattr(ci_healer, "_latest_telegram_language", lambda chat_id: "en")
    monkeypatch.setattr(ci_healer, "_fetch_failure_logs", lambda context: "RuntimeError: boom")
    monkeypatch.setattr(
        ci_healer,
        "_parse_failure_details",
        lambda logs: ci_healer.ParsedFailure(file_path="module.py", line_number=9, error_type="RuntimeError", log_excerpt=logs),
    )
    monkeypatch.setattr(ci_healer, "_prepare_checkout", lambda context: (SimpleNamespace(), repo_dir))
    monkeypatch.setattr(ci_healer, "_resolve_target_file", lambda repo, failure: target)
    monkeypatch.setattr(ci_healer, "_suggest_fixed_file_content", lambda *args: "bad = False\n")
    monkeypatch.setattr(ci_healer, "_write_file_via_terminal_agent", lambda path, content: path.write_text(content, encoding="utf-8") or True)
    monkeypatch.setattr(ci_healer, "_run_validation_tests", lambda repo: False)
    monkeypatch.setattr(ci_healer, "_notify_user", lambda message: notifications.append(message))

    def fake_create_pr(*args):
        pr_called["value"] = True
        return 9, "https://example.com/pr/9"

    monkeypatch.setattr(ci_healer, "_create_pr", fake_create_pr)

    ci_healer.handle_ci_failure(_context())

    assert pr_called["value"] is False
    assert notifications
    assert "Could not auto-fix. Review needed." in notifications[0]


def test_resolve_target_file_blocks_paths_outside_repo(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    failure = ci_healer.ParsedFailure(
        file_path="../../../../../../etc/passwd",
        line_number=1,
        error_type="PermissionError",
        log_excerpt="",
    )

    with pytest.raises(ci_healer.SecurityError):
        ci_healer._resolve_target_file(repo_dir, failure)


def test_unsafe_llm_fix_is_rejected_before_write(monkeypatch, tmp_path):
    target = tmp_path / "module.py"
    target.write_text("bad = True\n", encoding="utf-8")
    repo_dir = tmp_path
    notifications = []
    write_called = {"value": False}

    monkeypatch.setattr(ci_healer, "_github_config", lambda: {"auto_fix": True, "auto_pr": True, "notify_on_failure": True, "webhook_port": 9876})
    monkeypatch.setattr(ci_healer, "_latest_telegram_chat_id", lambda: "123")
    monkeypatch.setattr(ci_healer, "_latest_telegram_language", lambda chat_id: "en")
    monkeypatch.setattr(ci_healer, "_fetch_failure_logs", lambda context: "RuntimeError: boom")
    monkeypatch.setattr(
        ci_healer,
        "_parse_failure_details",
        lambda logs: ci_healer.ParsedFailure(file_path="module.py", line_number=9, error_type="RuntimeError", log_excerpt=logs),
    )
    monkeypatch.setattr(ci_healer, "_prepare_checkout", lambda context: (SimpleNamespace(), repo_dir))
    monkeypatch.setattr(ci_healer, "_resolve_target_file", lambda repo, failure: target)
    monkeypatch.setattr(ci_healer, "_suggest_fixed_file_content", lambda *args: "import os\nos.system('rm -rf ~')\n")
    monkeypatch.setattr(ci_healer, "_notify_user", lambda message: notifications.append(message))
    monkeypatch.setattr(ci_healer, "_run_validation_tests", lambda repo: True)
    monkeypatch.setattr(ci_healer, "_create_pr", lambda *args: (5, "https://example.com/pr/5"))

    def fake_write(path: Path, content: str) -> bool:
        write_called["value"] = True
        return True

    monkeypatch.setattr(ci_healer, "_write_file_via_terminal_agent", fake_write)

    ci_healer.handle_ci_failure(_context())

    assert write_called["value"] is False
    assert notifications == [ci_healer._UNSAFE_FIX_MESSAGE]


def test_telegram_notification_sent_in_both_success_and_failure_cases(monkeypatch, tmp_path):
    target = tmp_path / "module.py"
    target.write_text("bad = True\n", encoding="utf-8")
    repo_dir = tmp_path
    notifications = []
    validation_results = iter([True, False])

    monkeypatch.setattr(ci_healer, "_github_config", lambda: {"auto_fix": True, "auto_pr": True, "notify_on_failure": True, "webhook_port": 9876})
    monkeypatch.setattr(ci_healer, "_latest_telegram_chat_id", lambda: "123")
    monkeypatch.setattr(ci_healer, "_latest_telegram_language", lambda chat_id: "en")
    monkeypatch.setattr(ci_healer, "_fetch_failure_logs", lambda context: "RuntimeError: boom")
    monkeypatch.setattr(
        ci_healer,
        "_parse_failure_details",
        lambda logs: ci_healer.ParsedFailure(file_path="module.py", line_number=9, error_type="RuntimeError", log_excerpt=logs),
    )
    monkeypatch.setattr(ci_healer, "_prepare_checkout", lambda context: (SimpleNamespace(), repo_dir))
    monkeypatch.setattr(ci_healer, "_resolve_target_file", lambda repo, failure: target)
    monkeypatch.setattr(ci_healer, "_suggest_fixed_file_content", lambda *args: "bad = False\n")
    monkeypatch.setattr(ci_healer, "_write_file_via_terminal_agent", lambda path, content: path.write_text(content, encoding="utf-8") or True)
    monkeypatch.setattr(ci_healer, "_run_validation_tests", lambda repo: next(validation_results))
    monkeypatch.setattr(ci_healer, "_create_pr", lambda *args: (5, "https://example.com/pr/5"))
    monkeypatch.setattr(ci_healer, "_notify_user", lambda message: notifications.append(message))

    ci_healer.handle_ci_failure(_context())
    ci_healer.handle_ci_failure(_context())

    assert len(notifications) == 2
    assert "PR #5 opened" in notifications[0]
    assert "Could not auto-fix. Review needed." in notifications[1]
