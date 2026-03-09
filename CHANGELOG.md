# Changelog

All notable changes to Gedos are documented here.  
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)

---

## [Unreleased]

---

## [0.9.16] — 2026-03-09
### Added
- CI matrix for Python 3.12 and 3.13
- Smoke E2E test suite (tests/e2e/)
- Optional dependency groups in pyproject.toml (semantic, web, voice, dev, all)
### Fixed
- datetime.utcnow() deprecation warnings across all modules
### Improved
- Coverage enforcement configured globally
- pip cache added to CI for faster runs

---

## [0.9.15] — 2026-03-09
### Added
- Semantic memory layer (ChromaDB + Ollama embeddings) — episodic, session, and pattern memory
- Event-driven screen perception via AXObserver (replaces 10s polling in Copilot Mode)
- Kokoro TTS local synthesis (replaces gTTS as primary, gTTS remains fallback)
- Web scraping tool via Scrapling (optional dependency, `pip install scrapling`)

---

## [0.9.13] — 2026-03-04
### Added
- GitHub Actions CI workflow with coverage reporting
- `/checklist` command: visual setup validation
- JSON audit log (`~/.gedos/audit.log`) with `/auditlog` command
- GitHub issue templates (bug, feature, copilot feedback)
- Badges: CI, coverage, license, Python, macOS, Local-first AI
- Quick Start section in README
- Real-world showcase examples with before/after
- ROADMAP.md with milestones
- GitHub Discussions enabled

### Changed
- README restructured for faster first impression
- FAQ expanded with stability promise

---

## [0.9.12.1] — 2026-03-04
### Fixed
- `shell=True` removed from `gui_agent.py`
- GitHub watcher no longer replays all items on first poll
- `/export` command for data portability (GDPR/LGPD)
- `/deletedata` command for full account erasure
- Privacy notice added to onboarding
- Data retention policy (90-day auto-cleanup)
- CLI oversized input rejection
- Telegram task overlap prevention

### Security
- Proactive notifications sanitized before delivery
- Unsanitized external content blocked from notifications

---

## [0.9.12] — 2026-03-04
### Added
- Proactive Engine with 4 background watchers
- `system_watcher`: CPU, disk, memory, stuck process alerts
- `github_watcher`: issues, PRs, CI failure notifications
- `idle_watcher`: 10-minute idle detection, end-of-day suggestions
- `morning_briefing`: daily briefing at learned start time
- Custom permissions level (allow/confirm/block per category)
- Copilot polling: 10s/30s/120s sensitivity tiers

---

## [0.9.11.1] — 2026-03-04
### Added
- `pyproject.toml` packaging metadata for Homebrew/Python packaging support

### Changed
- Homebrew installation path aligned with Python package entrypoint expectations

---

## [0.9.11] — 2026-03-04
### Added
- Homebrew formula (`Formula/gedos.rb`)
- `--version` support in `gedos.py` for packaging tests
- Homebrew installation guide (`docs/homebrew.md`)

### Changed
- README install section updated for Homebrew-first onboarding

---

## [0.9.10] — 2026-03-04
### Added
- Natural-language schedule parsing (20+ expressions)
- Timezone auto-detection and per-user timezone storage
- `/schedule history` command (last 5 scheduled runs)

### Changed
- Rich `/schedule` confirmation with next run preview
- Redesigned `/schedules` output with improved readability
- `/unschedule` confirmation now includes removed schedule details
- Fixed `daily 9am` parsing

---

## [0.9.9] — 2026-03-04
### Added
- CLI Mode auto-activation when Telegram token is missing
- First-run onboarding (name, preferences, permissions, Telegram optional setup)
- `~/.gedos/GEDOS.md` personal configuration file
- ASCII startup banner with mode/model/version line

### Changed
- Redesigned CLI `/help` with full command reference
- Added `/permissions` command in CLI and Telegram
- Added `/config` command to open or locate `GEDOS.md`
- Multi-step plan/progress output polished for demo quality

---

## [0.9.8] — 2026-03-04
### Added
- Voice output via gTTS with Telegram OGG delivery
- `/voice on|off|status` command
- CLI voice playback support via `afplay`

