# Gedos

> Your Mac. Working while you're not.

Gedos is an open-source autonomous AI agent that runs on your Mac. It reads the screen (AX Tree), controls mouse and keyboard, runs terminal commands, browses the web, and talks to you on Telegram — in **Pilot Mode** (autonomous tasks) or **Copilot Mode** (proactive suggestions and warnings while you work).

## Demo

![Gedos demo — Telegram → execute → report](docs/demo.gif)

> Flow: user sends `/task ls -la` on Telegram → Gedos executes → result sent back.
> Copilot Mode detects context and sends proactive suggestions.

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

For local LLM, install Ollama — see [docs/setup-ollama.md](docs/setup-ollama.md) for a step-by-step guide.

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
/task navegar para google.com
/ask o que é Python?
/copilot on
```

See [docs/examples.md](docs/examples.md) for 5 detailed usage examples.

## Requirements

- **macOS** (Accessibility API for AX Tree + GUI control)
- **Python 3.12+**
- **Ollama** (optional, for local LLM) — [setup guide](docs/setup-ollama.md)

## Documentation

| Doc | Description |
|---|---|
| [docs/setup-ollama.md](docs/setup-ollama.md) | Ollama installation and model recommendations |
| [docs/examples.md](docs/examples.md) | 5 real usage examples with expected output |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute: setup, code style, PRs |
| [CHANGELOG.md](CHANGELOG.md) | Version history |

## Running tests

```bash
pytest tests/ -v
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions, code style rules, semantic commit conventions, and how to submit a PR.

## License

Open source. Built by [@g-dos](https://github.com/g-dos).
