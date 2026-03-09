"""
GEDOS optional web scraper utility.

This module provides lightweight HTTP scraping helpers using Scrapling
without requiring browser automation. Install with:

    pip install scrapling
"""

from __future__ import annotations

from typing import Optional

try:
    from scrapling import Fetcher

    SCRAPLING_AVAILABLE = True
except ImportError:
    Fetcher = None  # type: ignore[assignment]
    SCRAPLING_AVAILABLE = False


def _missing_dependency_message() -> str:
    """Return a standard message for missing Scrapling dependency."""
    return "Scrapling is not installed. Install it with: pip install scrapling"


def scrape(url: str, css_selector: Optional[str] = None) -> str:
    """
    Fetch page content and return either selected nodes or full text.

    Args:
        url: Target URL.
        css_selector: Optional CSS selector to extract specific nodes.

    Returns:
        Scraped text on success, or an error message string on failure.
    """
    if not SCRAPLING_AVAILABLE:
        return _missing_dependency_message()

    try:
        page = Fetcher.get(url)  # type: ignore[union-attr]
        if css_selector:
            nodes = page.css(css_selector).getall()
            return "\n".join(str(node) for node in nodes)
        return str(page.get_text())
    except Exception as exc:
        return f"Web scrape failed: {exc}"


def fetch_raw(url: str) -> str:
    """
    Fetch and return raw HTML from a URL.

    Args:
        url: Target URL.

    Returns:
        Raw HTML string on success, or an error message string on failure.
    """
    if not SCRAPLING_AVAILABLE:
        return _missing_dependency_message()

    try:
        page = Fetcher.get(url)  # type: ignore[union-attr]
        return str(page.html_content)
    except Exception as exc:
        return f"Raw fetch failed: {exc}"
