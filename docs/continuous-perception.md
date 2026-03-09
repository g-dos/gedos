# Continuous Perception

## Overview

Percepção Contínua is Gedos' event-driven screen awareness layer for Copilot mode.

- Old model: fixed polling every 10s, which adds delay and unnecessary CPU work.
- New model: native macOS AXObserver notifications fire on real UI changes, so reactions happen near-instantly.

## How it works

1. `AXObserver` tracks the frontmost app and subscribes to accessibility notifications.
2. On each event, Gedos applies debounce (`1s`) to avoid noisy bursts.
3. Then it runs:
   - `analyze_context()`
   - `publish_hints()`
   - `proactive_engine.notify(...)`
4. Fallback behavior: if pyobjc is unavailable, existing polling mode continues unchanged.

## Events monitored

- `AXFocusedWindowChanged`
- `AXFocusedUIElementChanged`
- `AXValueChanged`
- `AXTitleChanged`
- `AXSelectedTextChanged`

## Requirements

```bash
pip install pyobjc-framework-ApplicationServices pyobjc-framework-Cocoa
```

- macOS 12+ required

## Privacy

All perception and analysis run locally on the Mac.
No screen content is sent externally by this feature.
