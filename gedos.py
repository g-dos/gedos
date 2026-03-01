#!/usr/bin/env python3
"""
GEDOS — entrypoint.
Starts the Telegram bot and runs until interrupted.
"""

__version__ = "0.1.0"

import logging
import sys

from core.config import load_config, log_level
from interfaces.telegram_bot import run_polling


def main() -> int:
    """Initialize logging and run the Telegram bot."""
    try:
        config = load_config()
    except FileNotFoundError as e:
        logging.basicConfig(level=logging.INFO)
        logging.error("%s", e)
        return 1

    level = getattr(logging, (config.get("logging") or {}).get("level", "INFO").upper(), logging.INFO)
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=level,
    )
    logger = logging.getLogger(__name__)
    logger.info("Gedos starting (Pilot Mode)")

    run_polling()
    return 0


if __name__ == "__main__":
    sys.exit(main())
