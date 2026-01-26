# adapters/mt5/__init__.py
"""
Cliente MetaTrader 5 refactorizado.

Exports:
    - MT5Client: Cliente principal
    - Tick, SymbolInfo, MT5Error: Tipos
"""

from .client import MT5Client
from .types import Tick, SymbolInfo, MT5Error

__all__ = [
    "MT5Client",
    "Tick",
    "SymbolInfo",
    "MT5Error",
]