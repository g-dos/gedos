"""
GEDOS Web Agent — Playwright browser automation.
Navigate, click, type, scrape content, screenshot.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.config import get_agent_config
from core.retry import retry_with_backoff

logger = logging.getLogger(__name__)

_BROWSER = None
_CONTEXT = None
_PAGE = None


@dataclass
class WebResult:
    """Result of a web action."""
    success: bool
    message: str
    url: Optional[str] = None
    title: Optional[str] = None
    content_preview: Optional[str] = None
    screenshot_path: Optional[str] = None


def _get_browser():
    """Lazy init Playwright browser (chromium)."""
    global _BROWSER, _CONTEXT, _PAGE
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None, None, None
    if _BROWSER is None:
        try:
            pw = sync_playwright().start()
            _BROWSER = pw.chromium.launch(headless=True)
            _CONTEXT = _BROWSER.new_context()
            _PAGE = _CONTEXT.new_page()
            cfg = get_agent_config("web")
            _PAGE.set_default_timeout(cfg.get("timeout", 30000))
            logger.info("Web agent: Playwright browser started")
        except Exception as e:
            logger.exception("Web agent: failed to start browser: %s", e)
            return None, None, None
    return _BROWSER, _CONTEXT, _PAGE


def navigate(url: str, timeout_ms: Optional[int] = None, max_retries: Optional[int] = None) -> WebResult:
    """Navigate to URL with retry on transient network failures."""
    if not url.strip():
        return WebResult(success=False, message="Empty URL.")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    browser, _, page = _get_browser()
    if not page:
        return WebResult(success=False, message="Playwright not available. Install: pip install playwright && playwright install chromium")

    cfg = get_agent_config("web")
    t = timeout_ms or cfg.get("timeout", 30000)
    retries = max_retries if max_retries is not None else cfg.get("max_retries", 3)

    def _attempt():
        page.goto(url, timeout=t)
        return WebResult(
            success=True, message="Page loaded.",
            url=page.url, title=page.title(),
            content_preview=page.content()[:500] if page.content() else None,
        )

    try:
        return retry_with_backoff(_attempt, max_attempts=retries, base_delay=1.0, label=f"navigate({url[:60]})")
    except Exception as e:
        logger.warning("navigate %s: %s", url, e)
        return WebResult(success=False, message=str(e), url=url)


def get_page_content(max_chars: int = 10000) -> WebResult:
    """Get current page URL, title, and text content."""
    _, _, page = _get_browser()
    if not page:
        return WebResult(success=False, message="No page open.")
    try:
        url = page.url
        title = page.title()
        body = page.locator("body")
        text = body.inner_text() if body.count() else ""
        if len(text) > max_chars:
            text = text[:max_chars] + "\n... (truncated)"
        return WebResult(success=True, message="Content retrieved.", url=url, title=title, content_preview=text)
    except Exception as e:
        return WebResult(success=False, message=str(e))


def click_selector(selector: str) -> WebResult:
    """Click element matching CSS selector."""
    _, _, page = _get_browser()
    if not page:
        return WebResult(success=False, message="No page open.")
    try:
        page.click(selector, timeout=5000)
        return WebResult(success=True, message=f"Clicked: {selector}", url=page.url)
    except Exception as e:
        return WebResult(success=False, message=str(e))


def type_selector(selector: str, text: str) -> WebResult:
    """Type text into element matching selector."""
    _, _, page = _get_browser()
    if not page:
        return WebResult(success=False, message="No page open.")
    try:
        page.fill(selector, text, timeout=5000)
        return WebResult(success=True, message=f"Filled: {selector}", url=page.url)
    except Exception as e:
        return WebResult(success=False, message=str(e))


def screenshot(path: Optional[str] = None) -> WebResult:
    """Take screenshot of current page. Returns path if path provided."""
    _, _, page = _get_browser()
    if not page:
        return WebResult(success=False, message="No page open.")
    try:
        if not path:
            root = Path(__file__).resolve().parent.parent
            path = str(root / "screenshot.png")
        page.screenshot(path=path)
        return WebResult(success=True, message="Screenshot saved.", screenshot_path=path, url=page.url)
    except Exception as e:
        return WebResult(success=False, message=str(e))


def search_google(query: str) -> WebResult:
    """Navigate to Google and run search (simplified: go to search URL)."""
    safe = query.replace(" ", "+")
    url = f"https://www.google.com/search?q={safe}"
    return navigate(url)


def close_browser() -> None:
    """Close Playwright browser and context."""
    global _BROWSER, _CONTEXT, _PAGE
    if _BROWSER:
        try:
            _BROWSER.close()
        except Exception:
            pass
        _BROWSER = None
        _CONTEXT = None
        _PAGE = None
    logger.info("Web agent: browser closed")
