# core/parsers/management_parser.py
"""
Parser de comandos de gestión desde mensajes de Telegram.

Comandos soportados:
- BE (Break Even)
- MOVER EL SL A {precio}
- CERRAR TP{n}
- CERRAR TODO
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from core.domain.enums import ManagementType


@dataclass
class ManagementAction:
    """
    Representa un comando de gestión parseado.
    
    Attributes:
        type: Tipo de comando (ManagementType enum)
        price: Precio para MOVE_SL
        tp_index: Índice de TP para CLOSE_TP_AT
    """
    type: ManagementType
    price: Optional[float] = None
    tp_index: Optional[int] = None
    
    @property
    def kind(self) -> str:
        """Backward compatibility: retorna type.value."""
        return self.type.value


class ManagementParser:
    """
    Parser de comandos de gestión de posiciones.
    
    Detecta y parsea comandos como:
    - "BE" → Break Even
    - "MOVER EL SL A 4905" → Move SL
    - "CERRAR TP1" → Close at TP1
    - "CERRAR TODO" → Close all
    """
    
    # Regex patterns
    _BE_RE = re.compile(
        r"\bBE\b|MOVER\s+EL\s+STOP\s*LOSS\s+A\s+BE|CERRAR\s+A\s+BE",
        re.IGNORECASE
    )
    _MOVE_SL_RE = re.compile(
        r"MOVER\s+EL\s+(?:SL|STOP\s*LOSS)\s+A\s*(\d+(?:\.\d+)?)",
        re.IGNORECASE
    )
    _CLOSE_TP_RE = re.compile(
        r"\bCERRAR\b.*\bTP\s*(\d+)\b",
        re.IGNORECASE
    )
    _CLOSE_ALL_RE = re.compile(
        r"\bCERRAR\b.*\bTODO\b|\bCLOSE\s+ALL\b",
        re.IGNORECASE
    )
    
    def parse(self, text: str) -> ManagementAction:
        """
        Parsea un comando de gestión.
        
        Args:
            text: Texto del mensaje
        
        Returns:
            ManagementAction con el comando parseado
        """
        t = (text or "").strip()
        if not t:
            return ManagementAction(type=ManagementType.NONE)
        
        # Prioridad: MOVE_SL > BE > CLOSE_TP > CLOSE_ALL
        
        # 1. MOVE_SL (tiene precio específico)
        m = self._MOVE_SL_RE.search(t)
        if m:
            try:
                price = float(m.group(1))
                return ManagementAction(
                    type=ManagementType.MOVE_SL,
                    price=price
                )
            except (ValueError, AttributeError):
                pass
        
        # 2. BE (break even)
        if self._BE_RE.search(t):
            return ManagementAction(type=ManagementType.BE)
        
        # 3. CLOSE_TP (cerrar en TP específico)
        m = self._CLOSE_TP_RE.search(t)
        if m:
            try:
                idx = int(m.group(1))
                return ManagementAction(
                    type=ManagementType.CLOSE_TP_AT,
                    tp_index=idx
                )
            except (ValueError, AttributeError):
                pass
        
        # 4. CLOSE_ALL (cerrar todo)
        if self._CLOSE_ALL_RE.search(t):
            return ManagementAction(type=ManagementType.CLOSE_ALL_AT)
        
        # No es comando de gestión
        return ManagementAction(type=ManagementType.NONE)
    
    def is_management_command(self, text: str) -> bool:
        """
        Verifica si el texto es un comando de gestión.
        
        Args:
            text: Texto a verificar
        
        Returns:
            True si es comando de gestión
        """
        action = self.parse(text)
        return action.type != ManagementType.NONE


# ==========================================
# Función de compatibilidad
# ==========================================

_parser = ManagementParser()


def classify_management(text: str) -> ManagementAction:
    """
    Clasifica un comando de gestión (función de compatibilidad).
    
    Args:
        text: Texto del mensaje
    
    Returns:
        ManagementAction
    """
    return _parser.parse(text)