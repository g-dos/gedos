"""
GEDOS Telegram interface — Pilot and Copilot mode.
Handles /task, /status, /stop, /report; receives and responds to messages.
"""

import logging
from typing import Optional

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from core.config import get_telegram_token, pilot_enabled
from agents.terminal_agent import run_shell, TerminalResult
from agents.gui_agent import click_button
from tools.ax_tree import get_ax_tree

logger = logging.getLogger(__name__)

# In-memory task state for v0.1 (no orchestrator yet)
_current_task: Optional[str] = None
_task_status: str = "idle"  # idle | running | stopped

# Commands we allow to run directly from /task in v0.1
_SHELL_SAFE_PREFIXES = (
    "ls", "pwd", "whoami", "date", "git ", "cat ", "echo ", "which ",
    "node ", "npm ", "python", "python3", "cd ", "head ", "tail ", "wc ",
)


def _looks_like_shell_command(payload: str) -> bool:
    """Heuristic: single line, no leading/trailing quotes only, safe-looking."""
    line = payload.strip()
    if "\n" in line or len(line) > 500:
        return False
    low = line.lower()
    return any(low.startswith(p) for p in _SHELL_SAFE_PREFIXES) or low in ("ls", "pwd", "whoami", "date")


def _format_ax_tree(tree: dict) -> str:
    """Format AX tree for Telegram (readable summary)."""
    err = tree.get("error")
    if err:
        return f"Erro: {err}"
    app = tree.get("app") or "?"
    lines = [f"App: {app}"]
    for w in (tree.get("windows") or [])[:5]:
        title = (w.get("title") or "").strip() or "(sem título)"
        lines.append(f"  Janela: {title}")
    btns = tree.get("buttons") or []
    if btns:
        lines.append("Botões: " + ", ".join((b.get("title") or b.get("role") or "?") for b in btns[:15]))
    return "\n".join(lines)


def _format_terminal_result(r: TerminalResult) -> str:
    """Format TerminalResult for Telegram (short, readable)."""
    out = (r.stdout or "").strip() or "(no output)"
    err = (r.stderr or "").strip()
    if len(out) > 3500:
        out = out[:3500] + "\n… (truncado)"
    status = "✅" if r.success else "❌"
    msg = f"{status} {r.command[:80]}\n\n{out}"
    if err:
        msg += f"\n\nstderr:\n{err[:500]}"
    return msg


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — welcome and instructions."""
    if not update.message or not update.message.text:
        return
    welcome = (
        "Olá, sou o Gedos. Seu agente autônomo no Mac.\n\n"
        "**Pilot Mode** — Envie uma tarefa e eu executo.\n\n"
        "Comandos:\n"
        "• /task <descrição> — Enviar tarefa para execução\n"
        "• /status — Status da tarefa atual\n"
        "• /stop — Parar execução\n"
        "• /help — Lista de comandos\n\n"
        "Exemplo: /task listar arquivos do diretório atual"
    )
    await update.message.reply_text(welcome)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help — list commands."""
    if not update.message:
        return
    help_text = (
        "Comandos disponíveis:\n"
        "/start — Boas-vindas e instruções\n"
        "/task <descrição> — Enviar tarefa para execução\n"
        "/status — Status da tarefa atual\n"
        "/stop — Parar execução atual\n"
        "/help — Esta mensagem"
    )
    await update.message.reply_text(help_text)


async def cmd_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /task — receive task description and acknowledge."""
    global _current_task, _task_status
    if not update.message or not update.message.text:
        return

    # Payload: everything after "/task "
    text = update.message.text.strip()
    payload = text[5:].strip() if text.lower().startswith("/task") else text
    if not payload:
        await update.message.reply_text("Use: /task <descrição da tarefa>")
        return

    _current_task = payload
    _task_status = "running"
    logger.info("Task received: %s", payload[:100])

    # AX Tree / list elements (e.g. "listar elementos da tela", "elementos da janela")
    low = payload.lower()
    if any(kw in low for kw in ("listar elementos", "elementos da tela", "elementos da janela", "ax tree", "o que você vê")):
        _task_status = "idle"
        tree = get_ax_tree(max_buttons=25, max_text_fields=10)
        reply = _format_ax_tree(tree)
        await update.message.reply_text(reply)
        return

    # Click button (e.g. "clicar no botão OK", "click no botão Cancel")
    if "clicar" in low or "click" in low:
        btn_name = None
        for prefix in ("clicar no botão ", "clicar no botao ", "click no botão ", "click no botao ", "clicar no ", "click no "):
            if prefix in low:
                rest = low.split(prefix, 1)[-1].strip()
                btn_name = rest.split()[0] if rest else None
                break
        if not btn_name and len(payload.split()) >= 2:
            btn_name = payload.split()[-1].strip(".,")
        if btn_name:
            ok = click_button(btn_name)
            _task_status = "idle"
            await update.message.reply_text("Cliquei no botão." if ok else f"Não encontrei botão '{btn_name}'.")
            return

    # Shell command
    if _looks_like_shell_command(payload):
        result = run_shell(payload)
        _task_status = "idle"
        reply = _format_terminal_result(result)
        await update.message.reply_text(reply)
        return

    await update.message.reply_text(
        f"Tarefa recebida: _{payload[:200]}_\n\nEm execução…", parse_mode="Markdown"
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status — report current task status."""
    if not update.message:
        return
    global _current_task, _task_status
    if _task_status == "idle" or not _current_task:
        await update.message.reply_text("Nenhuma tarefa em execução.")
        return
    status_msg = f"Status: {_task_status}\nTarefa: {_current_task[:150]}"
    if _current_task and len(_current_task) > 150:
        status_msg += "..."
    await update.message.reply_text(status_msg)


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /stop — stop current execution."""
    global _task_status
    if not update.message:
        return
    _task_status = "stopped"
    logger.info("Stop requested")
    await update.message.reply_text("Parada solicitada. A execução será interrompida.")


def build_application() -> Application:
    """Build and return the Telegram Application with all handlers."""
    token = get_telegram_token()
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("task", cmd_task))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("stop", cmd_stop))

    return app


def run_polling() -> None:
    """Run the bot with polling (blocking)."""
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    if not pilot_enabled():
        logger.warning("Pilot mode is disabled in config.")
    app = build_application()
    logger.info("Gedos Telegram bot starting (polling)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
