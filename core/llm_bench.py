"""
GEDOS LLM Benchmark — measure response times for Ollama, Claude, OpenAI.
"""

import logging
import time
from typing import Optional

from core.llm import complete

logger = logging.getLogger(__name__)


def benchmark_llm(prompt: str = "What is Python?", max_tokens: int = 100) -> dict[str, float]:
    """
    Benchmark current LLM provider response time.
    Returns dict with timing metrics in seconds.
    """
    start = time.time()
    try:
        result = complete(prompt, max_tokens=max_tokens)
        elapsed = time.time() - start
        success = len(result) > 0
        logger.info("LLM benchmark: %.2fs, %d chars, success=%s", elapsed, len(result), success)
        return {
            "elapsed_s": elapsed,
            "chars": len(result),
            "success": success,
            "prompt_tokens": len(prompt.split()),
            "response_tokens_est": len(result.split()),
        }
    except Exception as e:
        elapsed = time.time() - start
        logger.error("LLM benchmark failed after %.2fs: %s", elapsed, e)
        return {
            "elapsed_s": elapsed,
            "chars": 0,
            "success": False,
            "error": str(e),
        }


def compare_llm_providers(
    ollama_model: Optional[str] = None,
    claude_key: Optional[str] = None,
    openai_key: Optional[str] = None,
    prompt: str = "Explain recursion in one sentence.",
) -> dict[str, dict]:
    """
    Compare response times across multiple LLM providers.
    Returns dict keyed by provider name with benchmark results.
    Only tests providers with valid config/keys.
    """
    from core.config import load_config
    import os

    results = {}
    config = load_config()
    original_provider = config.get("llm", {}).get("provider", "ollama")

    # Benchmark Ollama
    if ollama_model or original_provider == "ollama":
        logger.info("Benchmarking Ollama...")
        os.environ["LLM_PROVIDER"] = "ollama"
        if ollama_model:
            os.environ["OLLAMA_MODEL"] = ollama_model
        results["ollama"] = benchmark_llm(prompt)
        time.sleep(0.5)

    # Benchmark Claude
    if claude_key or os.getenv("ANTHROPIC_API_KEY"):
        logger.info("Benchmarking Claude...")
        os.environ["LLM_PROVIDER"] = "claude"
        if claude_key:
            os.environ["ANTHROPIC_API_KEY"] = claude_key
        results["claude"] = benchmark_llm(prompt)
        time.sleep(0.5)

    # Benchmark OpenAI
    if openai_key or os.getenv("OPENAI_API_KEY"):
        logger.info("Benchmarking OpenAI...")
        os.environ["LLM_PROVIDER"] = "openai"
        if openai_key:
            os.environ["OPENAI_API_KEY"] = openai_key
        results["openai"] = benchmark_llm(prompt)

    # Restore original provider
    os.environ["LLM_PROVIDER"] = original_provider

    logger.info("LLM comparison complete: %d providers tested", len(results))
    return results
