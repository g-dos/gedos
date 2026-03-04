"""Tests for the GitHub webhook receiver."""

import hashlib
import hmac

import core.github_webhook as github_webhook


def _reset_webhook_state():
    github_webhook._RECENT_DELIVERIES.clear()
    github_webhook._RECENT_DELIVERY_SET.clear()
    github_webhook._REQUEST_TIMESTAMPS.clear()


def _signature(secret: str, payload: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_webhook_validates_github_signature_correctly(monkeypatch):
    payload = b'{"hello":"world"}'
    monkeypatch.setattr(github_webhook, "_webhook_secret", lambda: "secret123")

    assert github_webhook._signature_is_valid(payload, _signature("secret123", payload)) is True


def test_invalid_signature_returns_403(monkeypatch):
    _reset_webhook_state()
    app = github_webhook.create_webhook_app()
    client = app.test_client()
    payload = b'{"workflow_run":{"conclusion":"failure"}}'
    monkeypatch.setattr(github_webhook, "_webhook_secret", lambda: "secret123")

    response = client.post(
        "/webhook",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "workflow_run",
            "X-Hub-Signature-256": "sha256=bad",
        },
    )

    assert response.status_code == 403


def test_non_failure_workflow_run_event_is_ignored(monkeypatch):
    _reset_webhook_state()
    app = github_webhook.create_webhook_app()
    client = app.test_client()
    raw_payload = b'{"workflow_run":{"conclusion":"success"}}'
    monkeypatch.setattr(github_webhook, "_webhook_secret", lambda: "secret123")

    response = client.post(
        "/webhook",
        data=raw_payload,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "workflow_run",
            "X-GitHub-Delivery": "non-failure-1",
            "X-Hub-Signature-256": _signature("secret123", raw_payload),
        },
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "ignored"


def test_failure_event_triggers_ci_healer_with_correct_context(monkeypatch):
    _reset_webhook_state()
    app = github_webhook.create_webhook_app()
    client = app.test_client()
    payload = {
        "repository": {"full_name": "g-dos/gedos", "default_branch": "main"},
        "workflow_run": {
            "conclusion": "failure",
            "head_branch": "feature-branch",
            "head_sha": "abc123def456",
            "name": "CI",
            "logs_url": "https://example.com/logs",
            "id": 42,
            "html_url": "https://github.com/g-dos/gedos/actions/runs/42",
        },
    }
    raw_payload = (
        b'{"repository":{"full_name":"g-dos/gedos","default_branch":"main"},'
        b'"workflow_run":{"conclusion":"failure","head_branch":"feature-branch",'
        b'"head_sha":"abc123def456","name":"CI","logs_url":"https://example.com/logs",'
        b'"id":42,"html_url":"https://github.com/g-dos/gedos/actions/runs/42"}}'
    )
    monkeypatch.setattr(github_webhook, "_webhook_secret", lambda: "secret123")
    calls = []

    def fake_healer(context):
        calls.append(context)

    class ImmediateThread:
        def __init__(self, target, args=(), daemon=None):
            self.target = target
            self.args = args
            self.daemon = daemon

        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(github_webhook, "handle_ci_failure", fake_healer)
    monkeypatch.setattr(github_webhook.threading, "Thread", ImmediateThread)

    response = client.post(
        "/webhook",
        data=raw_payload,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "workflow_run",
            "X-GitHub-Delivery": "failure-1",
            "X-Hub-Signature-256": _signature("secret123", raw_payload),
        },
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "accepted"
    assert len(calls) == 1
    context = calls[0]
    assert context.repo_full_name == "g-dos/gedos"
    assert context.branch == "feature-branch"
    assert context.commit_sha == "abc123def456"
    assert context.workflow_name == "CI"
    assert context.failure_logs_url == "https://example.com/logs"
