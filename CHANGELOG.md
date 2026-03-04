# Changelog

All notable changes to GEDOS are documented here. Versioning follows [Semver](https://semver.org/).

## [0.9.6.3] — 2026-03

### Security Hardening Patch 3
- **Safe path restrictions**: `cat`, `find`, `cp`, `mv`, and `ls` now reject sensitive files, sensitive directories, and unsafe destinations while preserving safe relative project paths
- **`env` removed from the allowlist**: direct environment dumps are no longer permitted through terminal execution
- **Dangerous `git` operations blocked**: `-c`, global config changes, `clone`, `submodule`, `archive`, and related risky operations are now rejected during sanitization
- **Blocked network-listening Python modules**: `python -m http.server`, `smtpd`, and other interactive or server-style modules are now blocked
- **Command length limit**: shell commands longer than 1000 characters are rejected before parsing
- **LLM security system prompt**: all LLM calls now include a built-in security prompt that refuses prompt-injection attempts, secret disclosure, and safety bypasses
- **Planner prompt sanitization**: multi-step planning now strips common prompt-injection phrases and wraps user tasks as `USER TASK:` before sending them to the LLM
- **CI healer path traversal blocked**: resolved target files must stay inside the checked-out repository root
- **CI healer patch validation**: LLM-generated fixes are rejected if they are too large or contain obviously unsafe code patterns before any write occurs
- **MCP task history scoped**: MCP history now reads and writes only within the dedicated `mcp_client` task stream
- **Unsafe URL schemes blocked**: `ftp://`, `file://`, `javascript:`, `data:`, and similar schemes are explicitly rejected

### Validation
- **Advanced red-team regression**: the newly targeted shell abuse cases, prompt-injection paths, CI healer traversal checks, and MCP history leak are all covered by the updated tests
- **Test suite**: all tests pass after the third hardening pass (`99 passed`)

## [0.9.6.2] — 2026-03

### Security Hardening Patch 2
- **Auto-generated pairing code**: when no `PAIRING_CODE` is configured, Gedos now generates a one-time local claim code and requires it before the first owner can claim the bot
- **`pip install` path traversal blocked**: local paths such as `../`, `/tmp`, `~/`, and `file:` are now rejected during command sanitization
- **Unsafe `git` flags blocked**: dangerous flags such as `--exec-path` and path-valued long options are now rejected before execution
- **Database file permissions**: `gedos.db` is now forced to `0600` during database initialization and startup checks
- **Webhook identifier sanitization**: GitHub repo and branch names must now match a safe allowlist before CI healing starts
- **Per-user task history**: task history is now scoped by `user_id`, so `/memory` only shows data from the requesting chat
- **`/forget all` implemented**: users can now clear their own learned patterns and stored user-scoped history
- **NUL byte and non-printable input blocked**: command sanitization now rejects embedded NUL bytes and control characters up front
- **Unauthorized chat log throttling**: repeated unauthorized chat spam now logs at most once per chat per minute

### Validation
- **Red-team regression**: all 19 shell attack payloads are now blocked by `sanitize_command()`
- **Test suite**: all tests pass after the second hardening pass (`94 passed`)

## [0.9.6.1] — 2026-03

### Security Hardening
- **Shell injection hardening**: `sanitize_command()` is now mandatory before shell execution and enforces a strict executable allowlist
- **Strict shell mode**: terminal execution now uses `shell=False` with tokenized args, making injection through shell metacharacters structurally impossible
- **Telegram owner pairing**: the first authorized `/start` pairs an owner chat, while unauthorized chats are silently ignored after pairing
- **Webhook replay protection**: GitHub webhook handling now rejects stale events, duplicate delivery IDs, and bursts over the per-minute rate limit
- **PR gating**: CI auto-healing now always opens a PR only, disables auto-merge, applies the `gedos-bot` label, and adds a verification checklist to the PR body
- **Destructive command confirmation**: risky commands now require explicit confirmation before Telegram task execution in strict mode
- **Kill switch hardening**: the shared stop signal now uses `asyncio.Event()` so `/stop` reliably interrupts multi-step work between steps
- **Dry-run planning**: multi-step task execution now shows a plan preview and requires confirmation before the first step runs
- **Security regression coverage**: added focused security tests for shell injection blocking, Telegram auth enforcement, and webhook replay/rate limiting

### Validation
- **Test suite**: all tests pass after hardening, including the new security coverage (`88 passed`)

## [0.9.6] — 2026-03

### Added
- **GitHub webhook receiver**: added `core/github_webhook.py` to accept signed `workflow_run` failure events from GitHub
- **CI self-healing**: added `core/ci_healer.py` to fetch failure logs, analyze errors, ask the LLM for a fix, and validate the result locally
- **Auto PR flow**: when the local verification passes, Gedos can commit the fix, push a branch, and open a pull request automatically
- **Webhook test coverage**: added unit tests for signature validation, event filtering, and CI healer dispatch
- **CI healer test coverage**: added unit tests for log parsing, fix application, PR creation decisions, and user notifications

### Enhanced
- **CLI startup**: added `--webhook` so Gedos can run the GitHub webhook server alongside the Telegram bot
- **Telegram integration**: added `/github status` and `/github connect` plus CI success/failure notifications sent through Telegram

### Validation
- **Test suite**: expanded the passing suite from 71 to 80 tests, including the new webhook and CI healer coverage

## [0.9.5] — 2026-03

### Added
- **MCP server**: introduced `core/mcp_server.py` so Gedos can run as a Model Context Protocol server over stdio
- **MCP tool surface**: exposed 6 tools for terminal execution, application launching, web browsing, screen reading, LLM queries, and task history access
- **MCP test coverage**: added mock-based unit coverage for MCP server initialization and all 6 MCP tools in `tests/test_mcp_server.py`

### Enhanced
- **CLI startup**: added `--mcp` to `gedos.py` so Gedos can run in Telegram mode or MCP mode from the same entrypoint
- **Integration docs**: documented Claude Desktop and Cursor setup in `docs/mcp.md` and linked the quick-start snippets from `README.md`
- **Telegram discoverability**: `/ping` and `/help` now mention MCP availability and how to connect

### Validation
- **Runtime check**: verified `python gedos.py --mcp` starts cleanly without startup errors
- **Test suite**: expanded the passing suite from 64 to 71 tests, including the new MCP coverage

## [0.9.4] — 2026-03

### Fixed
- **Test suite stability**: resolved all collection errors and restored the full suite to 64 passing tests
- **Multi-step execution tests**: fixed step retry coverage, cancellation behavior, and working-directory persistence across terminal steps
- **Copilot and routing tests**: aligned Copilot assertions, web routing expectations, and pilot cancellation tests with real behavior

### Enhanced
- **Language polish**: audited Telegram user-facing messaging and routed the active command responses through `interfaces/i18n.py`
- **i18n completeness**: added an import-time completeness check to ensure `en`, `pt`, and `es` stay in sync for all defined keys
- **Voice transcription**: passes the detected user language as a hint to local Whisper before transcription
- **Copilot context awareness**: improved suggestions for VS Code, Terminal errors, GitHub PR pages, Finder, and idle-state prompts
- **Copilot controls**: added `/copilot status` and `/copilot sensitivity high|medium|low`, with strict per-user cooldown handling

### Security
- **Security audit**: verified no hardcoded `/Users/santiago` paths and no obvious hardcoded token patterns in Python sources
- **Dead code cleanup**: removed an unused production import and confirmed there are no stray debug `print()` calls or untracked TODO comments in production code

---

## [0.9.3] — 2026-03

### Added
- **Scheduled tasks**: `/schedule`, `/schedules`, `/unschedule` with APScheduler and SQLite persistence
- **Voice input**: send voice messages as task input, transcribed locally via Whisper
- **Natural language schedule parsing**: "every day at 9am", "tomorrow at 3pm", "every monday at 9am"
- **Timezone support**: system timezone detection for scheduler
- **Rich table for /schedules**: clean formatted output
- **Voice polish**: typing indicator, memory logging, edge cases (empty, >60s, background noise)
- **Tests**: `tests/test_scheduler.py` and `tests/test_voice.py`

### Enhanced
- **/schedule**: supports both explicit (daily 09:00) and natural language formats
- **Voice handler**: rejects empty/long messages, detects background noise, logs to memory

---

## [0.9.2] — 2026-03

### Added
- **Error recovery system**: multi-step tasks now retry failed steps once automatically
- **User decision prompts**: when retry fails, Gedos asks "Continue anyway? /yes /no" 
- **Self-correction for terminal**: failed terminal commands are automatically corrected using LLM and retried
- **New commands**: `/yes` and `/no` for responding to step failure prompts
- **Graceful cancellation**: `/stop` now cancels multi-step tasks between steps cleanly
- **Integration tests**: comprehensive test suite for multi-step execution, retry logic, and self-correction (`tests/integration/test_multistep.py`)

### Enhanced
- **Multi-step execution**: more robust with automatic error handling and user interaction
- **Terminal agent**: "errando e se corrigindo" behavior - learns from mistakes and fixes commands automatically
- **Task cancellation**: improved mid-execution stopping with proper cleanup

---

## [0.9.1] — 2026-03

### Fixed
- **agents/web_agent.py**: confirmed async_playwright() migration complete, fully compatible with asyncio loop
- **interfaces/telegram_bot.py**: _check_rate_limit function properly defined and working (10 commands/min per user)
- **config.yaml**: default LLM model confirmed as llama3.2 for optimal performance
- **.env.example**: LLM_PROVIDER and OLLAMA_MODEL defaults properly set for new installations

---

## [0.9.0] — 2026-03

### Added
- **Documentation overhaul**: complete README with logo, architecture diagram, modes, commands, LLM config
- **docs/setup-ollama.md**: full Ollama setup guide with install steps, recommended models, troubleshooting
- **docs/examples.md**: 5 real usage examples with exact Telegram commands and expected outputs
- **docs/demo-placeholder.md**: placeholder for real demo GIF (to be recorded before v1.0)
- **Integration tests**: pilot flow, copilot flow, orchestrator routing (`tests/integration/`)
- **CHECKLIST.md**: pre-launch checklist for v0.9.0 RC validation
- **Security baseline**:
  - Input sanitization (`core/security.py`) — blocks dangerous shell patterns, validates URLs
  - Rate limiting (10 commands per minute per user) in Telegram bot
  - API key validation on startup — fail fast with clear error if keys missing
  - Logging audit — confirmed no secrets logged anywhere
- **README badges**: License, Python version, Ollama LLM
- **README sections**: Quick Start, Commands table, Architecture, Modes (Pilot vs Copilot), LLM Configuration, Tech Stack, Contributing, Roadmap

### Changed
- **README.md**: complete overhaul with `>gedos` logo, ASCII architecture diagram, command table, modes explained
- **`gedos.py`**: validate API keys before starting bot
- **`interfaces/telegram_bot.py`**: rate limiting applied to all commands

### Security
- Input sanitization for shell commands, URLs, and Telegram input
- Rate limiting prevents abuse (10 commands/min per user)
- API keys validated on startup
- No API keys or tokens logged

---

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
