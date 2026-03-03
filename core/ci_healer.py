"""
GEDOS CI healer — analyzes GitHub CI failures and attempts autonomous fixes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, UTC
import io
import logging
import os
from pathlib import Path
import re
import shlex
import tempfile
from typing import Optional
import zipfile

import requests
from github import Github

from agents.terminal_agent import run_shell
from core.config import load_config
from core.llm import complete
from core.memory import Conversation, get_session, get_user_language, init_db as memory_init_db
from interfaces.i18n import t

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CIFailureContext:
    """Structured payload for a GitHub CI failure."""

    repo_full_name: str
    branch: str
    commit_sha: str
    workflow_name: str
    failure_logs_url: str
    run_id: Optional[int] = None
    html_url: Optional[str] = None


@dataclass(slots=True)
class ParsedFailure:
    """Best-effort parsed CI failure location and type."""

    file_path: str
    line_number: Optional[int]
    error_type: str
    log_excerpt: str


def _github_config() -> dict:
    """Return GitHub-related config with environment overrides."""
    config = load_config()
    github_cfg = dict(config.get("github") or {})
    if port := os.getenv("GITHUB_WEBHOOK_PORT"):
        try:
            github_cfg["webhook_port"] = int(port)
        except ValueError:
            logger.warning("Ignoring invalid GITHUB_WEBHOOK_PORT: %s", port)
    return {
        "webhook_port": int(github_cfg.get("webhook_port", 9876)),
        "auto_fix": bool(github_cfg.get("auto_fix", True)),
        "auto_pr": bool(github_cfg.get("auto_pr", True)),
        "notify_on_failure": bool(github_cfg.get("notify_on_failure", True)),
    }


def _github_token() -> str:
    """Return the GitHub token required for CI healing."""
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token:
        raise ValueError("GITHUB_TOKEN is required for CI healing.")
    return token


def _github_client() -> Github:
    """Create an authenticated GitHub API client."""
    return Github(_github_token())


def _fetch_failure_logs(context: CIFailureContext) -> str:
    """Fetch and normalize workflow failure logs into plain text."""
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {_github_token()}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    response = requests.get(context.failure_logs_url, headers=headers, timeout=60)
    response.raise_for_status()
    content_type = (response.headers.get("content-type") or "").lower()
    body = response.content

    if "application/zip" in content_type or zipfile.is_zipfile(io.BytesIO(body)):
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            parts: list[str] = []
            for name in archive.namelist():
                with archive.open(name) as handle:
                    try:
                        parts.append(handle.read().decode("utf-8", errors="replace"))
                    except Exception:
                        parts.append(handle.read().decode("latin-1", errors="replace"))
            return "\n".join(parts)

    return body.decode("utf-8", errors="replace")


def _trim_log_excerpt(log_text: str, max_chars: int = 6000) -> str:
    """Keep the most relevant tail of the log to reduce prompt size."""
    text = (log_text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def _parse_failure_details(log_text: str) -> Optional[ParsedFailure]:
    """Heuristically extract a failing file, line number, and error type."""
    excerpt = _trim_log_excerpt(log_text)
    patterns = [
        re.compile(r'File "([^"]+)", line (\d+).*\n(?:.*\n){0,2}([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception))', re.MULTILINE),
        re.compile(r"^([A-Za-z0-9_./\\-]+\.(?:py|js|ts|tsx|jsx|rb|go|rs|java|kt|swift|c|cpp|h)):(\d+)(?::\d+)?:\s*([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception|Warning))", re.MULTILINE),
        re.compile(r"FAILED\s+([A-Za-z0-9_./\\-]+\.(?:py|js|ts|tsx|jsx))::", re.MULTILINE),
    ]

    for pattern in patterns:
        match = pattern.search(log_text)
        if not match:
            continue
        file_path = match.group(1)
        line_number = None
        error_type = "CI failure"
        if match.lastindex and match.lastindex >= 2:
            try:
                line_number = int(match.group(2))
            except Exception:
                line_number = None
        if match.lastindex and match.lastindex >= 3:
            error_type = match.group(3)
        return ParsedFailure(
            file_path=file_path,
            line_number=line_number,
            error_type=error_type,
            log_excerpt=excerpt,
        )

    generic_error = re.search(r"([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception))", log_text)
    if generic_error:
        return ParsedFailure(
            file_path="",
            line_number=None,
            error_type=generic_error.group(1),
            log_excerpt=excerpt,
        )
    return None


def _clean_llm_file_output(response: str) -> str:
    """Strip common markdown wrappers from full-file LLM responses."""
    text = (response or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _suggest_fixed_file_content(
    file_path: Path,
    current_content: str,
    failure: ParsedFailure,
    context: CIFailureContext,
) -> str:
    """Ask the configured LLM for corrected full-file contents."""
    line_text = f"Line: {failure.line_number}\n" if failure.line_number else ""
    prompt = (
        "You are fixing a failing CI run.\n"
        f"Repository: {context.repo_full_name}\n"
        f"Workflow: {context.workflow_name}\n"
        f"Commit: {context.commit_sha}\n"
        f"Target file: {failure.file_path or file_path.as_posix()}\n"
        f"{line_text}"
        f"Error type: {failure.error_type}\n\n"
        "Failure logs (tail):\n"
        f"{failure.log_excerpt}\n\n"
        "Current file contents:\n"
        f"{current_content}\n\n"
        "Return ONLY the full corrected contents of the target file. "
        "Do not add markdown fences or explanations."
    )
    fixed = complete(prompt, max_tokens=4096)
    return _clean_llm_file_output(fixed)


def _write_file_via_terminal_agent(target_path: Path, new_content: str) -> bool:
    """Write file contents by invoking a local Python process through the terminal agent."""
    code = (
        "from pathlib import Path\n"
        f"Path({str(target_path)!r}).write_text({new_content!r}, encoding='utf-8')\n"
    )
    command = f"python -c {shlex.quote(code)}"
    result = run_shell(command)
    if not result.success:
        logger.error("Failed to write patched file %s: %s", target_path, (result.stderr or result.stdout).strip())
    return result.success


def _authenticated_clone_url(clone_url: str, token: str) -> str:
    """Embed a GitHub token into an HTTPS clone URL."""
    if clone_url.startswith("https://"):
        return clone_url.replace("https://", f"https://x-access-token:{token}@", 1)
    return clone_url


def _prepare_checkout(context: CIFailureContext):
    """Clone the target repository into a fresh temporary directory and check out the failing branch."""
    gh = _github_client()
    repo = gh.get_repo(context.repo_full_name)
    tokenized_url = _authenticated_clone_url(repo.clone_url, _github_token())
    clone_root = Path(tempfile.mkdtemp(prefix="gedos-ci-"))
    checkout_dir = clone_root / repo.name

    clone_result = run_shell(f"git clone {shlex.quote(tokenized_url)} {shlex.quote(str(checkout_dir))}")
    if not clone_result.success:
        raise RuntimeError(f"Failed to clone repository: {(clone_result.stderr or clone_result.stdout).strip()}")

    fetch_result = run_shell(f"git fetch origin {shlex.quote(context.branch)}", cwd=str(checkout_dir))
    if not fetch_result.success:
        raise RuntimeError(f"Failed to fetch branch {context.branch}: {(fetch_result.stderr or fetch_result.stdout).strip()}")

    remote_ref = f"origin/{context.branch}"
    checkout_result = run_shell(f"git checkout --track {shlex.quote(remote_ref)}", cwd=str(checkout_dir))
    if not checkout_result.success:
        fallback = run_shell(f"git checkout {shlex.quote(context.branch)}", cwd=str(checkout_dir))
        if not fallback.success:
            raise RuntimeError(f"Failed to check out branch {context.branch}: {(fallback.stderr or fallback.stdout).strip()}")

    return repo, checkout_dir


def _resolve_target_file(repo_dir: Path, failure: ParsedFailure) -> Optional[Path]:
    """Resolve the best candidate target file inside the cloned repository."""
    if failure.file_path:
        candidate = (repo_dir / failure.file_path).resolve()
        if candidate.exists() and candidate.is_file():
            return candidate

        matches = list(repo_dir.rglob(Path(failure.file_path).name))
        for match in matches:
            if match.is_file():
                return match
    return None


def _run_validation_tests(repo_dir: Path) -> bool:
    """Run the local test suite after applying a fix."""
    commands = (
        "python -m pytest -q",
        "pytest -q",
    )
    for command in commands:
        result = run_shell(command, cwd=str(repo_dir), timeout_seconds=300)
        if result.success:
            return True
    return False


def _create_pr(repo, repo_dir: Path, context: CIFailureContext, failure: ParsedFailure) -> tuple[int, str]:
    """Commit the fix, push a branch, and open a pull request."""
    branch_name = f"codex/ci-heal-{context.commit_sha[:7]}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
    git_name = run_shell('git config user.name "Gedos CI Healer"', cwd=str(repo_dir))
    git_email = run_shell('git config user.email "ci-healer@gedos.local"', cwd=str(repo_dir))
    if not git_name.success or not git_email.success:
        raise RuntimeError("Failed to configure git author for CI healer.")

    branch_result = run_shell(f"git checkout -b {shlex.quote(branch_name)}", cwd=str(repo_dir))
    if not branch_result.success:
        raise RuntimeError(f"Failed to create fix branch: {(branch_result.stderr or branch_result.stdout).strip()}")

    add_result = run_shell("git add .", cwd=str(repo_dir))
    commit_result = run_shell(
        'git commit -m "fix: auto-heal CI failure"',
        cwd=str(repo_dir),
        timeout_seconds=120,
    )
    push_result = run_shell(f"git push -u origin {shlex.quote(branch_name)}", cwd=str(repo_dir), timeout_seconds=300)
    if not add_result.success or not commit_result.success or not push_result.success:
        raise RuntimeError("Failed to commit and push the CI fix branch.")

    pr = repo.create_pull(
        title=f"fix: auto-heal {failure.error_type}",
        body=(
            "Automated CI healer attempt.\n\n"
            f"- Workflow: {context.workflow_name}\n"
            f"- Failed commit: {context.commit_sha}\n"
            f"- Target branch: {context.branch}\n"
            f"- Error: {failure.error_type}\n"
        ),
        head=branch_name,
        base=context.branch,
    )
    return pr.number, pr.html_url


def _latest_telegram_chat_id() -> Optional[str]:
    """Best-effort lookup of the most recent Telegram chat id from stored conversations."""
    memory_init_db()
    with get_session() as session:
        convo = session.query(Conversation).order_by(Conversation.timestamp.desc()).first()
        if convo:
            return convo.user_id
    return None


def _latest_telegram_language(chat_id: Optional[str]) -> str:
    """Best-effort lookup of the latest Telegram user's preferred language."""
    if not chat_id:
        return "en"
    return get_user_language(chat_id) or "en"


