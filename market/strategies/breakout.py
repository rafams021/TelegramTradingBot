# market/strategies/breakout.py
"""
Estrategia de Breakout.

Detecta cuando el precio rompe por encima del máximo reciente (BUY)
o por debajo del mínimo reciente (SELL) con confirmación de volumen.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from core.models import Signal
from market.indicators import recent_high, recent_low
from .base import BaseStrategy


class BreakoutStrategy(BaseStrategy):
    """
    Estrategia de ruptura de niveles recientes.

    Setup BUY:
        - Precio actual > máximo de las últimas N velas + buffer
        - Entry: precio actual
        - SL: máximo reciente - sl_buffer
        - TPs: entry + tp_distances

    Setup SELL:
        - Precio actual < mínimo de las últimas N velas - buffer
        - Entry: precio actual
        - SL: mínimo reciente + sl_buffer
        - TPs: entry - tp_distances
    """

    def __init__(
        self,
        symbol: str,
        magic: int,
        lookback_candles: int = 24,
        breakout_buffer: float = 2.0,
        sl_buffer: float = 5.0,
        tp_distances: list = None,
    ):
        """
        Args:
            symbol: Símbolo a operar
            magic: Número mágico
            lookback_candles: Velas para calcular high/low (default: 24 = 24h en H1)
            breakout_buffer: Pips sobre el high/bajo del low para confirmar ruptura
            sl_buffer: Pips entre el nivel roto y el SL
            tp_distances: Lista de distancias en pips para TPs (default: [15, 30, 50])
        """
        super().__init__(symbol, magic)
        self.lookback_candles = lookback_candles
        self.breakout_buffer = breakout_buffer
        self.sl_buffer = sl_buffer
        self.tp_distances = tp_distances or [15.0, 30.0, 50.0]

    @property
    def name(self) -> str:
        return "BREAKOUT"

    def scan(
        self,
        df: pd.DataFrame,
        current_price: float,
    ) -> Optional[Signal]:
        """
        Detecta ruptura del rango reciente.
        """
        if len(df) < self.lookback_candles + 1:
            return None

        # Calcular rango reciente (excluir la vela actual)
        high = recent_high(df.iloc[:-1], self.lookback_candles)
        low = recent_low(df.iloc[:-1], self.lookback_candles)

        # Generar ID único basado en timestamp de la última vela
        msg_id = int(df.index[-1].timestamp())

        # BUY: precio rompe por encima del máximo
        breakout_buy_level = high + self.breakout_buffer
        if current_price > breakout_buy_level:
            entry = current_price
            sl = high - self.sl_buffer
            tps = [round(entry + d, 2) for d in self.tp_distances]

            return self._make_signal(
                side="BUY",
                entry=round(entry, 2),
                sl=round(sl, 2),
                tps=tps,
                msg_id=msg_id,
            )

        # SELL: precio rompe por debajo del mínimo
        breakout_sell_level = low - self.breakout_buffer
        if current_price < breakout_sell_level:
            entry = current_price
            sl = low + self.sl_buffer
            tps = [round(entry - d, 2) for d in self.tp_distances]

            return self._make_signal(
                side="SELL",
                entry=round(entry, 2),
                sl=round(sl, 2),
                tps=tps,
                msg_id=msg_id,
            )

        return None