### Changed
- Speech-safe text formatter for markdown stripping/truncation
- Voice fallback to text responses when synthesis fails

---

## [0.9.7] — 2026-03-04
### Added
- Behavior tracker with pattern learning from task history
- Pattern types: time-based, context-based, workflow-based
- `/patterns` command with confidence scores
- Pattern suppression (`never suggest again`) flow

### Changed
- Proactive suggestions now include learned behavior patterns
- `/forget <id>` and `/forget all` pattern cleanup flow finalized

---

## [0.9.6.3] — 2026-03-04
### Security
- Restricted `cat/find/cp/mv/ls` to safe path patterns
- Removed `env` from allowed executables
- Blocked dangerous git operations (`clone`, `submodule`, `-c`, etc.)
- Blocked network-listening Python modules (`http.server`, `smtpd`, etc.)
- Added command length limit (1000 chars)
- Added LLM security system prompt and task planner sanitization
- Blocked CI healer path traversal and unsafe LLM-generated fixes
- Scoped MCP task history per client
- Blocked unsafe URL schemes (`ftp://`, `file://`, `javascript:`, etc.)

---

## [0.9.6.2] — 2026-03-04
### Security
- One-time generated pairing code when `PAIRING_CODE` is not set
- Blocked `pip install` local-path traversal (`../`, `~/`, `/tmp`, `file:`)
- Blocked unsafe git flags (`--exec-path`, path-valued long flags)
- Enforced `0600` permissions on `gedos.db`
- Added webhook repo/branch sanitization
- Scoped task history by `user_id`
- Implemented `/forget all` for user-scoped pattern deletion
- Blocked NUL byte and non-printable command payloads
- Added unauthorized chat log rate limiting

---

## [0.9.6.1] — 2026-03-04
### Security
- Mandatory command sanitization before terminal execution
- `shell=False` execution path for safer command handling
- Telegram owner pairing + unauthorized chat blocking
- Webhook replay protection (timestamp, nonce, rate limit)
- CI healer PR gating (`auto_merge: false`, `gedos-bot` label, checklist)
- Destructive action confirmation flow
- Kill-switch hardening with global stop event checks
- Dry-run plan confirmation before multi-step execution

---

## [0.9.6] — 2026-03-04
### Added
- GitHub webhook receiver (`/webhook`) for CI failures
- CI self-healing core flow with LLM-assisted fix attempts
- Auto-PR flow when local tests pass
- `--webhook` runtime flag
- `/github status` and `/github connect` commands
- Telegram CI success/failure notifications

---

## [0.9.5] — 2026-03-04
### Added
- MCP server implementation (`gedos --mcp`)
- 6 MCP tools exposed (terminal, app, web, screen, llm, history)
- Claude Desktop and Cursor integration docs

### Changed
- Telegram `/ping` and `/help` updated to surface MCP availability

---

## [0.9.4] — 2026-03-04
### Fixed
- Pytest collection issues resolved (`gedos-demo` exclusion and missing modules)
- Integration test failures fixed (Copilot assertions, context return shape, terminal cwd flow)
- Retry-path hanging test fixed in multistep flow

### Added
- Language polish pass with broader i18n coverage (`en/pt/es`)
- Copilot status/sensitivity controls and richer contextual suggestions
- Security and dead-code cleanup pass

---

## [0.9.3] — 2026-03-04
### Added
- Scheduled tasks (`/schedule`, `/schedules`, `/unschedule`) with APScheduler + SQLite
- Voice input pipeline with Whisper transcription
- Natural-language schedule parsing and timezone-aware execution
- Improved schedule display and voice edge-case handling

---

## [0.9.2] — 2026-03-04
### Added
- Multi-step task planner and orchestrator execution flow
- Step retry and user decision controls (`/yes`, `/no`)
- Terminal self-correction loop for failed commands
- Telegram progress updates for multi-step tasks

---

## [0.9.1] — 2026-03-04
### Fixed
- Async Playwright integration stability
- Telegram rate limiting reliability
- LLM model/config defaults alignment
- `.env.example` baseline configuration improvements
