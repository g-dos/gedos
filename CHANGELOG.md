# Changelog

All notable changes to GEDOS are documented here. Versioning follows [Semver](https://semver.org/).

## [0.8.0] — 2026-03

### Added
- **AX Tree cache**: 5-second TTL cache for static apps to reduce overhead when reading screen elements repeatedly
- **LLM benchmark utility** (`core/llm_bench.py`): measure and compare response times for Ollama, Claude, OpenAI
- **Memory profiler** (`core/memory_profiler.py`): detect memory leaks in long-running sessions, log stats on startup
- **`psutil`**: added for runtime memory usage monitoring

### Changed
- **Lazy agent imports**: agents are imported only when needed, reducing startup time
- **Orchestrator**: `_run_terminal`, `_run_gui`, `_run_web`, `_run_llm` use lazy imports instead of top-level imports
- **Startup**: logs memory stats on launch for profiling

---

## [0.7.0] — 2026-03

### Added
- **Onboarding via `/start`**: first-time users see detailed welcome with mode explanations and quick start guide
- **Mode-specific `/help`**: different output for Pilot vs Copilot modes with relevant commands and examples
- **Progress updates**: long-running tasks send "⏳ Task started, executing..." and update on completion
- **`/task cancel`**: gracefully interrupt running tasks mid-execution with cancellation checkpoints
- **Rich tracebacks**: CLI displays formatted, colored error output instead of raw Python stack traces

### Changed
- **`/start`**: detects first-time vs returning users via memory history
- **`/help`**: dynamic content based on active Copilot status
- **`/stop`**: renamed internally to `/task cancel` behavior, provides clear feedback
- **Task execution**: progress messages edited in-place to show results
- **Error handling**: `rich.traceback` installed globally for better debugging

---

## [0.6.0] — 2026-03

### Added
- **Retry logic**: all agents (terminal, GUI, web) retry up to 3 times with exponential backoff on transient failures
- **`core/retry.py`**: reusable `retry_with_backoff` utility
- **Configurable agent timeouts**: `agents.terminal.timeout`, `agents.gui.timeout`, `agents.web.timeout` in `config.yaml`
- **Telegram error handler**: global error handler logs errors and sends user-friendly message on failure
- **Telegram connection resilience**: configurable `connect_timeout`, `read_timeout`, `write_timeout`; `drop_pending_updates` on startup
- **Rich CLI**: colored startup banner with version, mode, and LLM info
- **CLI flags**: `gedos --help`, `gedos --version` / `-V`, `gedos --mode pilot|copilot` / `-m`
- **`rich`** added to dependencies

### Changed
- **Terminal Agent**: `run_command` and `run_shell` accept `max_retries` parameter, read defaults from config
- **GUI Agent**: `click_button` retries via `retry_with_backoff` when AX Tree doesn't find button immediately
- **Web Agent**: `navigate` retries on network failures with backoff
- **Entrypoint**: rewritten with `argparse`, `rich` banner, graceful `KeyboardInterrupt` handling

---

## [0.5.0] — 2026-03

### Added
- **Demo GIF**: animated terminal simulation at `docs/demo.gif` with generation script
- **docs/setup-ollama.md**: step-by-step Ollama install, recommended models, troubleshooting
- **docs/examples.md**: 5 real usage examples (git commit, VS Code, web, screen, copilot mode)
- **CONTRIBUTING.md**: clone/run instructions, code style, semantic commits, PR checklist

### Changed
- **README**: complete rewrite — end-to-end quickstart from fresh clone, command table, links to all docs

---

## [0.4.0] — 2026-03

### Added
- **Pytest smoke tests**: config, memory, terminal_agent, orchestrator (22 tests)

### Changed
- **Terminal Agent**: default timeout lowered to 30s (was 60s), configurable via `timeout_seconds`
- **Terminal Agent**: clearer error messages (Portuguese) for timeout, command-not-found, generic failure
- **Telegram bot**: improved error formatting (distinct icons for timeout, not-found, generic errors)

### Fixed
- AGENTS.md Development Order checklist now reflects all completed items

---

## [0.3.0] — 2025-03

### Added
- **Full Copilot Mode**: proactive suggestions based on active app (Terminal, VS Code, Xcode, Safari, etc.) and warnings when error-like text is detected on screen
- **Stability**: retry once on orchestrator failure, try/except around task execution with user-facing error messages
- **Health check**: `/ping` command
- `core/copilot_context.py`: context analysis for suggestions and warnings

### Changed
- Copilot job uses `analyze_context()` for smarter suggestions and warnings
- Throttling: no duplicate Copilot messages per user

---

## [0.2.0] — 2025-03

### Added
- Web Agent (Playwright): navigate, search, scrape
- Memory layer (SQLite + SQLAlchemy): conversations, tasks, context
- Orchestrator (LangGraph): route tasks to terminal, GUI, web, or LLM
- LLM integration: Ollama (local), Claude/OpenAI (optional)
- Copilot Mode (basic): `/copilot on|off`, app-change suggestions
- Commands: `/memory`, `/web <url>`, `/ask <pergunta>`

---

## [0.1.0] — 2025-03

### Added
- Telegram bot (Pilot Mode): `/task`, `/status`, `/stop`, `/start`, `/help`
- Terminal Agent: shell command execution
- AX Tree: native macOS Accessibility screen reading
- GUI Agent: mouse and keyboard control, click by button name
- Config (YAML + .env), Semver in `gedos.py` and `config.yaml`

---

*Built by [@g-dos](https://github.com/g-dos)*
