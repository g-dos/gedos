"""
GEDOS configuration — loads config.yaml and .env, exposes settings.
All configuration flows through this module; no hardcoded values.
"""

from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
import os


def _project_root() -> Path:
    """Resolve project root (directory containing config.yaml)."""
    return Path(__file__).resolve().parent.parent


def load_config() -> dict[str, Any]:
    """
    Load merged configuration from config.yaml and .env.
    Environment variables override YAML for secrets and overrides.
    """
    root = _project_root()
    env_path = root / ".env"
    load_dotenv(env_path)

    yaml_path = root / "config.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"Missing config: {yaml_path}")

    with open(yaml_path, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    # Override from environment
    if token := os.getenv("TELEGRAM_BOT_TOKEN"):
        config.setdefault("telegram", {})["bot_token"] = token

    llm = config.setdefault("llm", {})
    if v := os.getenv("LLM_PROVIDER"):
        llm["provider"] = v
    for key in ("OLLAMA_MODEL", "OLLAMA_BASE_URL"):
        if value := os.getenv(key):
            llm[key.lower()] = value

    return config


def get_telegram_token() -> str:
    """Return Telegram bot token; raises if missing."""
    config = load_config()
    token = (config.get("telegram") or {}).get("bot_token") or os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN is required. Set it in .env or config.yaml."
        )
    return token


def get_llm_config() -> dict[str, Any]:
    """Return LLM configuration (provider, model, base_url)."""
    config = load_config()
    llm = config.get("llm") or {}
    return {
        "provider": llm.get("provider", "ollama"),
        "model": llm.get("model", "llama3.3"),
        "base_url": llm.get("base_url") or llm.get("ollama_base_url", "http://localhost:11434"),
    }


def pilot_enabled() -> bool:
    """Whether Pilot Mode is enabled."""
    config = load_config()
    return (config.get("modes") or {}).get("pilot", True)


def log_level() -> str:
    """Logging level (e.g. INFO, DEBUG)."""
    config = load_config()
    return (config.get("logging") or {}).get("level", "INFO")
