# market/strategies/breakout.py
"""
Estrategia de Breakout.

TPs calculados con ATR + R:R mínimo garantizado.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from core.models import Signal
from market.indicators import recent_high, recent_low, atr
from .base import BaseStrategy


class BreakoutStrategy(BaseStrategy):
    """
    Setup BUY:  precio > high(N velas) + buffer → entry, SL bajo el high
    Setup SELL: precio < low(N velas) - buffer  → entry, SL sobre el low

    TPs: max(ATR_multiple × ATR, min_rr × SL_distance)
    Garantiza TPs alcanzables (ATR) y rentables (R:R mínimo).
    """

    def __init__(
        self,
        symbol: str,
        magic: int,
        lookback_candles: int = 24,
        breakout_buffer: float = 2.0,
        sl_buffer: float = 5.0,
        atr_period: int = 14,
        atr_multiples: list = None,
        min_rr_multiples: list = None,
    ):
        """
        Args:
            symbol: Símbolo a operar
            magic: Número mágico
            lookback_candles: Velas para calcular high/low (default: 24h en H1)
            breakout_buffer: Pips sobre high/bajo low para confirmar ruptura
            sl_buffer: Pips entre nivel roto y SL
            atr_period: Período del ATR (default: 14)
            atr_multiples: Múltiplos de ATR para cada TP (default: [1.0, 2.0, 3.0])
            min_rr_multiples: R:R mínimo por TP (default: [1.5, 2.0, 3.0])
        """
        super().__init__(symbol, magic)
        self.lookback_candles = lookback_candles
        self.breakout_buffer = breakout_buffer
        self.sl_buffer = sl_buffer
        self.atr_period = atr_period
        self.atr_multiples = atr_multiples or [1.0, 2.0, 3.0]
        self.min_rr_multiples = min_rr_multiples or [1.5, 2.0, 3.0]

    @property
    def name(self) -> str:
        return "BREAKOUT"

    def _calculate_tps(
        self,
        side: str,
        entry: float,
        sl: float,
        atr_value: float,
    ) -> list:
        """
        Calcula TPs usando ATR con R:R mínimo garantizado.

        Cada TP = entry ± max(atr_multiple × ATR, min_rr × SL_distance)
        """
        sl_distance = abs(entry - sl)
        tps = []

        for atr_mult, rr_mult in zip(self.atr_multiples, self.min_rr_multiples):
            atr_distance = atr_mult * atr_value
            rr_distance = rr_mult * sl_distance
            tp_distance = max(atr_distance, rr_distance)

            if side == "BUY":
                tp = round(entry + tp_distance, 2)
            else:
                tp = round(entry - tp_distance, 2)

            tps.append(tp)

        return tps

    def scan(self, df: pd.DataFrame, current_price: float) -> Optional[Signal]:
        min_candles = max(self.lookback_candles + 1, self.atr_period + 1)
        if len(df) < min_candles:
            return None

        # Calcular rango excluyendo la vela actual
        high = recent_high(df.iloc[:-1], self.lookback_candles)
        low = recent_low(df.iloc[:-1], self.lookback_candles)

        # Calcular ATR actual
        atr_series = atr(df, period=self.atr_period)
        atr_value = float(atr_series.iloc[-1])
        if pd.isna(atr_value) or atr_value <= 0:
            return None

        msg_id = int(df.index[-1].timestamp())

        # BUY breakout
        if current_price > high + self.breakout_buffer:
            entry = current_price
            sl = round(high - self.sl_buffer, 2)
            tps = self._calculate_tps("BUY", entry, sl, atr_value)
            return self._make_signal("BUY", round(entry, 2), sl, tps, msg_id)

        # SELL breakout
        if current_price < low - self.breakout_buffer:
            entry = current_price
            sl = round(low + self.sl_buffer, 2)
            tps = self._calculate_tps("SELL", entry, sl, atr_value)
            return self._make_signal("SELL", round(entry, 2), sl, tps, msg_id)

        return None