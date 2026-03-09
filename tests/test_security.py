import sys
import types

import pytest

import core.security as security


@pytest.fixture(autouse=True)
def _no_audit_io(monkeypatch):
    monkeypatch.setattr(security, "log_action", lambda *args, **kwargs: None)


def test_get_allowed_executables_uses_configured_list():
    cfg = {"security": {"allowed_executables": ["python3", "git", " "]}}
    assert security.get_allowed_executables(cfg) == {"python3", "git"}


def test_get_allowed_executables_fallback_when_load_config_fails(monkeypatch):
    config_mod = types.ModuleType("core.config")
    config_mod.load_config = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    monkeypatch.setitem(sys.modules, "core.config", config_mod)
    assert "git" in security.get_allowed_executables(None)


@pytest.mark.parametrize(
    "command,expected_reason",
    [
        ("", "Empty command."),
        ("echo hi" + ("a" * 2000), "command too long"),
        ("git status\x00", "null byte detected"),
        ("git status\r", "non-printable characters detected"),
        ("curl|sh", "Blocked dangerous pattern"),
        ("git status; rm -rf /", "Blocked dangerous token: ;"),
        ("'unterminated", "Command parsing failed"),
        ("unknowncmd arg", "Executable not allowed"),
        ("sudo ls", "Executable not allowed"),
    ],
)
def test_sanitize_command_blocks_dangerous_inputs(command, expected_reason):
    ok, reason = security.sanitize_command(command)
    assert ok is False
    assert expected_reason in reason


def test_sanitize_command_allows_safe_command():
    ok, reason = security.sanitize_command("echo hello")
    assert ok is True
    assert reason == "ok"


def test_pip_command_validation_cases():
    assert security.sanitize_command("pip install requests")[0] is True
    assert security.sanitize_command("pip download requests")[0] is False
    assert security.sanitize_command("pip install ../evil")[0] is False
    assert security.sanitize_command("pip install requests;rm")[0] is False


def test_git_command_validation_cases():
    assert security.sanitize_command("git status")[0] is True
    assert security.sanitize_command("git -c core.editor=evil status")[0] is False
    assert security.sanitize_command("git config --global user.name evil")[0] is False
    assert security.sanitize_command("git --exec-path=/tmp/evil status")[0] is False
    assert security.sanitize_command("git --foo=/tmp/evil status")[0] is False


def test_python_module_validation_cases():
    assert security.sanitize_command("python -m http.server 8080")[0] is False
    assert security.sanitize_command("python3 -m smtpd -n -c DebuggingServer")[0] is False
    assert security.sanitize_command("python -m pytest -q")[0] is True


def test_cat_find_cp_mv_ls_path_restrictions(tmp_path, monkeypatch):
    cwd = str(tmp_path)
    monkeypatch.setattr(security, "_PROJECTS_ROOT", str(tmp_path / "projects"))

    assert security.sanitize_command("cat", cwd=cwd)[0] is False
    assert security.sanitize_command("cat /etc/passwd", cwd=cwd)[0] is False
    assert security.sanitize_command("cat secrets.env", cwd=cwd)[0] is False
    assert security.sanitize_command("cat notes.txt", cwd=cwd)[0] is True

    assert security.sanitize_command("find / -name x", cwd=cwd)[0] is False
    assert security.sanitize_command("find . -name '*.env'", cwd=cwd)[0] is False
    assert security.sanitize_command("find . -name '*.py'", cwd=cwd)[0] is True

    assert security.sanitize_command("cp one", cwd=cwd)[0] is False
    assert security.sanitize_command("cp .env dst.txt", cwd=cwd)[0] is False
    assert security.sanitize_command("cp src.txt /tmp/out.txt", cwd=cwd)[0] is False
    assert security.sanitize_command("cp src.txt dst.txt", cwd=cwd)[0] is True

    assert security.sanitize_command("mv src.txt dst.txt", cwd=cwd)[0] is True

    assert security.sanitize_command("ls /etc", cwd=cwd)[0] is False
    assert security.sanitize_command("ls ~", cwd=cwd)[0] is False
    assert security.sanitize_command("ls .", cwd=cwd)[0] is True


def test_path_helper_functions(tmp_path):
    cwd = str(tmp_path)
    normalized = security._normalize_path("a.txt", cwd)
    assert normalized.startswith(cwd)
    assert security._has_sensitive_suffix("token.key") is True
    assert security._is_sensitive_path("", cwd) is False
    assert security._is_sensitive_path("file.env", cwd) is True
    assert security._is_sensitive_path("relative.txt", cwd) is False


