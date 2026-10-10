"""Logging setup. Call :func:`configure_logging` once at program start."""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

__all__ = ["configure_logging", "logger"]

_CONSOLE_FORMAT = "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}"


def configure_logging(level: str = "INFO", log_file: str = "") -> None:
    logger.remove()
    logger.add(sys.stderr, level=level, format=_CONSOLE_FORMAT)
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        logger.add(log_file, level="DEBUG", rotation="10 MB", retention="7 days", enqueue=True)
