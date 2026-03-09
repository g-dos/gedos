"""Tests for optional Scrapling web scraper helpers."""

from __future__ import annotations

from unittest.mock import patch

from tools import web_scraper


def test_scrapling_unavailable() -> None:
    """scrape should return install guidance when Scrapling is unavailable."""
    with patch("tools.web_scraper.SCRAPLING_AVAILABLE", False):
        result = web_scraper.scrape("http://example.com")
    assert "pip install scrapling" in result


def test_scrape_no_selector() -> None:
    """scrape should return full text when no selector is provided."""
    class FakePage:
        def get_text(self) -> str:
            return "hello world"

    with patch("tools.web_scraper.SCRAPLING_AVAILABLE", True), patch("tools.web_scraper.Fetcher") as mock_fetcher:
        mock_fetcher.get.return_value = FakePage()
        result = web_scraper.scrape("http://example.com")
    assert result == "hello world"


def test_scrape_with_selector() -> None:
    """scrape should join selector matches when selector is provided."""
    class FakeSelection:
        def getall(self) -> list[str]:
            return ["item1", "item2"]

    class FakePage:
        def css(self, _selector: str) -> FakeSelection:
            return FakeSelection()

    with patch("tools.web_scraper.SCRAPLING_AVAILABLE", True), patch("tools.web_scraper.Fetcher") as mock_fetcher:
        mock_fetcher.get.return_value = FakePage()
        result = web_scraper.scrape("http://example.com", css_selector=".item")
    assert "item1" in result
    assert "item2" in result


def test_fetch_raw_unavailable() -> None:
    """fetch_raw should return install guidance when Scrapling is unavailable."""
    with patch("tools.web_scraper.SCRAPLING_AVAILABLE", False):
        result = web_scraper.fetch_raw("http://example.com")
    assert "pip install scrapling" in result


def test_scrape_exception_handling() -> None:
    """scrape should swallow exceptions and return an error string."""
    with patch("tools.web_scraper.SCRAPLING_AVAILABLE", True), patch("tools.web_scraper.Fetcher") as mock_fetcher:
        mock_fetcher.get.side_effect = RuntimeError("boom")
        result = web_scraper.scrape("http://example.com")
    assert isinstance(result, str)
