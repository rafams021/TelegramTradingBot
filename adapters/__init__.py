# adapters/__init__.py
"""
Módulo adapters - Interfaces con servicios externos.

Contiene:
    - mt5_client: Cliente de MetaTrader 5
"""

# Backward compatibility: permitir import de mt5_client
try:
    from . import mt5_client
except ImportError:
    pass

__all__ = [
    "mt5_client",
]