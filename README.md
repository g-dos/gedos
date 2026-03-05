# Gedos

```text
 _____          _           
|  __ \        | |          
| |  \/ ___  __| | ___  ___ 
| | __ / _ \/ _` |/ _ \/ __|
| |_\ \  __/ (_| | (_) \__ \
 \____/\___|\__,_|\___/|___/
                            
                            
```

[![CI](https://github.com/g-dos/gedos/actions/workflows/test.yml/badge.svg)](https://github.com/g-dos/gedos/actions/workflows/test.yml)
[![Coverage](https://codecov.io/gh/g-dos/gedos/branch/main/graph/badge.svg)](https://codecov.io/gh/g-dos/gedos)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![macOS](https://img.shields.io/badge/macOS-12%2B-lightgrey.svg)](https://www.apple.com/macos/)
[![Local-first AI](https://img.shields.io/badge/AI-local--first-green.svg)](https://ollama.ai)

## Quick Start

```bash
brew tap g-dos/gedos
brew install gedos
gedos
```

**Test drive in 30 seconds** (no config needed):
```text
> what files are on my desktop?
> open VS Code
> what's the weather in São Paulo today?
```

→ [Watch the demo](#) · [Full setup guide](docs/setup.md)

**Your Mac. Working while you're not.**

Gedos is an open-source autonomous AI agent that lives on your Mac.
It reads your screen, controls mouse and keyboard, executes commands,
browses the web, learns your workflows, fixes your bugs while you sleep,
and gives any AI hands to control your computer.

Local. Private. Open source.

---

## Install

**Via Homebrew (recommended):**

```bash
brew tap g-dos/gedos
brew install gedos
gedos
```

**Manual:**

```bash
git clone https://github.com/g-dos/gedos
cd gedos && pip install -r requirements.txt
python gedos.py
```

---

## What Gedos can do

## Real-world examples

**Self-healing CI — while you sleep:**
```text
You:   [pushed a bug and went to sleep 🌙]

Gedos: 🔴 CI failed on main — test_scheduler_parse
       💡 Root cause: assertion expects hour=10, returns 9
       🔧 Fix applied and tested locally (193 passed)
       ✅ PR #42 opened → github.com/g-dos/gedos/pull/42
```

**Copilot Mode — real-time suggestions:**
```text
You:   [opens VS Code, error visible on screen]

Gedos: 💡 I see errors in auth.py. Want me to fix them?
You:   yes
Gedos: ✅ Fixed TypeError on line 47. Tests passing.
```

**Morning briefing — proactive:**
```text
Gedos: ☀️ Good morning Santiago.

       Yesterday: ✅ deploy ran · ✅ 3 tasks completed
       Today: 2 open PRs · CI green · 1 new issue

       Anything to start with?
```

**MCP — give Claude hands on your Mac:**
```bash
gedos --mcp
# Now Claude Desktop can control your Mac as a tool
```

**Natural language scheduling:**
```text
> /schedule every weekday at 9am "check HN and brief me"

Gedos: 📅 Every weekday at 9:00 AM — check HN and brief me
       Next run: Tomorrow, Mon at 9:00 AM ✅
```

### 🤖 Pilot Mode
Send a task from anywhere. Gedos executes on your Mac and reports back.

```text
You: /task run pytest and tell me if the branch is safe to merge
Gedos:
⚙️ Running step 1/2...
✅ Step 1/2: pytest — 193 passed
⚙️ Running step 2/2...
✅ Step 2/2: git status — clean
✓ Done in 5.1s
```

### 👥 Copilot Mode
Monitors your screen in real-time and suggests actions as you work.

```text
[You open VS Code on a failing test]
Gedos: 💡 I see an error. Want me to fix it?
You: yes
Gedos: Running tests, checking traceback, and preparing a fix.
```

### 🔧 Self-healing CI
CI broke at 3am? Gedos reads the error, fixes the code,
runs tests, and opens a PR. You wake up to a green build.

```text
🔧 CI failure detected on g-dos/gedos/main
Error: tests/test_scheduler.py failed on assertion
Fix applied: updated scheduler parser and test coverage
Tests: ✅ passing
PR #42 opened: https://github.com/g-dos/gedos/pull/42
```

### 🧠 Contextual Memory
Learns your workflows over time and acts proactively.

```text
💡 I noticed a pattern:
After git commit -> you usually push.
Want me to automate this?
```

### 🎙️ Voice
Send a voice message. Gedos transcribes, executes, responds by voice.

```text
You: [voice] "run tests and tell me if they passed"
Gedos: 🎙️ Heard: run tests and tell me if they passed. Executing...
[returns spoken summary]
```

### 🔌 MCP Server
Exposes your Mac as an MCP server. Claude, Cursor, GPT —
any LLM can use your Mac as a tool.

```bash
gedos --mcp
```

**Claude Desktop**

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

**Cursor**

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

### ⏰ Scheduled Tasks
Natural language scheduling.

```text
/schedule every weekday at 9am "check HN and brief me"
/schedule every friday at 5pm "run tests and deploy if green"
/schedule in 30 minutes "remind me to review the PR"
```

---

## Commands

| Command | What it does |
| --- | --- |
| `/start` | Start Gedos, pairing, and onboarding in Telegram Mode |
| `/help` | Show the full command reference |
| `/task <description>` | Run any task through the orchestrator |
| `/status` | Show the current task status |
| `/stop` | Cancel the current task |
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

---

## Architecture

```text
           User (CLI / Telegram / MCP / Webhook)
                         |
      +------------------+------------------+
      |                  |                  |
   CLI Mode         Telegram Bot        MCP Server
      |                  |                  |
      +------------------+------------------+
                         |
                 Orchestrator (LangGraph)
                         |
     +-----------+-------+--------+------------+
     |           |                |            |
 Terminal     GUI Agent        Web Agent      LLM
  Agent       (AX Tree)       (Playwright)   Layer
     |                                         |
     +-------------------+---------------------+
                         |
                 Memory Layer (SQLite)
                         |
      +-------------+----+-----+---------------+
      |             |          |               |
 Behavior Tracker  Scheduler  CI Healer   Security Layer
      |             |          |               |
      +-------------+----------+---------------+
                         |
                Proactive Suggestions / History
```

---

## Modes

CLI Mode — zero config, runs immediately, no Telegram needed

Telegram Mode — auto-activates when `TELEGRAM_BOT_TOKEN` is in `.env`

MCP Mode — `gedos --mcp`

Webhook Mode — `gedos --webhook`

---

## LLM Configuration

Gedos uses Ollama by default.

```bash
brew install ollama
ollama serve
ollama pull llama3.2
```

Optional cloud providers:

```bash
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=...
```

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=...
```

## Privacy

Gedos stores local state in `~/.gedos/gedos.db`, including task history, learned patterns, and user preferences.

Use `/export` to download your stored data and `/deletedata` to erase it locally.

When using Ollama, task content can stay local. If you configure Claude or OpenAI, task content may be sent to those providers.

---

## Requirements

macOS 12.0+, Python 3.12+, Ollama or API key, ffmpeg (for voice)

---

## Tech Stack

| Component | Technology |
| --- | --- |
| Language | Python 3.12+ |
| Orchestration | LangGraph |
| Browser automation | Playwright |
| Telegram | python-telegram-bot |
| Memory | SQLite + SQLAlchemy |
| Scheduler | APScheduler |
| Local LLM | Ollama |
| Cloud LLMs | Claude API, OpenAI API |
| Voice input | Whisper |
| Voice output | gTTS + pydub + ffmpeg |
| Natural language scheduling | parsedatetime + pytz + tzlocal |
| MCP | `mcp` Python SDK |
| GitHub automation | Flask + PyGithub |
| Language detection | langdetect |
| Screen understanding | macOS Accessibility Tree (AX) |

---

## FAQ

### Does Gedos send my data to the cloud?
Not by default. Ollama is the default provider, so everything can stay local unless you explicitly configure Claude or OpenAI.

### Does Gedos need Telegram to work?
No. If no Telegram token is configured, Gedos starts in CLI Mode automatically.

### Can Gedos really control my Mac?
Yes. Gedos can execute terminal commands, browse the web, read the AX Tree, and control GUI interactions on macOS.

### Can I use Gedos from Claude Desktop or Cursor?
Yes. Run `gedos --mcp` and connect it as an MCP server. See [docs/mcp.md](docs/mcp.md).

### Is Gedos safe to run unattended?
It is designed with confirmations, shell hardening, owner pairing, and strict mode by default, but Full Access mode and autonomous workflows still require judgment.

### Is Gedos stable enough to run 24/7?
Gedos runs 24/7 in background on my Mac without crashes in common scenarios (209+ tests passing, tested on macOS 13/14/15 with Ollama + Llama 3.2). In Full Access mode, use with caution — always review autonomous actions at first. Default mode requires confirmation for destructive commands.

---

## Future

v1.0.0 -> Launch

v1.1.0 -> Linux support

v1.2.0 -> Multi-Mac

v2.0.0 -> Gedos GUI app

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

Apache 2.0

---

Built by Guilherme Santiago - @g-dos
