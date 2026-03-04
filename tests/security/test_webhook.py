"""Security tests for webhook replay protection."""

from datetime import datetime, timedelta, UTC
import hashlib
import hmac
import json

import core.github_webhook as github_webhook


def _signature(secret: str, payload: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _payload(updated_at: str) -> bytes:
    body = {
        "repository": {"full_name": "g-dos/gedos", "default_branch": "main"},
        "workflow_run": {
            "conclusion": "failure",
            "head_branch": "main",
            "head_sha": "abc123",
            "name": "CI",
            "logs_url": "https://example.com/logs",
            "updated_at": updated_at,
        },
    }
    return json.dumps(body).encode("utf-8")


def _reset_webhook_state():
    github_webhook._RECENT_DELIVERIES.clear()
    github_webhook._RECENT_DELIVERY_SET.clear()
    github_webhook._REQUEST_TIMESTAMPS.clear()


def test_duplicate_delivery_id_is_rejected(monkeypatch):
    _reset_webhook_state()
    app = github_webhook.create_webhook_app()
    client = app.test_client()
    now = datetime.now(UTC).isoformat()
    payload = _payload(now)
    monkeypatch.setattr(github_webhook, "_webhook_secret", lambda: "secret123")
    monkeypatch.setattr(github_webhook.threading, "Thread", lambda target, args=(), daemon=None: type("T", (), {"start": lambda self: None})())

    first = client.post(
        "/webhook",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "workflow_run",
            "X-GitHub-Delivery": "delivery-1",
            "X-Hub-Signature-256": _signature("secret123", payload),
        },
    )
    second = client.post(
        "/webhook",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "workflow_run",
            "X-GitHub-Delivery": "delivery-1",
            "X-Hub-Signature-256": _signature("secret123", payload),
        },
    )

    assert first.status_code == 200
    assert second.status_code == 409


def test_event_older_than_five_minutes_is_rejected(monkeypatch):
    _reset_webhook_state()
    app = github_webhook.create_webhook_app()
    client = app.test_client()
    old = (datetime.now(UTC) - timedelta(minutes=6)).isoformat()
    payload = _payload(old)
    monkeypatch.setattr(github_webhook, "_webhook_secret", lambda: "secret123")

    response = client.post(
        "/webhook",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "workflow_run",
            "X-GitHub-Delivery": "delivery-old",
            "X-Hub-Signature-256": _signature("secret123", payload),
        },
    )

    assert response.status_code == 409


def test_rate_limit_returns_429_after_ten_requests_per_minute(monkeypatch):
    _reset_webhook_state()
    app = github_webhook.create_webhook_app()
    client = app.test_client()
    now = datetime.now(UTC).isoformat()
    payload = _payload(now)
    monkeypatch.setattr(github_webhook, "_webhook_secret", lambda: "secret123")
    monkeypatch.setattr(github_webhook.threading, "Thread", lambda target, args=(), daemon=None: type("T", (), {"start": lambda self: None})())

    for idx in range(10):
        response = client.post(
            "/webhook",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "workflow_run",
                "X-GitHub-Delivery": f"delivery-{idx}",
                "X-Hub-Signature-256": _signature("secret123", payload),
            },
        )
        assert response.status_code == 200

    limited = client.post(
        "/webhook",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "workflow_run",
            "X-GitHub-Delivery": "delivery-11",
            "X-Hub-Signature-256": _signature("secret123", payload),
        },
    )

    assert limited.status_code == 429


def test_unsafe_repo_name_returns_400(monkeypatch):
    _reset_webhook_state()
    app = github_webhook.create_webhook_app()
    client = app.test_client()
    now = datetime.now(UTC).isoformat()
    body = {
        "repository": {"full_name": "../../../etc/passwd", "default_branch": "main"},
        "workflow_run": {
            "conclusion": "failure",
            "head_branch": "main",
            "head_sha": "abc123",
            "name": "CI",
            "logs_url": "https://example.com/logs",
            "updated_at": now,
        },
    }
    payload = json.dumps(body).encode("utf-8")
    monkeypatch.setattr(github_webhook, "_webhook_secret", lambda: "secret123")

    response = client.post(
        "/webhook",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "workflow_run",
            "X-GitHub-Delivery": "unsafe-repo",
            "X-Hub-Signature-256": _signature("secret123", payload),
        },
    )

    assert response.status_code == 400


def test_unsafe_branch_name_returns_400(monkeypatch):
    _reset_webhook_state()
    app = github_webhook.create_webhook_app()
    client = app.test_client()
    now = datetime.now(UTC).isoformat()
    body = {
        "repository": {"full_name": "g-dos/gedos", "default_branch": "main"},
        "workflow_run": {
            "conclusion": "failure",
            "head_branch": "main; rm -rf ~",
            "head_sha": "abc123",
            "name": "CI",
            "logs_url": "https://example.com/logs",
            "updated_at": now,
        },
    }
    payload = json.dumps(body).encode("utf-8")
    monkeypatch.setattr(github_webhook, "_webhook_secret", lambda: "secret123")

    response = client.post(
        "/webhook",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "workflow_run",
            "X-GitHub-Delivery": "unsafe-branch",
            "X-Hub-Signature-256": _signature("secret123", payload),
        },
    )

    assert response.status_code == 400
