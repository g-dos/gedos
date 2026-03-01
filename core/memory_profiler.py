"""
GEDOS Memory Profiler — detect memory leaks in long-running sessions.
"""

import gc
import logging
import sys
from typing import Optional

logger = logging.getLogger(__name__)


def get_memory_usage_mb() -> float:
    """Return current process memory usage in MB."""
    try:
        import psutil
        import os
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024 * 1024)
    except ImportError:
        logger.warning("psutil not available, memory profiling disabled")
        return 0.0


def get_object_counts() -> dict[str, int]:
    """Return count of objects by type for leak detection."""
    gc.collect()
    type_counts: dict[str, int] = {}
    for obj in gc.get_objects():
        t = type(obj).__name__
        type_counts[t] = type_counts.get(t, 0) + 1
    return type_counts


def log_memory_stats(label: str = "memory_check") -> None:
    """Log current memory usage and top object counts."""
    mem_mb = get_memory_usage_mb()
    if mem_mb > 0:
        logger.info("%s: %.2f MB RSS", label, mem_mb)
    counts = get_object_counts()
    top = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:10]
    logger.debug("%s top objects: %s", label, ", ".join(f"{t}={n}" for t, n in top))


def check_memory_leak(
    baseline_mb: float,
    threshold_mb: float = 50.0,
    label: str = "leak_check",
) -> Optional[str]:
    """
    Check if memory usage has grown beyond threshold since baseline.
    Returns warning message if leak detected, None otherwise.
    """
    current_mb = get_memory_usage_mb()
    if current_mb == 0.0:
        return None
    delta_mb = current_mb - baseline_mb
    if delta_mb > threshold_mb:
        msg = f"{label}: memory grew {delta_mb:.2f} MB (from {baseline_mb:.2f} to {current_mb:.2f})"
        logger.warning(msg)
        return msg
    logger.debug("%s: memory delta %.2f MB", label, delta_mb)
    return None