def _notify_user(message: str) -> None:
    """Send a best-effort Telegram notification to the most recent chat."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = _latest_telegram_chat_id()
    if not token or not chat_id:
        logger.info("Skipping Telegram notification: missing token or known chat.")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message[:4000]},
            timeout=15,
        )
    except Exception:
        logger.exception("Failed to send Telegram notification")


def handle_ci_failure(context: CIFailureContext) -> None:
    """Run the self-healing flow for a failed CI workflow."""
    github_cfg = _github_config()
    if not github_cfg["auto_fix"]:
        logger.info("GitHub CI auto-fix is disabled.")
        return

    try:
        chat_id = _latest_telegram_chat_id()
        lang = _latest_telegram_language(chat_id)
        logs = _fetch_failure_logs(context)
        failure = _parse_failure_details(logs)
        if not failure:
            raise RuntimeError("Could not determine failing file from workflow logs.")

        repo, repo_dir = _prepare_checkout(context)
        target_file = _resolve_target_file(repo_dir, failure)
        if target_file is None:
            raise RuntimeError(f"Could not locate failing file in checkout: {failure.file_path or '(unknown)'}")

        current_content = target_file.read_text(encoding="utf-8")
        suggested = _suggest_fixed_file_content(target_file, current_content, failure, context)
        if not suggested or suggested == current_content:
            raise RuntimeError("LLM did not produce a meaningful file change.")

        if not _write_file_via_terminal_agent(target_file, suggested):
            raise RuntimeError("Failed to apply file patch through terminal agent.")

        if not _run_validation_tests(repo_dir):
            raise RuntimeError("CI failed, couldn't auto-fix")

        pr_url = ""
        pr_number: Optional[int] = None
        if github_cfg["auto_pr"]:
            pr_number, pr_url = _create_pr(repo, repo_dir, context, failure)

        message = t(
            "github_ci_fix_success",
            lang,
            repo=context.repo_full_name,
            branch=context.branch,
            error_summary=failure.error_type,
            what_was_changed=target_file.relative_to(repo_dir).as_posix(),
            pr_number=pr_number or "?",
            pr_url=pr_url or "",
        )
        _notify_user(message)
    except Exception as exc:
        logger.exception("CI healer failed")
        if github_cfg["notify_on_failure"]:
            chat_id = _latest_telegram_chat_id()
            lang = _latest_telegram_language(chat_id)
            _notify_user(
                t(
                    "github_ci_fix_failure",
                    lang,
                    repo=context.repo_full_name,
                    branch=context.branch,
                    error_summary=str(exc),
                )
            )
