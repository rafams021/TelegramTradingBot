# market/strategies/trend.py
"""
Estrategia de Trend Following con pullbacks a SMA.

Detecta cuando el precio hace un pullback a la SMA20
en dirección de la tendencia definida por SMA20 vs SMA50.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from core.models import Signal
from market.indicators import sma
from .base import BaseStrategy


class TrendStrategy(BaseStrategy):
    """
    Estrategia de seguimiento de tendencia con pullbacks.

    Setup BUY (uptrend + pullback a SMA20):
        - SMA20 > SMA50 (tendencia alcista confirmada)
        - Precio actual cerca de SMA20 (dentro de proximity_pips)
        - Precio viene desde arriba (pullback, no ruptura)
        - Entry: SMA20 + entry_buffer
        - SL: SMA20 - sl_buffer
        - TPs: entry + tp_distances

    Setup SELL (downtrend + pullback a SMA20):
        - SMA20 < SMA50 (tendencia bajista confirmada)
        - Precio actual cerca de SMA20 (dentro de proximity_pips)
        - Precio viene desde abajo (pullback, no ruptura)
        - Entry: SMA20 - entry_buffer
        - SL: SMA20 + sl_buffer
        - TPs: entry - tp_distances
    """

    def __init__(
        self,
        symbol: str,
        magic: int,
        fast_period: int = 20,
        slow_period: int = 50,
        proximity_pips: float = 2.0,
        entry_buffer: float = 1.0,
        sl_buffer: float = 15.0,
        tp_distances: list = None,
    ):
        """
        Args:
            symbol: Símbolo a operar
            magic: Número mágico
            fast_period: Período SMA rápida (default: 20)
            slow_period: Período SMA lenta (default: 50)
            proximity_pips: Distancia máxima a SMA20 para considerar pullback
            entry_buffer: Buffer sobre/bajo SMA20 para entry
            sl_buffer: Buffer bajo/sobre SMA20 para SL
            tp_distances: Distancias en pips para TPs (default: [25, 50])
        """
        super().__init__(symbol, magic)
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.proximity_pips = proximity_pips
        self.entry_buffer = entry_buffer
        self.sl_buffer = sl_buffer
        self.tp_distances = tp_distances or [25.0, 50.0]

    @property
    def name(self) -> str:
        return "TREND"

    def scan(
        self,
        df: pd.DataFrame,
        current_price: float,
    ) -> Optional[Signal]:
        """
        Detecta pullbacks a SMA20 en dirección de la tendencia.
        """
        min_candles = self.slow_period + 1
        if len(df) < min_candles:
            return None

        # Calcular SMAs
        sma_fast = sma(df, self.fast_period)
        sma_slow = sma(df, self.slow_period)

        current_sma_fast = float(sma_fast.iloc[-1])
        current_sma_slow = float(sma_slow.iloc[-1])

        # Verificar que las SMAs son válidas
        if pd.isna(current_sma_fast) or pd.isna(current_sma_slow):
            return None

        distance_to_sma = abs(current_price - current_sma_fast)

        # Si el precio no está cerca de la SMA20, no hay pullback
        if distance_to_sma > self.proximity_pips:
            return None

        msg_id = int(df.index[-1].timestamp())

        # UPTREND: SMA20 > SMA50 → buscar BUY en pullback
        if current_sma_fast > current_sma_slow:
            # Confirmar que el precio viene desde arriba (pullback real)
            if current_price >= current_sma_fast:
                entry = current_sma_fast + self.entry_buffer
                sl = current_sma_fast - self.sl_buffer
                tps = [round(entry + d, 2) for d in self.tp_distances]

                return self._make_signal(
                    side="BUY",
                    entry=round(entry, 2),
                    sl=round(sl, 2),
                    tps=tps,
                    msg_id=msg_id,
                )

        # DOWNTREND: SMA20 < SMA50 → buscar SELL en pullback
        elif current_sma_fast < current_sma_slow:
            # Confirmar que el precio viene desde abajo (pullback real)
            if current_price <= current_sma_fast:
                entry = current_sma_fast - self.entry_buffer
                sl = current_sma_fast + self.sl_buffer
                tps = [round(entry - d, 2) for d in self.tp_distances]

                return self._make_signal(
                    side="SELL",
                    entry=round(entry, 2),
                    sl=round(sl, 2),
                    tps=tps,
                    msg_id=msg_id,
                )

        return None