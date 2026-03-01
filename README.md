# Gedos

> Your Mac. Working while you're not.

Gedos is an open-source autonomous AI agent that runs on your Mac. It reads the screen (AX Tree), controls mouse and keyboard, runs terminal commands, browses the web, and talks to you on Telegram — in **Pilot Mode** (autonomous tasks) or **Copilot Mode** (proactive suggestions and warnings while you work).

## Quick start

### 1. Clone and install

```bash
git clone https://github.com/g-dos/gedos.git
cd gedos
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env` and set at least `TELEGRAM_BOT_TOKEN` (get one from [@BotFather](https://t.me/BotFather)).

For local LLM, install [Ollama](https://ollama.com/download), then run `ollama pull llama3.3 && ollama serve`.

Alternatively, set `LLM_PROVIDER=claude` or `openai` with the corresponding API key in `.env`.

### 3. Run

```bash
python gedos.py
```

### 4. Use

| Command | Description |
|---|---|
| `/start`, `/help` | List available commands |
| `/task <description>` | Run a task (terminal, web, GUI, or LLM) |
| `/web <url>` | Open URL in headless browser |
| `/ask <question>` | Ask the LLM directly |
| `/screen` | Show current screen elements (AX Tree) |
| `/copilot on\|off` | Toggle Copilot Mode |
| `/memory` | Recent task history |
| `/status` | Current task status |
| `/stop` | Stop running task |
| `/ping` | Health check |

**Examples:**

```
/task ls -la
/task git status
/task navigate to google.com
/ask what is Python?
/copilot on
```

## Requirements

- **macOS** (Accessibility API for AX Tree + GUI control)
- **Python 3.12+**
- **Ollama** (optional, for local LLM)

## Running tests

```bash
pytest tests/ -v
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions, code style rules, semantic commit conventions, and how to submit a PR.

See [CHANGELOG.md](CHANGELOG.md) for version history.

## License

Open source. Built by [@g-dos](https://github.com/g-dos).
