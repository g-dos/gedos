"""Smoke tests for core.config."""

import os
from core.config import load_config, get_llm_config, pilot_enabled, log_level


def test_load_config_returns_dict():
    config = load_config()
    assert isinstance(config, dict)
    assert "telegram" in config
    assert "llm" in config


def test_llm_config_defaults():
    llm = get_llm_config()
    assert llm["provider"] in ("ollama", "claude", "openai")
    assert isinstance(llm["model"], str)
    assert llm["base_url"].startswith("http")


def test_pilot_enabled_returns_bool():
    assert isinstance(pilot_enabled(), bool)


def test_log_level_returns_string():
    level = log_level()
    assert level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


def test_env_override(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    config = load_config()
    assert config["llm"]["provider"] == "openai"
