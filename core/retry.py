"""
GEDOS retry utility — exponential backoff for transient failures.
"""

import logging
import time
from typing import TypeVar, Callable, Optional

logger = logging.getLogger(__name__)

T = TypeVar("T")


def retry_with_backoff(
    fn: Callable[..., T],
    *args,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    exceptions: tuple = (Exception,),
    label: Optional[str] = None,
    **kwargs,
) -> T:
    """
    Call fn with retry and exponential backoff.
    Raises the last exception if all attempts fail.
    """
    tag = label or getattr(fn, "__name__", "operation")
    last_exc: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn(*args, **kwargs)
        except exceptions as e:
            last_exc = e
            if attempt == max_attempts:
                logger.error("%s failed after %d attempts: %s", tag, max_attempts, e)
                raise
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning("%s attempt %d/%d failed (%s), retrying in %.1fs", tag, attempt, max_attempts, e, delay)
            time.sleep(delay)
    raise last_exc  # unreachable but satisfies type checker
