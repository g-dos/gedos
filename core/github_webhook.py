"""
GEDOS GitHub webhook receiver — accepts CI failure events and launches healing.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import threading

from flask import Flask, jsonify, request

from core.ci_healer import CIFailureContext, handle_ci_failure
from core.config import load_config

logger = logging.getLogger(__name__)


def _webhook_port() -> int:
    """Resolve GitHub webhook port from config or environment."""
    if env_port := os.getenv("GITHUB_WEBHOOK_PORT"):
        try:
            return int(env_port)
        except ValueError:
            logger.warning("Ignoring invalid GITHUB_WEBHOOK_PORT: %s", env_port)
    config = load_config()
    return int((config.get("github") or {}).get("webhook_port", 9876))


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


def create_webhook_app() -> Flask:
    """Create the Flask app that receives GitHub webhooks."""
    app = Flask("gedos-github-webhook")

    @app.post("/webhook")
    def webhook():
        raw_body = request.get_data()
        signature = request.headers.get("X-Hub-Signature-256", "")
        if not _signature_is_valid(raw_body, signature):
            return jsonify({"status": "invalid signature"}), 401

        if request.headers.get("X-GitHub-Event") != "workflow_run":
            return jsonify({"status": "ignored"}), 200

        payload = request.get_json(silent=True) or {}
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
    logger.info("Starting GitHub webhook server on port %s", port)
    app.run(host="0.0.0.0", port=port)
