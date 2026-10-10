"""Logging setup. Call :func:`configure_logging` once at program start."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from loguru import logger

__all__ = ["configure_logging", "logger"]

_CONSOLE_FORMAT = "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}"


def _private_opener(path: str, flags: int) -> int:
    return os.open(path, flags, 0o600)


def configure_logging(level: str = "INFO", log_file: str = "") -> None:
    # diagnose/backtrace must stay off: loguru's diagnose mode prints the values of local
    # variables in tracebacks, which would write private keys and API secrets to the logs.
    logger.remove()
    logger.add(sys.stderr, level=level, format=_CONSOLE_FORMAT, diagnose=False, backtrace=False)
    if log_file:
        Path(log_file).parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        logger.add(
            log_file,
            level="DEBUG",
            rotation="10 MB",
            retention="7 days",
            enqueue=True,
            diagnose=False,
            backtrace=False,
            opener=_private_opener,
        )
