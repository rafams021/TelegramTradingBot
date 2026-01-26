# core/parsers/signal_parser.py
"""
Parser de señales de trading desde mensajes de Telegram.

Soporta formatos variados y es tolerante a errores de formato.
"""
from __future__ import annotations

import re
from typing import List, Optional

from core.domain.models import Signal
from core.domain.enums import OrderSide


class SignalParser:
    """
    Parser de señales de trading.
    
    Soporta formatos como:
    - "XAUUSD | BUY\nBUY @ 4910\nTP1: 4912 ...\nSL: 4900"
    - "XAUUSD SELL 4880\nTP 4875 ...\nSTOP LOSS: 4887"
    - "XAUUSD BUY\nBUY @ (4982.5-4981.5)\nTP1: ...\nSL: ..."
    """
    
    # Regex patterns
    _SYMBOL_RE = re.compile(r"\bXAUUSD\b", re.IGNORECASE)
    _BUY_RE = re.compile(r"\bBUY\b", re.IGNORECASE)
    _SELL_RE = re.compile(r"\bSELL\b", re.IGNORECASE)
    _ENTRY_AFTER_SIDE_RE = re.compile(
        r"\b(?:BUY|SELL)\b\s*@?\s*(\d+(?:\.\d+)?)",
        re.IGNORECASE,
    )
    _ENTRY_RANGE_RE = re.compile(
        r"\(\s*(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*\)",
        re.IGNORECASE,
    )
    _TP_RE = re.compile(r"\bTP\s*\d*\s*[:\s]+(\d+(?:\.\d+)?)", re.IGNORECASE)
    _SL_RE = re.compile(
        r"\b(?:SL|S/L|STOP\s*LOSS|STOPLOSS)\b\s*[:\s]+(\d+(?:\.\d+)?)",
        re.IGNORECASE,
    )
    
    def parse(self, text: str, msg_id: int = 0) -> Optional[Signal]:
        """
        Parsea un mensaje de Telegram en una señal.
        
        Args:
            text: Texto del mensaje
            msg_id: ID del mensaje (opcional)
        
        Returns:
            Signal si se puede parsear, None si no
        """
        if not text:
            return None
        
        if not self._SYMBOL_RE.search(text):
            return None
        
        side = self._extract_side(text)
        if side is None:
            return None
        
        tps = self._extract_tps(text)
        sl = self._extract_sl(text)
        entry = self._extract_entry(text, side=side)
        
        # Requerir mínimo: entry, SL y al menos un TP
        if entry is None or sl is None or not tps:
            return None
        
        try:
            return Signal(
                message_id=msg_id,
                symbol="XAUUSD",
                side=side,
                entry=entry,
                tps=tps,
                sl=sl,
            )
        except ValueError:
            # Signal.__post_init__ valida y puede lanzar ValueError
            return None
    
    def _extract_side(self, text: str) -> Optional[OrderSide]:
        """Extrae el lado (BUY/SELL) del texto."""
        if self._BUY_RE.search(text):
            return OrderSide.BUY
        if self._SELL_RE.search(text):
            return OrderSide.SELL
        return None
    
    def _extract_entry(self, text: str, side: OrderSide) -> Optional[float]:
        """
        Extrae el precio de entrada.
        
        Soporta:
        - Precio simple: "BUY @ 4910"
        - Rango: "BUY @ (4982.5-4981.5)"
        """
        # Primero buscar rangos como (a-b)
        rng = self._ENTRY_RANGE_RE.search(text)
        if rng:
            a = float(rng.group(1))
            b = float(rng.group(2))
            lo, hi = (a, b) if a <= b else (b, a)
            # Para BUY preferimos el precio más bajo; para SELL el más alto
            return lo if side == OrderSide.BUY else hi
        
        # Buscar precio después de BUY/SELL
        m = self._ENTRY_AFTER_SIDE_RE.search(text)
        if not m:
            return None
        return float(m.group(1))
    
    def _extract_tps(self, text: str) -> List[float]:
        """Extrae todos los TPs del texto."""
        return [float(x) for x in self._TP_RE.findall(text)]
    
    def _extract_sl(self, text: str) -> Optional[float]:
        """Extrae el Stop Loss del texto."""
        m = self._SL_RE.search(text)
        return float(m.group(1)) if m else None


# ==========================================
# Función de compatibilidad
# ==========================================

_parser = SignalParser()


def parse_signal(text: str, msg_id: int = 0) -> Optional[Signal]:
    """
    Parsea una señal (función de compatibilidad).
    
    Args:
        text: Texto del mensaje
        msg_id: ID del mensaje (opcional)
    
    Returns:
        Signal o None
    """
    return _parser.parse(text, msg_id)