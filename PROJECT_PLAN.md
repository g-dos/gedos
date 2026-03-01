# PROJECT_PLAN.md — Gedos Execution Plan

> This file is for AI agents working on this codebase.
> Read this alongside AGENTS.md before doing anything.
> Do not invent roadmap items. Do not change version targets. Follow this exactly.

---

## Current State

- **Version**: v0.6.0 ✅
- **Status**: Production-ready MVP
- **Lines**: 2,864 Python + 14 Markdown
- **Tests**: 22/22 passing
- **Repo**: g-dos/gedos

---

## Non-Negotiable Rules

- Never add features outside the current version scope
- Never change the roadmap order
- Never invent dates — dates are not defined intentionally
- Never remove docs, examples, or assets unless explicitly instructed
- Every version must be demo-able before moving to the next
- Semantic commits only: feat / fix / chore / docs / refactor
- Bump version in gedos.py AND config.yaml on every release
- Update CHANGELOG.md on every release

---

## Completed Milestones

| Version | Description |
|---|---|
| v0.1.0 | Telegram bot, Terminal Agent, AX Tree, GUI Agent, AGENTS.md |
| v0.2.0 | Web Agent, Memory Layer, LangGraph Orchestrator, LLM routing |
| v0.3.0 | Full Copilot Mode, proactive suggestions, stability |
| v0.4.0 | Pytest smoke tests, timeouts, error messages, hardening |
| v0.5.0 | Documentation (CONTRIBUTING.md, README final, docs/) |
| v0.6.0 | Retry logic, structured logging, graceful failures, Rich CLI |

---

## Roadmap — Do Not Alter

### v0.7.0 — UX do Usuário
Scope: improve the user experience inside Telegram and CLI. No new agents.

- [ ] Onboarding via /start — guide user from zero (ask for mode, explain commands)
- [ ] /help detailed by mode — different output for Pilot vs Copilot
- [ ] Progress updates during long tasks — Gedos sends intermediate messages
- [ ] /task cancel — interrupt running task mid-execution gracefully
- [ ] CLI: better error output with Rich (tracebacks formatted, not raw)
- [ ] Bump version to 0.7.0, update CHANGELOG

---

### v0.8.0 — Performance Local-First
Scope: make Gedos faster and leaner. No new features.

- [ ] AX Tree cache for static apps — don't re-read unchanged UI
- [ ] Benchmark Ollama vs Claude vs OpenAI — log response times per provider
- [ ] Reduce startup time — lazy load agents, only init what's needed
- [ ] Memory usage profiling — no memory leaks in long-running sessions
- [ ] Configurable polling interval for Copilot context analysis
- [ ] Bump version to 0.8.0, update CHANGELOG

---

### v0.9.0 — Release Candidate
Scope: freeze features, record demo, prepare for public launch.

- [ ] Feature freeze — absolutely no new features in this version
- [ ] Record real demo GIF — Gedos working live (Kap or Gifox on Mac)
  - Show: Telegram message → Gedos executes → reports back
  - Place at docs/demo.gif
  - Add to README replacing any placeholder
- [ ] docs/setup-ollama.md — step by step Ollama install + recommended models
- [ ] docs/examples.md — 5 real usage examples
- [ ] End-to-end integration tests
- [ ] README final review — must work from a fresh clone by someone outside the project
- [ ] Zero open critical issues
- [ ] Bump version to 0.9.0, update CHANGELOG

---

### v1.0.0 — Public Launch 🚀
Scope: tag, release, and distribute. No code changes unless critical bug.

- [ ] GitHub Release v1.0.0 with full changelog
- [ ] Post on Hacker News — "Show HN: Gedos — autonomous agent for macOS"
- [ ] Reddit: r/MachineLearning, r/LocalLLaMA, r/programming
- [ ] Twitter/X thread with demo GIF
- [ ] Open GitHub Sponsors + OpenCollective

---

## Post-Launch Triggers (do not build before these conditions are met)

| Condition | Action |
|---|---|
| v1.0 launched | Open GitHub Sponsors + OpenCollective |
| 500+ stars | Apply for grants (Anthropic, GitHub, AWS) |
| 1k+ stars | Gedos Cloud waitlist — simple landing page, Railway deploy |
| 5k+ stars | First hire — not a dev, whoever covers what you hate most |
| Cloud running | Apply to YC with real traction |
| $1M ARR | Begin Gedos OS development |

---

## Future Versions (after v1.0, not planned in detail yet)

- **v1.x** — Linux support
- **v2.0** — Gedos GUI app (Electron or Tauri) for non-devs
- **Gedos Cloud** — hosted version, zero setup, Stripe billing
- **Gedos OS** — dedicated Linux distro, Gedos integrated at system level

---

## Architecture Reference

```
Telegram Interface
       ↓
Orchestrator (LangGraph)
       ↓
┌──────┬──────┬──────┐
↓      ↓      ↓      ↓
Terminal  GUI   Web   LLM
Agent   Agent  Agent (Ollama/Claude/OpenAI)
       ↓
Memory Layer (SQLite + SQLAlchemy)
       ↓
Copilot Context Analysis
```

---

## Modes

- **Pilot Mode** — fully autonomous, user sends task and leaves
- **Copilot Mode** — proactive, user is at the desk, Gedos assists in real time via Telegram side chat

---

## LLM Strategy

- Default: Ollama (local, free, private)
- Optional: Claude API or OpenAI API via user-provided key in .env
- Never use cloud LLM by default
- Never send data to cloud without explicit user configuration

---

## Branding

- Name: Gedos
- Tagline: "Your Mac. Working while you're not."
- Logo: >gedos (terminal prompt aesthetic, black and white)
- License: Apache 2.0 (core) — proprietary for Cloud
- Creator: Guilherme Santiago — @g-dos

---

*Last updated: v0.6.0*
*Built by [@g-dos](https://github.com/g-dos)*
