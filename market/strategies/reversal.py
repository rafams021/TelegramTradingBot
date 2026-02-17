# market/strategies/reversal.py
"""
Estrategia de Reversión en Soporte/Resistencia.

Detecta cuando el precio está cerca de un nivel clave y hay
condiciones para una reversión.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from core.models import Signal
from market.indicators import support_resistance_levels, rsi
from .base import BaseStrategy


class ReversalStrategy(BaseStrategy):
    """
    Estrategia de reversión en niveles de S/R.

    Setup BUY (rebote en soporte):
        - Precio cerca de un nivel de soporte (dentro de proximity_pips)
        - RSI < rsi_oversold (zona de sobreventa)
        - Entry: nivel de soporte + entry_buffer
        - SL: nivel de soporte - sl_buffer
        - TPs: entry + tp_distances

    Setup SELL (rechazo en resistencia):
        - Precio cerca de un nivel de resistencia (dentro de proximity_pips)
        - RSI > rsi_overbought (zona de sobrecompra)
        - Entry: nivel de resistencia - entry_buffer
        - SL: nivel de resistencia + sl_buffer
        - TPs: entry - tp_distances
    """

    def __init__(
        self,
        symbol: str,
        magic: int,
        lookback_candles: int = 20,
        proximity_pips: float = 3.0,
        entry_buffer: float = 1.0,
        sl_buffer: float = 10.0,
        tp_distances: list = None,
        rsi_period: int = 14,
        rsi_oversold: float = 40.0,
        rsi_overbought: float = 60.0,
    ):
        """
        Args:
            symbol: Símbolo a operar
            magic: Número mágico
            lookback_candles: Velas para detectar niveles S/R
            proximity_pips: Distancia máxima al nivel para considerar "cerca"
            entry_buffer: Buffer sobre soporte / bajo resistencia para entry
            sl_buffer: Buffer bajo soporte / sobre resistencia para SL
            tp_distances: Distancias en pips para TPs (default: [20, 40])
            rsi_period: Período del RSI
            rsi_oversold: Umbral de sobreventa para BUY
            rsi_overbought: Umbral de sobrecompra para SELL
        """
        super().__init__(symbol, magic)
        self.lookback_candles = lookback_candles
        self.proximity_pips = proximity_pips
        self.entry_buffer = entry_buffer
        self.sl_buffer = sl_buffer
        self.tp_distances = tp_distances or [20.0, 40.0]
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought

    @property
    def name(self) -> str:
        return "REVERSAL"

    def scan(
        self,
        df: pd.DataFrame,
        current_price: float,
    ) -> Optional[Signal]:
        """
        Detecta reversiones en niveles de S/R con confirmación RSI.
        """
        min_candles = max(self.lookback_candles, self.rsi_period + 1)
        if len(df) < min_candles:
            return None

        # Calcular niveles S/R y RSI actual
        levels = support_resistance_levels(df, lookback=self.lookback_candles)
        if not levels:
            return None

        rsi_series = rsi(df, period=self.rsi_period)
        current_rsi = float(rsi_series.iloc[-1])

        msg_id = int(df.index[-1].timestamp())

        # Buscar el nivel más cercano al precio actual
        closest_level = min(levels, key=lambda l: abs(l - current_price))
        distance = abs(current_price - closest_level)

        if distance > self.proximity_pips:
            return None

        # BUY: precio en zona de soporte + RSI en sobreventa
        if current_price <= closest_level and current_rsi < self.rsi_oversold:
            entry = closest_level + self.entry_buffer
            sl = closest_level - self.sl_buffer
            tps = [round(entry + d, 2) for d in self.tp_distances]

            return self._make_signal(
                side="BUY",
                entry=round(entry, 2),
                sl=round(sl, 2),
                tps=tps,
                msg_id=msg_id,
            )

        # SELL: precio en zona de resistencia + RSI en sobrecompra
        if current_price >= closest_level and current_rsi > self.rsi_overbought:
            entry = closest_level - self.entry_buffer
            sl = closest_level + self.sl_buffer
            tps = [round(entry - d, 2) for d in self.tp_distances]

            return self._make_signal(
                side="SELL",
                entry=round(entry, 2),
                sl=round(sl, 2),
                tps=tps,
                msg_id=msg_id,
            )

        return None