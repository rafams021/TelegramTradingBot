# adapters/__init__.py
"""
Módulo adapters - Interfaces con servicios externos.

Contiene:
    - mt5: Cliente de MetaTrader 5 (refactorizado en Fase 3)
    - telegram: Cliente de Telegram (nuevo en Fase 3B)
    - mt5_client: API legacy (backward compatibility)
"""

# Backward compatibility: importar desde el wrapper de compatibilidad
try:
    from . import mt5_client_compat as mt5_client
except ImportError:
    # Fallback al archivo original si el wrapper no existe
    try:
        from . import mt5_client
    except ImportError:
        pass

# Nuevos clients refactorizados
try:
    from .mt5 import MT5Client
except ImportError:
    MT5Client = None

try:
    from .telegram import TelegramBotClient
except ImportError:
    TelegramBotClient = None

__all__ = [
    "mt5_client",  # API legacy
    "MT5Client",   # Nuevo client OOP
    "TelegramBotClient",  # Nuevo client Telegram
]