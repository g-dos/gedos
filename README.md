# Gedos

[![CI](https://github.com/g-dos/gedos/actions/workflows/test.yml/badge.svg)](https://github.com/g-dos/gedos/actions/workflows/test.yml)
[![Version](https://img.shields.io/badge/version-v0.9.16-blue.svg)](https://github.com/g-dos/gedos/releases)
[![Coverage](https://codecov.io/gh/g-dos/gedos/branch/main/graph/badge.svg)](https://codecov.io/gh/g-dos/gedos)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![macOS](https://img.shields.io/badge/macOS-12%2B-lightgrey.svg)](https://www.apple.com/macos/)

Your Mac. Working while you're not.

Gedos is an open-source autonomous AI agent built for developers and operators on macOS.
It executes tasks, watches context, and acts proactively across terminal, web, voice, and GitHub flows.
Unlike generic chat assistants, Gedos is local-first, privacy-aware, and macOS-native by design.
You can run it in CLI, Telegram, MCP, or webhook modes.

![Gedos Crow](docs/assets/gedos-crow.png)

## Quick Start

```bash
brew tap g-dos/gedos
brew install gedos
gedos
```

```text
> what files are on my desktop?
> open VS Code
> what's the weather in São Paulo today?
```

Demo GIF coming with v1.0.0 launch · [Full setup guide](docs/setup.md)

## What Gedos does

**Pilot Mode** runs autonomous tasks from Telegram and reports every step.
```text
You: /task run pytest and tell me if the branch is safe to merge
Gedos:
⚙️ Running step 1/2...
✅ Step 1/2: pytest — 193 passed
⚙️ Running step 2/2...
✅ Step 2/2: git status — clean
✓ Done in 5.1s
```

**Copilot Mode** reacts to your screen context and suggests actions in real time.
```text
You:   [opens VS Code, error visible on screen]

Gedos: 💡 I see errors in auth.py. Want me to fix them?
You:   yes
Gedos: ✅ Fixed TypeError on line 47. Tests passing.
```

**Self-healing CI** receives failure context, applies a fix, runs tests, and opens a PR.
```text
You:   [pushed a bug and went to sleep 🌙]

Gedos: 🔴 CI failed on main — test_scheduler_parse
       💡 Root cause: assertion expects hour=10, returns 9
       🔧 Fix applied and tested locally (193 passed)
       ✅ PR #42 opened → github.com/g-dos/gedos/pull/42
```

**MCP Server** exposes your Mac as a tool server for Claude, Cursor, and other MCP clients.
```bash
gedos --mcp
```

```json
{
  "mcpServers": {
    "gedos": {
      "command": "python",
      "args": ["/path/to/gedos/gedos.py", "--mcp"]
    }
  }
}
```

**Voice** supports Whisper input and voice output responses.
```text
You: [voice] "run tests and tell me if they passed"
Gedos: 🎙️ Heard: run tests and tell me if they passed. Executing...
[returns spoken summary]
```

**Semantic Memory** adds retrieval-aware context from previous conversations and task outcomes.
```text
Relevant context:
- Previous task failed on scheduler parsing
- You usually run tests after editing scheduler.py
```

**Continuous Perception** uses AXObserver events (instead of fixed polling) for faster Copilot reactions.

**Web Tool** uses Scrapling for lightweight static extraction and keeps Playwright for interactive flows.
```text
/task scrape https://example.com and get all h1 titles
```

**Scheduling** supports natural language scheduling with clear confirmations and next run previews.
```text
> /schedule every weekday at 9am "check HN and brief me"

Gedos: 📅 Every weekday at 9:00 AM — check HN and brief me
       Next run: Tomorrow, Mon at 9:00 AM ✅
```

```text
Gedos: ☀️ Good morning Santiago.

       Yesterday: ✅ deploy ran · ✅ 3 tasks completed
       Today: 2 open PRs · CI green · 1 new issue

       Anything to start with?
```

## Commands

| Command | What it does |
| --- | --- |
| `/start` | Start Gedos, pairing, and onboarding in Telegram Mode |
| `/help` | Show the full command reference |
| `/task <description>` | Run any task through the orchestrator |
| `/status` | Show the current task status |
| `/stop` | Cancel the current task |
| `/checklist` | Validate local setup and missing requirements |
| `/auditlog` | Show the latest audit log entries |
| `/web <url>` | Browse and summarize a URL |
| `/ask <question>` | Ask the configured LLM directly |
| `/memory` | Show recent task history |
| `/patterns` | Show learned behavioral patterns |
| `/forget <id>` | Remove one learned pattern |
| `/forget all` | Clear all learned patterns for the current user |
| `/copilot on` | Turn Copilot Mode on |
| `/copilot off` | Turn Copilot Mode off |
| `/copilot status` | Show Copilot state, sensitivity, and last suggestion |
| `/copilot sensitivity high\|medium\|low` | Change proactive suggestion frequency |
| `/voice on\|off\|status` | Toggle voice responses |
| `/permissions` | Show current permission level |
| `/permissions default` | Switch to Default permission mode |
| `/permissions full` | Request Full Access mode |
| `/config` | Open or locate `GEDOS.md` |
| `/ping` | Health check plus MCP availability |
| `/clear` | Clear the CLI screen |
| `/exit` | Quit CLI Mode cleanly |
| `/github status` | Show GitHub webhook server status |
| `/github connect` | Show GitHub webhook setup instructions |
| `/schedule <when> <task>` | Create a schedule from natural language |
| `/schedule history` | Show the last 5 scheduled task runs |
| `/schedules` | List active schedules with next run times |
| `/unschedule <id>` | Remove a schedule |
| `/owner status` | Show owner and allowed chat IDs |
| `/owner allow <chat_id>` | Allow another Telegram chat |
| `/owner revoke <chat_id>` | Revoke an allowed chat |
| `/yes` | Approve a pending plan, retry, or destructive action |
| `/no` | Deny a pending plan, retry, or suggestion |
| `/never` | Suppress a learned pattern suggestion permanently |

## Installation

Homebrew:
```bash
brew tap g-dos/gedos
brew install gedos
gedos
```

Manual:
```bash
git clone https://github.com/g-dos/gedos
cd gedos
pip install -r requirements.txt
python gedos.py
```

## LLM Configuration

Ollama (default, local):
```bash
brew install ollama
ollama serve
ollama pull llama3.2
```

Claude / OpenAI (optional):
```bash
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=...
```

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=...
```

Gedos stores state locally in `~/.gedos/gedos.db` (history, preferences, patterns) and supports `/export` and `/deletedata` for portability and erasure. With Ollama, task content can remain local. If you configure Claude or OpenAI, task content is sent to those providers. Gedos is open source and local-first, but autonomous modes still require operator judgment.

## Requirements

macOS 12.0+, Python 3.12+, Ollama or API key, ffmpeg (for voice).

## FAQ

### Does Gedos send my data to the cloud?
Not by default. Ollama is local-first; cloud transfer happens only if you configure Claude/OpenAI.

### Does Gedos need Telegram to work?
No. Without `TELEGRAM_BOT_TOKEN`, Gedos starts in CLI mode automatically.

### Can Gedos really control my Mac?
Yes. It can run terminal commands, browse the web, and operate macOS UI flows.

### Can I use Gedos from Claude Desktop or Cursor?
Yes. Run `gedos --mcp` and configure it as an MCP server.

### Is Gedos safe to run unattended?
Default mode keeps confirmation gates for destructive actions; Full Access should be used carefully.

### Is Gedos stable enough to run 24/7?
Current baseline is 200+ passing tests and continuous runs on macOS developer setups; start in Default mode first.

## Contributing + License + Built by

Contributing: see [CONTRIBUTING.md](CONTRIBUTING.md).  
License: Apache 2.0.  
Built by Guilherme Santiago — @g-dos.
