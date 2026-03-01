# Gedos

> Your Mac. Working while you're not.

Gedos is an open-source autonomous AI agent that lives on your Mac.
It sees, clicks, codes, commits, and reports back to you on Telegram.

> 🚧 Under active development. Star to follow progress.

## v0.1 — Quick start

1. **Clone and install**
   ```bash
   cd Gedos
   python3 -m venv .venv && source .venv/bin/activate  # or: .venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```

2. **Configure**
   - Copy `.env.example` to `.env`
   - Get a bot token from [@BotFather](https://t.me/BotFather) and set `TELEGRAM_BOT_TOKEN` in `.env`

3. **Run**
   ```bash
   python gedos.py
   ```

4. **Use**
   - Open Telegram and message your bot
   - `/start` — welcome and commands
   - `/task ls` — run a shell command
   - `/task listar elementos da tela` — list UI elements (macOS Accessibility)
   - `/task clicar no botão OK` — click a button by name

**Requirements:** macOS (for AX Tree and GUI control), Python 3.12+.

---

*Built by [@g-dos](https://github.com/g-dos)*
