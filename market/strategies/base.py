# market/strategies/base.py
"""
Clase base abstracta para todas las estrategias de trading.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import pandas as pd

from core.models import Signal


class BaseStrategy(ABC):
    """
    Contrato común para todas las estrategias autónomas.

    Cada estrategia recibe datos de mercado y devuelve una Signal
    si detecta una oportunidad, o None si no hay setup válido.

    El objeto Signal devuelto usa el mismo formato que el parser
    de Telegram, por lo que el executor no necesita cambios.
    """

    def __init__(self, symbol: str, magic: int):
        """
        Args:
            symbol: Símbolo a operar (ej: "XAUUSD-ECN")
            magic: Número mágico para identificar órdenes del bot
        """
        self.symbol = symbol
        self.magic = magic

    @abstractmethod
    def scan(
        self,
        df: pd.DataFrame,
        current_price: float,
    ) -> Optional[Signal]:
        """
        Analiza el mercado y devuelve una señal si hay oportunidad.

        Args:
            df: DataFrame con velas históricas (OHLCV)
            current_price: Precio actual del mercado (mid price)

        Returns:
            Signal si hay oportunidad, None si no hay setup válido
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre identificador de la estrategia."""
        pass

    def _make_signal(
        self,
        side: str,
        entry: float,
        sl: float,
        tps: list,
        msg_id: int,
    ) -> Optional[Signal]:
        """
        Crea un objeto Signal validado.

        Valida que SL y TPs estén del lado correcto antes de crear
        la señal. Si la validación falla, retorna None silenciosamente.

        Args:
            side: "BUY" o "SELL"
            entry: Precio de entrada
            sl: Stop Loss
            tps: Lista de Take Profits
            msg_id: ID único para esta señal (timestamp-based)

        Returns:
            Signal válida o None si no pasa validación
        """
        try:
            side_u = side.upper()

            # Validar que TPs y SL están del lado correcto
            if side_u == "BUY":
                if sl >= entry:
                    return None
                if not all(tp > entry for tp in tps):
                    return None
            else:  # SELL
                if sl <= entry:
                    return None
                if not all(tp < entry for tp in tps):
                    return None

            return Signal(
                message_id=msg_id,
                symbol=self.symbol,
                side=side_u,
                entry=entry,
                tps=tps,
                sl=sl,
            )

        except Exception:
            return None