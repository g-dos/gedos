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


def _env_path() -> Path:
    """Return the local .env file path."""
    return _project_root() / ".env"


def get_gedos_md_path() -> Path:
    """Return the per-user Gedos profile path."""
    return Path.home() / ".gedos" / "GEDOS.md"


def has_telegram_token() -> bool:
    """Return whether a Telegram bot token is configured in .env or env vars."""
    env_vars = read_env_file()
    token = os.getenv("TELEGRAM_BOT_TOKEN") or env_vars.get("TELEGRAM_BOT_TOKEN")
    return bool(token and token.strip())


def read_env_file() -> dict[str, str]:
    """Parse the local .env file into a flat key/value mapping."""
    env_path = _env_path()
    values: dict[str, str] = {}
    if not env_path.exists():
        return values
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def write_env_value(key: str, value: str) -> None:
    """Upsert a variable in the local .env file."""
    key = str(key).strip().replace("\n", "").replace("\r", "")
    value = str(value).replace("\n", "").replace("\r", "").strip()
    env_path = _env_path()
    env_path.parent.mkdir(parents=True, exist_ok=True)
    existing_lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    updated: list[str] = []
    replaced = False
    for line in existing_lines:
        if line.strip().startswith(f"{key}="):
            updated.append(f"{key}={value}")
            replaced = True
        else:
            updated.append(line)
    if not replaced:
        updated.append(f"{key}={value}")
    env_path.write_text("\n".join(updated).rstrip() + "\n", encoding="utf-8")
    os.environ[key] = value


def update_config(values: dict[str, Any]) -> None:
    """Persist top-level config updates back to config.yaml."""
    yaml_path = _project_root() / "config.yaml"
    with open(yaml_path, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    for key, value in values.items():
        if isinstance(value, dict) and isinstance(config.get(key), dict):
            merged = dict(config.get(key) or {})
            merged.update(value)
            config[key] = merged
        else:
            config[key] = value
    yaml_path.write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=False), encoding="utf-8")


def load_gedos_profile() -> dict[str, Any]:
    """Parse ~/.gedos/GEDOS.md as a lightweight YAML-like profile."""
    path = get_gedos_md_path()
    if not path.exists():
        return {}

    profile: dict[str, Any] = {}
    context_lines: list[str] = []
    blocked_commands: list[str] = []
    active_section: str | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("## "):
            heading = stripped[3:].strip().lower()
            if heading == "context":
                active_section = "context"
            elif heading == "blocked commands":
                active_section = "blocked_commands"
            else:
                active_section = None
            continue
        if stripped.startswith("#"):
            continue
        if active_section == "context":
            context_lines.append(stripped)
            continue
        if active_section == "blocked_commands":
            blocked_commands.append(stripped.lstrip("- ").strip())
            continue
        if ":" in stripped:
            key, value = stripped.split(":", 1)
            profile[key.strip()] = value.strip()

    if context_lines:
        profile["context"] = "\n".join(context_lines)
    if blocked_commands:
        profile["blocked_commands"] = blocked_commands
    return profile


def load_config() -> dict[str, Any]:
    """
    Load merged configuration from config.yaml and .env.
    Environment variables override YAML for secrets and overrides.
    """
    root = _project_root()
    env_path = _env_path()
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

    profile = load_gedos_profile()
    if profile:
        config["profile"] = profile
        if profile.get("language") and profile.get("language") != "auto":
            config.setdefault("preferences", {})["language"] = profile["language"]
        if profile.get("response_style"):
            config.setdefault("preferences", {})["response_style"] = profile["response_style"]
        permission_level = (profile.get("level") or "").strip().lower()
        if permission_level == "full_access":
            config.setdefault("security", {})["strict_shell"] = False
        elif permission_level == "default":
            config.setdefault("security", {})["strict_shell"] = True

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
        "model": llm.get("model", "llama3.2"),
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


def get_agent_config(agent_name: str) -> dict:
    """Return agent-specific config (timeout, max_retries) with defaults."""
    config = load_config()
    agents = config.get("agents") or {}
    defaults = {"max_retries": agents.get("max_retries", 3)}
    specific = agents.get(agent_name) or {}
    return {**defaults, **specific}
