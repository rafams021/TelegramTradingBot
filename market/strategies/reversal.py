# market/strategies/reversal.py
"""
Estrategia de Reversión en Soporte/Resistencia.

SL: entry ± (sl_atr_multiple × ATR)
TPs: ATR escalonado [0.5, 1.0, 2.0] con R:R mínimo [1.0, 1.5, 2.0].
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from core.models import Signal
from market.indicators import support_resistance_levels, rsi, atr
from .base import BaseStrategy


class ReversalStrategy(BaseStrategy):

    def __init__(
        self,
        symbol: str,
        magic: int,
        lookback_candles: int = 20,
        proximity_pips: float = 3.0,
        entry_buffer: float = 1.0,
        sl_atr_multiple: float = 1.5,
        atr_period: int = 14,
        atr_multiples: list = None,
        min_rr_multiples: list = None,
        rsi_period: int = 14,
        rsi_oversold: float = 40.0,
        rsi_overbought: float = 60.0,
    ):
        super().__init__(symbol, magic)
        self.lookback_candles = lookback_candles
        self.proximity_pips = proximity_pips
        self.entry_buffer = entry_buffer
        self.sl_atr_multiple = sl_atr_multiple
        self.atr_period = atr_period
        self.atr_multiples = atr_multiples or [0.5, 1.0, 2.0]
        self.min_rr_multiples = min_rr_multiples or [1.0, 1.5, 2.0]
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought

    @property
    def name(self) -> str:
        return "REVERSAL"

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
        min_candles = max(self.lookback_candles, self.rsi_period + 1, self.atr_period + 1)
        if len(df) < min_candles:
            return None

        levels = support_resistance_levels(df, lookback=self.lookback_candles)
        if not levels:
            return None

        current_rsi = float(rsi(df, period=self.rsi_period).iloc[-1])

        atr_series = atr(df, period=self.atr_period)
        atr_value = float(atr_series.iloc[-1])
        if pd.isna(atr_value) or atr_value <= 0:
            return None

        msg_id = int(df.index[-1].timestamp())
        sl_distance = self.sl_atr_multiple * atr_value

        closest_level = min(levels, key=lambda l: abs(l - current_price))
        if abs(current_price - closest_level) > self.proximity_pips:
            return None

        # BUY: en soporte + sobreventa
        if current_price <= closest_level and current_rsi < self.rsi_oversold:
            entry = round(closest_level + self.entry_buffer, 2)
            sl = round(entry - sl_distance, 2)
            tps = self._calculate_tps("BUY", entry, sl, atr_value)
            return self._make_signal("BUY", entry, sl, tps, msg_id)

        # SELL: en resistencia + sobrecompra
        if current_price >= closest_level and current_rsi > self.rsi_overbought:
            entry = round(closest_level - self.entry_buffer, 2)
            sl = round(entry + sl_distance, 2)
            tps = self._calculate_tps("SELL", entry, sl, atr_value)
            return self._make_signal("SELL", entry, sl, tps, msg_id)

        return None