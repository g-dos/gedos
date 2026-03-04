"""
GEDOS GitHub webhook receiver — accepts CI failure events and launches healing.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta, UTC
import hashlib
import hmac
import logging
import os
import threading
from typing import Any

from flask import Flask, jsonify, request

from core.ci_healer import CIFailureContext, handle_ci_failure
from core.config import load_config

logger = logging.getLogger(__name__)
_WEBHOOK_STATE: dict[str, Any] = {"running": False, "port": 9876}
_RECENT_DELIVERIES: deque[str] = deque(maxlen=100)
_RECENT_DELIVERY_SET: set[str] = set()
_REQUEST_TIMESTAMPS: deque[datetime] = deque()


def _webhook_port() -> int:
    """Resolve GitHub webhook port from config or environment."""
    if env_port := os.getenv("GITHUB_WEBHOOK_PORT"):
        try:
            return int(env_port)
        except ValueError:
            logger.warning("Ignoring invalid GITHUB_WEBHOOK_PORT: %s", env_port)
    config = load_config()
    return int((config.get("github") or {}).get("webhook_port", 9876))


def get_webhook_status() -> dict[str, Any]:
    """Return the current webhook server status."""
    port = _WEBHOOK_STATE.get("port") or _webhook_port()
    return {"running": bool(_WEBHOOK_STATE.get("running")), "port": int(port)}


def _set_webhook_status(running: bool, port: int) -> None:
    """Persist the in-process webhook status."""
    _WEBHOOK_STATE["running"] = running
    _WEBHOOK_STATE["port"] = port


def _webhook_secret() -> str:
    """Return the configured GitHub webhook secret."""
    return os.getenv("GITHUB_WEBHOOK_SECRET", "").strip()


def _signature_is_valid(raw_body: bytes, signature_header: str) -> bool:
    """Validate the GitHub HMAC SHA-256 webhook signature."""
    secret = _webhook_secret()
    if not secret:
        logger.warning("GITHUB_WEBHOOK_SECRET not set; rejecting webhook.")
        return False
    if not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    received = signature_header.split("=", 1)[1]
    return hmac.compare_digest(expected, received)


def _build_failure_context(payload: dict) -> CIFailureContext:
    """Translate a workflow_run payload into the healer input structure."""
    workflow_run = payload.get("workflow_run") or {}
    repository = payload.get("repository") or {}
    return CIFailureContext(
        repo_full_name=repository.get("full_name") or "",
        branch=workflow_run.get("head_branch") or repository.get("default_branch") or "main",
        commit_sha=workflow_run.get("head_sha") or "",
        workflow_name=workflow_run.get("name") or payload.get("workflow") or "GitHub Actions",
        failure_logs_url=workflow_run.get("logs_url") or "",
        run_id=workflow_run.get("id"),
        html_url=workflow_run.get("html_url"),
    )


def _payload_is_fresh(payload: dict) -> bool:
    """Reject workflow events older than 5 minutes when a timestamp is available."""
    workflow_run = payload.get("workflow_run") or {}
    timestamp = workflow_run.get("updated_at") or workflow_run.get("created_at")
    if not timestamp:
        return True
    try:
        event_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return False
    now = datetime.now(UTC)
    return now - event_time <= timedelta(minutes=5)


def _remember_delivery(delivery_id: str) -> bool:
    """Track recent delivery IDs and reject duplicates."""
    if not delivery_id:
        return False
    if delivery_id in _RECENT_DELIVERY_SET:
        return False
    if len(_RECENT_DELIVERIES) == _RECENT_DELIVERIES.maxlen:
        dropped = _RECENT_DELIVERIES.popleft()
        _RECENT_DELIVERY_SET.discard(dropped)
    _RECENT_DELIVERIES.append(delivery_id)
    _RECENT_DELIVERY_SET.add(delivery_id)
    return True


def _rate_limit_ok() -> bool:
    """Allow at most 10 webhook requests per minute."""
    now = datetime.now(UTC)
    cutoff = now - timedelta(minutes=1)
    while _REQUEST_TIMESTAMPS and _REQUEST_TIMESTAMPS[0] < cutoff:
        _REQUEST_TIMESTAMPS.popleft()
    if len(_REQUEST_TIMESTAMPS) >= 10:
        return False
    _REQUEST_TIMESTAMPS.append(now)
    return True


def create_webhook_app() -> Flask:
    """Create the Flask app that receives GitHub webhooks."""
    app = Flask("gedos-github-webhook")

    @app.post("/webhook")
    def webhook():
        if not _rate_limit_ok():
            return jsonify({"status": "rate limited"}), 429
        raw_body = request.get_data()
        signature = request.headers.get("X-Hub-Signature-256", "")
        if not _signature_is_valid(raw_body, signature):
            return jsonify({"status": "invalid signature"}), 403

        if request.headers.get("X-GitHub-Event") != "workflow_run":
            return jsonify({"status": "ignored"}), 200

        payload = request.get_json(silent=True) or {}
        delivery_id = request.headers.get("X-GitHub-Delivery", "")
        if not _remember_delivery(delivery_id):
            return jsonify({"status": "duplicate delivery"}), 409
        if not _payload_is_fresh(payload):
            return jsonify({"status": "stale event"}), 409
        workflow_run = payload.get("workflow_run") or {}
        if workflow_run.get("conclusion") != "failure":
            return jsonify({"status": "ignored"}), 200

        context = _build_failure_context(payload)
        if not context.repo_full_name or not context.failure_logs_url:
            logger.warning("Ignoring incomplete workflow_run payload.")
            return jsonify({"status": "ignored"}), 200

        thread = threading.Thread(target=handle_ci_failure, args=(context,), daemon=True)
        thread.start()
        return jsonify({"status": "accepted"}), 200

    return app


def run_github_webhook_server() -> None:
    """Run the GitHub webhook server."""
    app = create_webhook_app()
    port = _webhook_port()
    _set_webhook_status(True, port)
    logger.info("Starting GitHub webhook server on port %s", port)
    try:
        app.run(host="0.0.0.0", port=port)
    finally:
        _set_webhook_status(False, port)
