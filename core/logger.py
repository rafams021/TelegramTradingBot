# core/logger.py
"""
DEPRECADO: Este archivo redirige al nuevo logger en infrastructure/logging.

Los archivos antiguos que usan:
    from core.logger import Logger, log_event, iso_now

Siguen funcionando gracias a esta redirección.

NUEVO CÓDIGO DEBERÍA USAR:
    from infrastructure.logging import event, info, warning, error
"""

# Importar todo desde el nuevo location
from infrastructure.logging import (
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