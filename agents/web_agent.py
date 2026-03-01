"""
GEDOS Web Agent — Playwright browser automation.
Navigate, click, type, scrape content, screenshot.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

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
            _PAGE.set_default_timeout(30000)
            logger.info("Web agent: Playwright browser started")
        except Exception as e:
            logger.exception("Web agent: failed to start browser: %s", e)
            return None, None, None
    return _BROWSER, _CONTEXT, _PAGE


def navigate(url: str, timeout_ms: Optional[int] = 30000) -> WebResult:
    """Navigate to URL. Ensures url has scheme."""
    if not url.strip():
        return WebResult(success=False, message="URL vazia.")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    browser, _, page = _get_browser()
    if not page:
        return WebResult(success=False, message="Playwright não disponível. Instale: pip install playwright && playwright install chromium")
    try:
        page.goto(url, timeout=timeout_ms or 30000)
        return WebResult(
            success=True,
            message="Página carregada.",
            url=page.url,
            title=page.title(),
            content_preview=page.content()[:500] if page.content() else None,
        )
    except Exception as e:
        logger.warning("navigate %s: %s", url, e)
        return WebResult(success=False, message=str(e), url=url)


def get_page_content(max_chars: int = 10000) -> WebResult:
    """Get current page URL, title, and text content."""
    _, _, page = _get_browser()
    if not page:
        return WebResult(success=False, message="Nenhuma página aberta.")
    try:
        url = page.url
        title = page.title()
        body = page.locator("body")
        text = body.inner_text() if body.count() else ""
        if len(text) > max_chars:
            text = text[:max_chars] + "\n… (truncado)"
        return WebResult(
            success=True,
            message="Conteúdo obtido.",
            url=url,
            title=title,
            content_preview=text,
        )
    except Exception as e:
        return WebResult(success=False, message=str(e))


def click_selector(selector: str) -> WebResult:
    """Click element matching CSS selector."""
    _, _, page = _get_browser()
    if not page:
        return WebResult(success=False, message="Nenhuma página aberta.")
    try:
        page.click(selector, timeout=5000)
        return WebResult(success=True, message=f"Clicado: {selector}", url=page.url)
    except Exception as e:
        return WebResult(success=False, message=str(e))


def type_selector(selector: str, text: str) -> WebResult:
    """Type text into element matching selector."""
    _, _, page = _get_browser()
    if not page:
        return WebResult(success=False, message="Nenhuma página aberta.")
    try:
        page.fill(selector, text, timeout=5000)
        return WebResult(success=True, message=f"Preenchido: {selector}", url=page.url)
    except Exception as e:
        return WebResult(success=False, message=str(e))


def screenshot(path: Optional[str] = None) -> WebResult:
    """Take screenshot of current page. Returns path if path provided."""
    _, _, page = _get_browser()
    if not page:
        return WebResult(success=False, message="Nenhuma página aberta.")
    try:
        if not path:
            root = Path(__file__).resolve().parent.parent
            path = str(root / "screenshot.png")
        page.screenshot(path=path)
        return WebResult(success=True, message="Screenshot salvo.", screenshot_path=path, url=page.url)
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
