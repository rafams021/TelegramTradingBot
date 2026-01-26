# core/__init__.py
"""
Módulo core del TelegramTradingBot.

Este archivo mantiene backward compatibility para imports antiguos
mientras gradualmente migramos a la nueva estructura.
"""

# =========================
# Backward compatibility para logger
# =========================
# Los archivos antiguos hacen: from core import logger
# Redirigimos al nuevo location en infrastructure/logging

try:
    # Intentar importar desde el nuevo location
    from infrastructure import logging as logger
except ImportError:
    # Fallback al viejo location si existe
    try:
        from . import logger
    except ImportError:
        # Último fallback: crear un logger básico
        import sys
        print("WARNING: Could not import logger, using fallback", file=sys.stderr)
        
        class _FallbackLogger:
            @staticmethod
            def log_event(event):
                print(f"[EVENT] {event}")
            
            @staticmethod
            def iso_now():
                from datetime import datetime, timezone
                return datetime.now(timezone.utc).isoformat()
        
        logger = _FallbackLogger()


# =========================
# Exports para backward compatibility
# =========================
__all__ = [
    "logger",
]