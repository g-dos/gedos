# Web Tool (Scrapling + Playwright)

## Overview

Gedos supports two web execution paths:

- **Scrapling tool** (`tools/web_scraper.py`): lightweight HTTP scraping, fast startup, no browser process. Best for static pages and simple content extraction.
- **Playwright Web Agent** (`agents/web_agent.py`): full browser automation for dynamic/JS-heavy pages and interactive flows.

Use Scrapling when you only need text/content quickly. Use Playwright when the page needs rendering, navigation state, or user-like interaction.

## Installation

```bash
pip install scrapling
```

## Usage (Telegram tasks)

```text
/task scrape https://example.com and get all h1 titles
/task fetch content from https://news.ycombinator.com
```

## Automatic Routing

In `core/orchestrator.py`, Gedos decides per task:

- If task intent looks like simple scrape/extract/get-text/fetch-content and not interaction, Gedos prefers Scrapling.
- Otherwise, Gedos falls back to the existing Playwright Web Agent path.
- If Scrapling is not installed, Gedos silently uses Playwright (no user-facing error).

## Limitations (Scrapling path)

- No JavaScript rendering
- No interactive actions (click/fill/interact)
- No login/session-driven browser flows

For these cases, Playwright is required.
