"""
GEDOS Web Agent — Playwright browser automation (async internally).
Provides both async implementations and synchronous wrappers for backward compatibility
with callers that may be synchronous. Uses Playwright's async API.
"""

import asyncio
import concurrent.futures
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable, TypeVar, Any

from core.config import get_agent_config

logger = logging.getLogger(__name__)

_PW = None
_BROWSER = None
_CONTEXT = None
_PAGE = None

T = TypeVar("T")


@dataclass
class WebResult:
    """Result of a web action."""
    success: bool
    message: str
    url: Optional[str] = None
    title: Optional[str] = None
    content_preview: Optional[str] = None
    screenshot_path: Optional[str] = None


async def _async_retry_with_backoff(
    fn: Callable[..., Any],
    *args,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    exceptions: tuple = (Exception,),
    label: Optional[str] = None,
    **kwargs,
) -> Any:
    """Async equivalent of retry_with_backoff."""
    tag = label or getattr(fn, "__name__", "operation")
    last_exc: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await fn(*args, **kwargs)
        except exceptions as e:
            last_exc = e
            if attempt == max_attempts:
                logger.error("%s failed after %d attempts: %s", tag, max_attempts, e)
                raise
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning("%s attempt %d/%d failed (%s), retrying in %.1fs", tag, attempt, max_attempts, e, delay)
            await asyncio.sleep(delay)
    raise last_exc  # type: ignore


async def _get_browser_async():
    """Lazy init Playwright browser (chromium) using async API."""
    global _PW, _BROWSER, _CONTEXT, _PAGE
    try:
        from playwright.async_api import async_playwright
    except Exception:
        return None, None, None
    if _BROWSER is None:
        try:
            _PW = await async_playwright().start()
            _BROWSER = await _PW.chromium.launch(headless=True)
            _CONTEXT = await _BROWSER.new_context()
            _PAGE = await _CONTEXT.new_page()
            cfg = get_agent_config("web")
            # set_default_timeout is synchronous method on Page object in async API
            _PAGE.set_default_timeout(cfg.get("timeout", 30000))
            logger.info("Web agent: Playwright browser started")
        except Exception as e:
            logger.exception("Web agent: failed to start browser: %s", e)
            return None, None, None
    return _BROWSER, _CONTEXT, _PAGE


def _run_coro_sync(coro):
    """Run coroutine and return result. If there's a running loop, run in a new thread."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop in this thread.
        return asyncio.run(coro)
    else:
        # Running loop: execute the coroutine in a fresh event loop in another thread.
        def _thread_run():
            new_loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(new_loop)
                return new_loop.run_until_complete(coro)
            finally:
                try:
                    new_loop.close()
                except Exception:
                    pass

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(_thread_run)
            return fut.result()


async def _navigate_async(url: str, timeout_ms: Optional[int] = None, max_retries: Optional[int] = None) -> WebResult:
    if not url.strip():
        return WebResult(success=False, message="Empty URL.", url=url)
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    browser, _, page = await _get_browser_async()
    if not page:
        return WebResult(success=False, message="Playwright not available. Install: pip install playwright && playwright install chromium", url=url)

    cfg = get_agent_config("web")
    t = timeout_ms or cfg.get("timeout", 30000)
    retries = max_retries if max_retries is not None else cfg.get("max_retries", 3)

    async def _attempt():
        await page.goto(url, timeout=t)
        title = await page.title()
        content_html = await page.content()
        preview = content_html[:500] if content_html else None
        return WebResult(success=True, message="Page loaded.", url=page.url, title=title, content_preview=preview)

    try:
        return await _async_retry_with_backoff(_attempt, max_attempts=retries, base_delay=1.0, label=f"navigate({url[:60]})")
    except Exception as e:
        logger.warning("navigate %s: %s", url, e)
        return WebResult(success=False, message=str(e), url=url)


def navigate(url: str, timeout_ms: Optional[int] = None, max_retries: Optional[int] = None) -> WebResult:
    """Synchronous wrapper around async navigate for backward compatibility."""
    return _run_coro_sync(_navigate_async(url, timeout_ms=timeout_ms, max_retries=max_retries))


async def _get_page_content_async(max_chars: int = 10000) -> WebResult:
    _, _, page = await _get_browser_async()
    if not page:
        return WebResult(success=False, message="No page open.")
    try:
        url = page.url
        title = await page.title()
        body = page.locator("body")
        text = await body.inner_text() if await body.count() else ""
        if len(text) > max_chars:
            text = text[:max_chars] + "\n... (truncated)"
        return WebResult(success=True, message="Content retrieved.", url=url, title=title, content_preview=text)
    except Exception as e:
        return WebResult(success=False, message=str(e))


def get_page_content(max_chars: int = 10000) -> WebResult:
    return _run_coro_sync(_get_page_content_async(max_chars=max_chars))


async def _click_selector_async(selector: str) -> WebResult:
    _, _, page = await _get_browser_async()
    if not page:
        return WebResult(success=False, message="No page open.")
    try:
        await page.click(selector, timeout=5000)
        return WebResult(success=True, message=f"Clicked: {selector}", url=page.url)
    except Exception as e:
        return WebResult(success=False, message=str(e))


def click_selector(selector: str) -> WebResult:
    return _run_coro_sync(_click_selector_async(selector))


async def _type_selector_async(selector: str, text: str) -> WebResult:
    _, _, page = await _get_browser_async()
    if not page:
        return WebResult(success=False, message="No page open.")
    try:
        await page.fill(selector, text, timeout=5000)
        return WebResult(success=True, message=f"Filled: {selector}", url=page.url)
    except Exception as e:
        return WebResult(success=False, message=str(e))


def type_selector(selector: str, text: str) -> WebResult:
    return _run_coro_sync(_type_selector_async(selector, text))


async def _screenshot_async(path: Optional[str] = None) -> WebResult:
    _, _, page = await _get_browser_async()
    if not page:
        return WebResult(success=False, message="No page open.")
    try:
        if not path:
            root = Path(__file__).resolve().parent.parent
            path = str(root / "screenshot.png")
        await page.screenshot(path=path)
        return WebResult(success=True, message="Screenshot saved.", screenshot_path=path, url=page.url)
    except Exception as e:
        return WebResult(success=False, message=str(e))


def screenshot(path: Optional[str] = None) -> WebResult:
    return _run_coro_sync(_screenshot_async(path=path))


def search_google(query: str) -> WebResult:
    safe = query.replace(" ", "+")
    url = f"https://www.google.com/search?q={safe}"
    return navigate(url)


async def _close_browser_async() -> None:
    global _PW, _BROWSER, _CONTEXT, _PAGE
    if _PAGE:
        try:
            await _PAGE.close()
        except Exception:
            pass
    if _CONTEXT:
        try:
            await _CONTEXT.close()
        except Exception:
            pass
    if _BROWSER:
        try:
            await _BROWSER.close()
        except Exception:
            pass
    if _PW:
        try:
            await _PW.stop()
        except Exception:
            pass
    _PW = None
    _BROWSER = None
    _CONTEXT = None
    _PAGE = None
    logger.info(\"Web agent: browser closed\")\n+
\n+def close_browser() -> None:\n+    return _run_coro_sync(_close_browser_async())\n+
