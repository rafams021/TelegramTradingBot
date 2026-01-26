# core/services/__init__.py
"""
Módulo de servicios - Lógica de negocio del bot.

Services:
    - SignalService: Procesamiento y validación de señales
"""

from .signal_service import SignalService

__all__ = [
    "SignalService",
]