# Gedos

> Your Mac. Working while you're not.

Gedos is an open-source autonomous AI agent that lives on your Mac.
It sees, clicks, codes, commits, and reports back to you on Telegram.

> 🚧 Under active development. Star to follow progress.

## Quick start (v0.2)

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
   - `/copilot on` | `/copilot off` — toggle Copilot Mode (proactive suggestions)
   - `/memory` — recent tasks history

**Requirements:** macOS (AX Tree + GUI), Python 3.12+. Ollama optional for local LLM.

---

*Built by [@g-dos](https://github.com/g-dos)*
