# Gedos

> Your Mac. Working while you're not.

Gedos is an open-source autonomous AI agent that runs on your Mac. It sees (AX Tree), clicks, runs commands, browses the web, and talks to you on Telegram — in **Pilot Mode** (autonomous tasks) or **Copilot Mode** (proactive suggestions and warnings while you work).

## Demo

*Record a short screen capture showing: `/task ls`, `/copilot on`, and a Copilot suggestion — then add the GIF here or under `docs/demo.gif`.*

## Quick start (v0.3)

1. **Clone and install**
   ```bash
   cd Gedos
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   playwright install chromium   # for Web Agent
   ```

2. **Configure**
   - Copy `.env.example` to `.env`
   - Set `TELEGRAM_BOT_TOKEN` (from [@BotFather](https://t.me/BotFather))
   - Optional: `LLM_PROVIDER=claude` or `openai` and API keys for cloud LLM (default: Ollama local)

3. **Run**
   ```bash
   python gedos.py
   ```

4. **Use**
   - `/start`, `/help` — commands
   - `/task <descrição>` — run task (terminal, web, GUI, or LLM via Orchestrator)
   - `/task ls`, `/task navegar para google.com`, `/task perguntar o que é Python`
   - `/web <url>` — open URL in headless browser
   - `/ask <pergunta>` — ask the LLM
   - `/copilot on` | `/copilot off` — Copilot Mode (suggestions + warnings)
   - `/memory` — recent tasks history
   - `/ping` — health check

**Requirements:** macOS (AX Tree + GUI), Python 3.12+. Ollama optional for local LLM.

See [CHANGELOG.md](CHANGELOG.md) for version history.

---

*Built by [@g-dos](https://github.com/g-dos)*
