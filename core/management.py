# core/management.py
"""
REFACTORIZADO EN FASE 4:
- Parser movido a core/parsers/management_parser.py
- Lógica movida a core/services/management_service.py
- Este archivo mantiene backward compatibility
"""
from __future__ import annotations

from typing import Optional

from core.parsers.management_parser import ManagementParser, ManagementAction
from core.services.management_service import ManagementService
from core.state import BotState

# Parser y service globales (lazy init)
_parser = ManagementParser()
_service: Optional[ManagementService] = None


def _get_service(state: BotState) -> ManagementService:
    """Obtiene o crea la instancia del servicio."""
    global _service
    if _service is None:
        _service = ManagementService(state)
    return _service


# ==========================================
# API Pública (backward compatible)
# ==========================================

def classify_management(text: str) -> ManagementAction:
    """
    Clasifica un comando de gestión (función de compatibilidad).
    
    Args:
        text: Texto del mensaje
    
    Returns:
        ManagementAction
    """
    return _parser.parse(text)


def apply_management(
    state: BotState,
    msg_id: int,
    reply_to: Optional[int],
    mg: ManagementAction
) -> None:
    """
    Aplica un comando de gestión (función de compatibilidad).
    
    Args:
        state: Estado del bot
        msg_id: ID del mensaje de comando
        reply_to: ID del mensaje de señal original
        mg: Acción de gestión parseada
    """
    service = _get_service(state)
    service.apply(mg, msg_id, reply_to)


__all__ = [
    "ManagementAction",
    "classify_management",
    "apply_management",
]