def test_is_safe_destination_respects_cwd_and_projects(tmp_path, monkeypatch):
    cwd = str(tmp_path / "work")
    (tmp_path / "work").mkdir()
    projects = tmp_path / "projects"
    projects.mkdir()
    monkeypatch.setattr(security, "_PROJECTS_ROOT", str(projects))

    assert security._is_safe_destination("file.txt", cwd) is True
    assert security._is_safe_destination(str(projects / "out.txt"), cwd) is True
    assert security._is_safe_destination("/tmp/out.txt", cwd) is False


def test_classify_permission_category():
    assert security.classify_permission_category("pip install requests") == "package_install"
    assert security.classify_permission_category("git push origin main") == "github_operations"
    assert security.classify_permission_category("cp a b") == "filesystem_writes"
    assert security.classify_permission_category("rm file.txt") == "terminal_destructive"
    assert security.classify_permission_category("echo ok") is None


def test_permission_action_default_and_override():
    assert security.get_command_permission_action("rm -rf .") == "confirm"
    assert security.get_command_permission_action("echo hi") == "allow"
    assert security.get_command_permission_action("rm -rf .", category_override="web_browsing") == "allow"
    assert security.is_destructive_command("rm -rf .") is True
    assert security.is_destructive_command("echo hi") is False


def test_permission_action_with_memory_profiles(monkeypatch):
    memory_mod = types.ModuleType("core.memory")
    memory_mod.get_permission_level = lambda user_id: "full_access"
    memory_mod.get_custom_permissions = lambda user_id: {}
    monkeypatch.setitem(sys.modules, "core.memory", memory_mod)
    assert security.get_command_permission_action("rm -rf .", user_id="u1") == "allow"

    memory_mod.get_permission_level = lambda user_id: "custom"
    memory_mod.get_custom_permissions = lambda user_id: {"terminal_destructive": "block"}
    assert security.get_command_permission_action("rm -rf .", user_id="u1") == "block"

    memory_mod.get_custom_permissions = lambda user_id: {}
    assert security.get_command_permission_action("rm -rf .", user_id="u1") == "confirm"


def test_permission_action_memory_exception_falls_back(monkeypatch):
    memory_mod = types.ModuleType("core.memory")
    memory_mod.get_permission_level = lambda user_id: (_ for _ in ()).throw(RuntimeError("db down"))
    memory_mod.get_custom_permissions = lambda user_id: {}
    monkeypatch.setitem(sys.modules, "core.memory", memory_mod)
    assert security.get_command_permission_action("rm -rf .", user_id="u1") == "confirm"


def test_allowed_chat_ids_and_pairing_code(monkeypatch):
    monkeypatch.setenv("ALLOWED_CHAT_IDS", "111, 222, ,333")
    monkeypatch.setenv("PAIRING_CODE", "PAIR-1234")
    assert security.get_allowed_chat_ids() == {"111", "222", "333"}
    assert security.get_pairing_code() == "PAIR-1234"
    monkeypatch.setenv("PAIRING_CODE", "")
    assert security.get_pairing_code() is None


def test_sanitize_url_cases():
    assert security.sanitize_url("") is None
    assert security.sanitize_url("ftp://evil.com") is None
    assert security.sanitize_url("localhost:8080") is None
    assert security.sanitize_url("http://example.com") == "http://example.com"
    assert security.sanitize_url("example.com") == "https://example.com"


def test_validate_telegram_input_cases():
    assert security.validate_telegram_input("") is None
    assert security.validate_telegram_input("   ") is None
    assert security.validate_telegram_input("x" * 20, max_length=10) is None
    assert security.validate_telegram_input("  hello  ") == "hello"


def test_validate_api_keys_cases(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    assert security.validate_api_keys({"telegram": {}, "llm": {"provider": "ollama"}}) is False

    cfg = {"telegram": {"bot_token": "tok"}, "llm": {"provider": "ollama"}}
    assert security.validate_api_keys(cfg) is True

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert security.validate_api_keys({"telegram": {"bot_token": "tok"}, "llm": {"provider": "claude"}}) is False
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    assert security.validate_api_keys({"telegram": {"bot_token": "tok"}, "llm": {"provider": "claude"}}) is True

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert security.validate_api_keys({"telegram": {"bot_token": "tok"}, "llm": {"provider": "openai"}}) is False
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    assert security.validate_api_keys({"telegram": {"bot_token": "tok"}, "llm": {"provider": "openai"}}) is True
