# core/services/__init__.py
"""
Módulo de servicios - Lógica de negocio del bot.

Services:
    - SignalService: Procesamiento y validación de señales
    - ManagementService: Gestión de posiciones (BE, MOVE_SL, CLOSE)
"""

from .signal_service import SignalService
from .management_service import ManagementService

__all__ = [
    "SignalService",
    "ManagementService",
]