# >gedos

**Your Mac. Working while you're not.**

Gedos is an open-source autonomous AI agent that runs natively on macOS. It reads the screen via the macOS Accessibility Tree, controls mouse and keyboard, executes terminal commands, browses the web, and communicates with you via Telegram.

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Ollama](https://img.shields.io/badge/LLM-Ollama-green.svg)](https://ollama.com)

---

## Demo

> **Note**: Real demo GIF will be recorded and added before v1.0 launch.  
> See [docs/demo-placeholder.md](docs/demo-placeholder.md) for instructions.

---

## Quick Start

```bash
# Clone the repository
git clone https://github.com/g-dos/gedos.git
cd gedos

# Install dependencies
pip install -r requirements.txt

# Install and start Ollama (default LLM)
brew install ollama
ollama serve
ollama pull llama3.3

# Install Playwright browsers (for web tasks)
playwright install chromium

# Configure Telegram bot
cp .env.example .env
# Add your Telegram bot token to .env

# Run Gedos
python gedos.py
```

Send `/start` to your bot on Telegram to begin.

**Full setup guide**: [docs/setup-ollama.md](docs/setup-ollama.md)

---

## Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/start` | Welcome message and setup guide | `/start` |
| `/help` | List all commands (context-aware) | `/help` |
| `/task <description>` | Execute any task autonomously | `/task git status` |
| `/status` | Check current task status | `/status` |
| `/stop` | Stop running task | `/stop` |
| `/copilot on\|off` | Enable/disable Copilot Mode | `/copilot on` |
| `/memory` | View recent task history | `/memory` |
| `/web <url>` | Browse the web | `/web google.com` |
| `/ask <question>` | Ask the LLM (local by default) | `/ask what is Python?` |
| `/ping` | Health check | `/ping` |

**More examples**: [docs/examples.md](docs/examples.md)

---

## Architecture

```
┌─────────────────────────────────┐
│    Telegram Interface (User)    │
└───────────────┬─────────────────┘
                │
        ┌───────▼────────┐
        │  Orchestrator  │
        │   (LangGraph)  │
        └───────┬────────┘
                │
    ┌───────────┼───────────┬────────────┐
    │           │           │            │
┌───▼────┐ ┌───▼────┐ ┌───▼────┐ ┌────▼─────┐
│Terminal│ │  GUI   │ │  Web   │ │   LLM    │
│ Agent  │ │ Agent  │ │ Agent  │ │  Agent   │
│ (shell)│ │(AX Tree│ │(Browser│ │ (Ollama/ │
│        │ │+mouse) │ │        │ │ Claude)  │
└────────┘ └────────┘ └────────┘ └──────────┘
                │
        ┌───────▼────────┐
        │ Memory Layer   │
        │    (SQLite)    │
        └────────────────┘
```

### Components

- **Orchestrator**: Central brain using LangGraph. Routes tasks to the appropriate agent.
- **Terminal Agent**: Executes shell commands (`git`, `npm`, `python`, any CLI tool).
- **GUI Agent**: Reads screen via AX Tree and controls mouse/keyboard via macOS Accessibility APIs.
- **Web Agent**: Browses the web using Playwright.
- **LLM Agent**: Answers questions using Ollama (local, default) or Claude/OpenAI (cloud, optional).
- **Memory Layer**: Persists task history and context using SQLite + SQLAlchemy.

---

## Modes

Gedos operates in two distinct modes:

### 🤖 Pilot Mode (Default)
Fully autonomous. Send a task, leave, Gedos executes and reports back when done.

**Example**:
```
You: /task git status
Gedos: On branch main. Your branch is up to date. Nothing to commit.
```

**Use cases**:
- Run terminal commands remotely
- Execute tasks while away from your Mac
- Automate repetitive workflows

---

### 👥 Copilot Mode
Proactive real-time assistant. Gedos monitors your screen and suggests actions as you work.

**Example**:
```
[You open VS Code]
Gedos: 💡 Want me to commit, run tests, or search for something?
You: run tests
Gedos: Running: pytest
      === 22 passed in 1.84s ===
      ✓ All tests passing.
```

**Enable Copilot Mode**:
```
/copilot on
```

**How it works**:
- Checks active app every 10 seconds (configurable)
- Detects context (Terminal, VS Code, Safari, etc.)
- Proactively suggests next steps
- Warns when errors appear on screen

**Disable**:
```
/copilot off
```

---

## LLM Configuration

Gedos uses **Ollama** by default — fully local, no API key required, no data sent to the cloud.

### Using Ollama (Default)

```bash
# Install
brew install ollama

# Start server
ollama serve

# Pull recommended model
ollama pull llama3.3
```

**Supported models**: `llama3.3`, `mistral`, `codellama`, `deepseek-coder`, `qwen2.5`

**Full guide**: [docs/setup-ollama.md](docs/setup-ollama.md)

---

### Using Cloud LLMs (Optional)

To use Claude or OpenAI instead, add your API key to `.env`:

```bash
# For Claude
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-...

# For OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

Restart Gedos after changing `.env`.

---

## Requirements

- **macOS** 12.0+ (Monterey or later)
- **Python** 3.12+
- **Ollama** (or Claude/OpenAI API key)
- **Telegram Bot Token** ([create one](https://t.me/BotFather))
- **Accessibility Permissions** (System Settings > Privacy & Security > Accessibility > Terminal)

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.12 |
| Orchestration | LangGraph |
| Screen Reading | atomacos / pyobjc (AX Tree) |
| Mouse & Keyboard | PyAutoGUI + macOS Accessibility API |
| Browser Automation | Playwright |
| Telegram Interface | python-telegram-bot |
| Memory | SQLite + SQLAlchemy |
| Local LLM | Ollama |
| Cloud LLM (optional) | Claude API / OpenAI API |
| CLI | Rich (colored output) |

---

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for:
- How to clone and run locally
- Code style guidelines
- How to submit a PR
- Semantic commit reference

---

## License

Apache 2.0 — see [LICENSE](LICENSE)

---

## Roadmap

- **v0.9.0** (current): Release Candidate — feature freeze, documentation, integration tests
- **v1.0.0**: Public launch 🚀
- **v1.x**: Linux support
- **v2.0**: Gedos GUI app (Electron/Tauri) for non-devs
- **Future**: Gedos Cloud (hosted, zero setup)

See [CHANGELOG.md](CHANGELOG.md) for version history.

---

## Built By

**Guilherme Santiago** — [@g-dos](https://github.com/g-dos)

---

**Gedos** — your Mac, working while you're not.
