"""Smoke tests for agents.terminal_agent."""

from agents.terminal_agent import run_command, run_shell, TerminalResult


def test_run_command_echo():
    r = run_command("echo hello")
    assert r.success is True
    assert "hello" in r.stdout
    assert r.return_code == 0


def test_run_command_failure():
    r = run_command("false")
    assert r.success is False
    assert r.return_code != 0


def test_run_command_empty():
    r = run_command("")
    assert r.success is False
    assert "Empty" in r.stderr


def test_run_shell_echo():
    r = run_shell("echo world")
    assert r.success is True
    assert "world" in r.stdout


def test_run_shell_pipeline():
    r = run_shell("echo abc | tr a-z A-Z")
    assert r.success is True
    assert "ABC" in r.stdout


def test_run_command_timeout():
    r = run_command("sleep 5", timeout_seconds=1)
    assert r.success is False
    assert "tempo limite" in r.stderr.lower() or "timed out" in r.stderr.lower()


def test_terminal_result_fields():
    r = run_command("pwd")
    assert isinstance(r, TerminalResult)
    assert isinstance(r.command, str)
    assert isinstance(r.stdout, str)
    assert isinstance(r.stderr, str)
    assert isinstance(r.return_code, int)
