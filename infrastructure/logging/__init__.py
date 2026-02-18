# infrastructure/logging/__init__.py
from .logger import (
    BotLogger,
    get_logger,
    set_logger,
    event,
    info,
    warning,
    error,
    debug,
)

__all__ = [
    "BotLogger",
    "get_logger",
    "set_logger",
    "event",
    "info",
    "warning",
    "error",
    "debug",
]