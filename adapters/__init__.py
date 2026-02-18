# adapters/__init__.py
"""
Modulo adapters - Interfaces con servicios externos.
"""
from .mt5 import MT5Client

__all__ = ["MT5Client"]