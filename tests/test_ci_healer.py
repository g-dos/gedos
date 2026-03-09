"""Tests for the CI healer core."""

from pathlib import Path
from types import SimpleNamespace
import io
import zipfile

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


def test_github_config_applies_env_override(monkeypatch):
    monkeypatch.setattr(
        ci_healer,
        "load_config",
        lambda: {"github": {"webhook_port": 9000, "auto_fix": False, "pr_label": "custom"}},
    )
    monkeypatch.setenv("GITHUB_WEBHOOK_PORT", "9876")
    cfg = ci_healer._github_config()
    assert cfg["webhook_port"] == 9876
    assert cfg["auto_fix"] is False
    assert cfg["pr_label"] == "custom"


def test_github_token_missing_raises(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(ValueError):
        ci_healer._github_token()


def test_fetch_failure_logs_plain_and_zip(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")

    class _Response:
        def __init__(self, content_type, content):
            self.headers = {"content-type": content_type}
            self.content = content

        def raise_for_status(self):
            return None

    plain_body = b"plain logs"
    monkeypatch.setattr(ci_healer.requests, "get", lambda *args, **kwargs: _Response("text/plain", plain_body))
    assert ci_healer._fetch_failure_logs(_context()) == "plain logs"

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        zf.writestr("a.txt", "zip logs")
    zip_content = zip_buf.getvalue()
    monkeypatch.setattr(
        ci_healer.requests,
        "get",
        lambda *args, **kwargs: _Response("application/zip", zip_content),
    )
    assert "zip logs" in ci_healer._fetch_failure_logs(_context())


def test_trim_excerpt_and_clean_llm_output():
    assert ci_healer._trim_log_excerpt("abc", max_chars=10) == "abc"
    assert ci_healer._trim_log_excerpt("x" * 20, max_chars=5) == "xxxxx"
    assert ci_healer._clean_llm_file_output("```py\nprint('x')\n```") == "print('x')"


def test_parse_failure_details_alternative_patterns():
    js_log = "src/app.ts:45:9: TypeError"
    parsed = ci_healer._parse_failure_details(js_log)
    assert parsed is not None
    assert parsed.file_path == "src/app.ts"
    assert parsed.line_number == 45
    assert parsed.error_type == "TypeError"

    failed_log = "FAILED tests/test_core.py::test_x"
    parsed2 = ci_healer._parse_failure_details(failed_log)
    assert parsed2 is not None
    assert parsed2.file_path == "tests/test_core.py"

    generic = "RuntimeError happened"
    parsed3 = ci_healer._parse_failure_details(generic)
    assert parsed3 is not None
    assert parsed3.error_type == "RuntimeError"

    assert ci_healer._parse_failure_details("all good") is None


def test_suggest_fixed_file_content_uses_llm(monkeypatch, tmp_path):
    target = tmp_path / "m.py"
    target.write_text("print('bad')", encoding="utf-8")
    failure = ci_healer.ParsedFailure("m.py", 3, "ValueError", "trace")
    monkeypatch.setattr(ci_healer, "complete", lambda *args, **kwargs: "```py\nprint('fixed')\n```")
    out = ci_healer._suggest_fixed_file_content(target, "print('bad')", failure, _context())
    assert out == "print('fixed')"


def test_write_file_via_terminal_agent_success_and_failure(monkeypatch, tmp_path):
    target = tmp_path / "file.py"

    monkeypatch.setattr(
        ci_healer,
        "run_command",
        lambda *args, **kwargs: SimpleNamespace(success=True, stderr="", stdout=""),
    )
    assert ci_healer._write_file_via_terminal_agent(target, "print('x')\n") is True

    monkeypatch.setattr(
        ci_healer,
        "run_command",
        lambda *args, **kwargs: SimpleNamespace(success=False, stderr="err", stdout=""),
    )
    assert ci_healer._write_file_via_terminal_agent(target, "print('x')\n") is False


def test_authenticated_clone_url():
    assert ci_healer._authenticated_clone_url("https://github.com/g-dos/gedos.git", "tok").startswith(
        "https://x-access-token:tok@"
    )
    assert ci_healer._authenticated_clone_url("git@github.com:g-dos/gedos.git", "tok").startswith("git@")


def test_prepare_checkout_success(monkeypatch, tmp_path):
    repo = SimpleNamespace(clone_url="https://github.com/g-dos/gedos.git", name="gedos")
    monkeypatch.setattr(ci_healer, "_github_client", lambda: SimpleNamespace(get_repo=lambda _: repo))
    monkeypatch.setattr(ci_healer, "_github_token", lambda: "tok")
    monkeypatch.setattr(ci_healer.tempfile, "mkdtemp", lambda prefix="": str(tmp_path))
    monkeypatch.setattr(
        ci_healer,
        "run_command",
        lambda *args, **kwargs: SimpleNamespace(success=True, stdout="", stderr=""),
    )

    out_repo, checkout_dir = ci_healer._prepare_checkout(_context())
    assert out_repo is repo
    assert checkout_dir == tmp_path / "gedos"


def test_prepare_checkout_fetch_failure_raises(monkeypatch, tmp_path):
    repo = SimpleNamespace(clone_url="https://github.com/g-dos/gedos.git", name="gedos")
    monkeypatch.setattr(ci_healer, "_github_client", lambda: SimpleNamespace(get_repo=lambda _: repo))
    monkeypatch.setattr(ci_healer, "_github_token", lambda: "tok")
    monkeypatch.setattr(ci_healer.tempfile, "mkdtemp", lambda prefix="": str(tmp_path))
    calls = {"n": 0}

    def _run(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            return SimpleNamespace(success=False, stdout="", stderr="fetch failed")
        return SimpleNamespace(success=True, stdout="", stderr="")

    monkeypatch.setattr(ci_healer, "run_command", _run)
    with pytest.raises(RuntimeError):
        ci_healer._prepare_checkout(_context())


def test_resolve_target_file_matches_by_name(tmp_path):
    repo_dir = tmp_path / "repo"
    nested = repo_dir / "pkg"
    nested.mkdir(parents=True)
    target = nested / "example.py"
    target.write_text("x=1", encoding="utf-8")
    failure = ci_healer.ParsedFailure("missing/example.py", 1, "Error", "")
    resolved = ci_healer._resolve_target_file(repo_dir, failure)
    assert resolved == target.resolve()


def test_validate_suggested_fix_rules():
    big = "a" * (1024 * 1024 + 1)
    with pytest.raises(ci_healer.SecurityError):
        ci_healer._validate_suggested_fix(big)
    with pytest.raises(ci_healer.SecurityError):
        ci_healer._validate_suggested_fix("import os\nos.system('id')\n")
    ci_healer._validate_suggested_fix("print('safe')")


def test_run_validation_tests_pass_and_fail(monkeypatch):
    outcomes = iter(
        [
            SimpleNamespace(success=False),
            SimpleNamespace(success=True),
        ]
    )
    monkeypatch.setattr(ci_healer, "run_command", lambda *args, **kwargs: next(outcomes))
    assert ci_healer._run_validation_tests(Path(".")) is True

    monkeypatch.setattr(
        ci_healer,
        "run_command",
        lambda *args, **kwargs: SimpleNamespace(success=False),
    )
    assert ci_healer._run_validation_tests(Path(".")) is False


def test_create_pr_opens_and_labels(monkeypatch, tmp_path):
    created = {}
    labels = []

    class _PR:
        number = 99
        html_url = "https://example.com/pr/99"

        def add_to_labels(self, label):
            labels.append(label)

    class _Repo:
        def create_pull(self, **kwargs):
            created.update(kwargs)
            return _PR()

    monkeypatch.setattr(ci_healer, "_github_config", lambda: {"pr_label": "gedos-bot"})
    monkeypatch.setattr(
        ci_healer,
        "run_command",
        lambda *args, **kwargs: SimpleNamespace(success=True, stdout="", stderr=""),
    )
    number, url = ci_healer._create_pr(_Repo(), tmp_path, _context(), ci_healer.ParsedFailure("a.py", 1, "ValueError", ""))
    assert number == 99
    assert url.endswith("/99")
    assert created["base"] == "main"
    assert created["title"].startswith("fix: auto-heal")
    assert labels == ["gedos-bot"]


def test_create_pr_raises_when_git_commands_fail(monkeypatch, tmp_path):
    class _Repo:
        def create_pull(self, **kwargs):
            raise AssertionError("should not be called")

    monkeypatch.setattr(ci_healer, "_github_config", lambda: {"pr_label": "gedos-bot"})
    monkeypatch.setattr(
        ci_healer,
        "run_command",
        lambda *args, **kwargs: SimpleNamespace(success=False, stdout="", stderr=""),
    )
    with pytest.raises(RuntimeError):
        ci_healer._create_pr(_Repo(), tmp_path, _context(), ci_healer.ParsedFailure("a.py", 1, "ValueError", ""))


def test_latest_chat_id_and_language(monkeypatch):
    class _Query:
        def order_by(self, *args, **kwargs):
            return self

        def first(self):
            return SimpleNamespace(user_id="321")

    class _Session:
        def query(self, *args, **kwargs):
            return _Query()

    class _Ctx:
        def __enter__(self):
            return _Session()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(ci_healer, "memory_init_db", lambda: None)
    monkeypatch.setattr(ci_healer, "get_session", lambda: _Ctx())
    assert ci_healer._latest_telegram_chat_id() == "321"
    monkeypatch.setattr(ci_healer, "get_user_language", lambda user_id: "pt")
    assert ci_healer._latest_telegram_language("321") == "pt"
    assert ci_healer._latest_telegram_language(None) == "en"


def test_notify_user_skips_without_token_or_chat(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setattr(ci_healer, "_latest_telegram_chat_id", lambda: None)
    called = {"value": False}
    monkeypatch.setattr(ci_healer.requests, "post", lambda *args, **kwargs: called.__setitem__("value", True))
    ci_healer._notify_user("hello")
    assert called["value"] is False


def test_notify_user_posts_when_available(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setattr(ci_healer, "_latest_telegram_chat_id", lambda: "123")
    payloads = []
    monkeypatch.setattr(ci_healer.requests, "post", lambda *args, **kwargs: payloads.append((args, kwargs)))
    ci_healer._notify_user("hello")
    assert payloads


def test_handle_ci_failure_auto_fix_disabled(monkeypatch):
    actions = []
    monkeypatch.setattr(ci_healer, "log_action", lambda *args, **kwargs: actions.append((args, kwargs)))
    monkeypatch.setattr(
        ci_healer,
        "_github_config",
        lambda: {"auto_fix": False, "auto_pr": True, "notify_on_failure": True, "webhook_port": 9876, "pr_label": "gedos-bot"},
    )
    ci_healer.handle_ci_failure(_context())
    assert any(call[0][3] == "skipped_auto_fix_disabled" for call in actions)
