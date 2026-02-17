# market/strategies/trend.py
"""
Estrategia de Trend Following con pullbacks a SMA20.

TPs calculados con ATR + R:R mínimo garantizado.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from core.models import Signal
from market.indicators import sma, atr
from .base import BaseStrategy


class TrendStrategy(BaseStrategy):
    """
    Setup BUY:  SMA20 > SMA50 + precio cerca de SMA20 desde arriba
    Setup SELL: SMA20 < SMA50 + precio cerca de SMA20 desde abajo

    TPs: max(ATR_multiple × ATR, min_rr × SL_distance)
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
        atr_period: int = 14,
        atr_multiples: list = None,
        min_rr_multiples: list = None,
    ):
        super().__init__(symbol, magic)
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.proximity_pips = proximity_pips
        self.entry_buffer = entry_buffer
        self.sl_buffer = sl_buffer
        self.atr_period = atr_period
        self.atr_multiples = atr_multiples or [1.0, 2.0, 3.0]
        self.min_rr_multiples = min_rr_multiples or [1.5, 2.0, 3.0]

    @property
    def name(self) -> str:
        return "TREND"

    def _calculate_tps(
        self,
        side: str,
        entry: float,
        sl: float,
        atr_value: float,
    ) -> list:
        sl_distance = abs(entry - sl)
        tps = []
        for atr_mult, rr_mult in zip(self.atr_multiples, self.min_rr_multiples):
            tp_distance = max(atr_mult * atr_value, rr_mult * sl_distance)
            if side == "BUY":
                tps.append(round(entry + tp_distance, 2))
            else:
                tps.append(round(entry - tp_distance, 2))
        return tps

    def scan(self, df: pd.DataFrame, current_price: float) -> Optional[Signal]:
        min_candles = max(self.slow_period + 1, self.atr_period + 1)
        if len(df) < min_candles:
            return None

        sma_fast = sma(df, self.fast_period)
        sma_slow = sma(df, self.slow_period)

        current_sma_fast = float(sma_fast.iloc[-1])
        current_sma_slow = float(sma_slow.iloc[-1])

        if pd.isna(current_sma_fast) or pd.isna(current_sma_slow):
            return None

        if abs(current_price - current_sma_fast) > self.proximity_pips:
            return None

        atr_series = atr(df, period=self.atr_period)
        atr_value = float(atr_series.iloc[-1])
        if pd.isna(atr_value) or atr_value <= 0:
            return None

        msg_id = int(df.index[-1].timestamp())

        # UPTREND: BUY pullback a SMA20
        if current_sma_fast > current_sma_slow and current_price >= current_sma_fast:
            entry = round(current_sma_fast + self.entry_buffer, 2)
            sl = round(current_sma_fast - self.sl_buffer, 2)
            tps = self._calculate_tps("BUY", entry, sl, atr_value)
            return self._make_signal("BUY", entry, sl, tps, msg_id)

        # DOWNTREND: SELL pullback a SMA20
        if current_sma_fast < current_sma_slow and current_price <= current_sma_fast:
            entry = round(current_sma_fast - self.entry_buffer, 2)
            sl = round(current_sma_fast + self.sl_buffer, 2)
            tps = self._calculate_tps("SELL", entry, sl, atr_value)
            return self._make_signal("SELL", entry, sl, tps, msg_id)

        return None