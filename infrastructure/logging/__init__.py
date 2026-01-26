# infrastructure/logging/__init__.py
"""
Módulo de logging del TelegramTradingBot.

Exports:
    - BotLogger class
    - get_logger(), set_logger()
    - Convenience functions: event(), info(), warning(), error(), debug()
    - Backward compatibility: log_event(), iso_now(), Logger class
"""

from .logger import (
    BotLogger,
    get_logger,
    set_logger,
    event,
    info,
    warning,
    error,
    debug,
    log_event,
    iso_now,
    Logger,
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
    "log_event",
    "iso_now",
    "Logger",
]