# market/strategies/breakout.py
"""
Estrategia de Breakout.

SL: entry ± (1.5 × ATR) — ajustado a volatilidad actual.
TPs: ATR escalonado [0.5, 1.0, 2.0] con R:R mínimo [1.0, 1.5, 2.0].
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from core.models import Signal
from market.indicators import recent_high, recent_low, atr
from .base import BaseStrategy


class BreakoutStrategy(BaseStrategy):
    """
    Setup BUY:  precio > high(N velas) + breakout_buffer
    Setup SELL: precio < low(N velas) - breakout_buffer

    SL: entry ± (sl_atr_multiple × ATR)
        Proporcional a la volatilidad — no depende del high/low histórico.

    TPs: max(atr_multiple × ATR, min_rr × SL_distance)
        TP1 cercano (0.5 ATR), TP2 medio (1.0 ATR), TP3 ambicioso (2.0 ATR)
    """

    def __init__(
        self,
        symbol: str,
        magic: int,
        lookback_candles: int = 24,
        breakout_buffer: float = 2.0,
        sl_atr_multiple: float = 1.5,
        atr_period: int = 14,
        atr_multiples: list = None,
        min_rr_multiples: list = None,
    ):
        """
        Args:
            symbol: Símbolo a operar
            magic: Número mágico
            lookback_candles: Velas para detectar high/low (default: 24h en H1)
            breakout_buffer: Pips sobre high/bajo low para confirmar ruptura
            sl_atr_multiple: Múltiplo de ATR para el SL (default: 1.5)
            atr_period: Período del ATR (default: 14)
            atr_multiples: Múltiplos ATR para TPs (default: [0.5, 1.0, 2.0])
            min_rr_multiples: R:R mínimo por TP (default: [1.0, 1.5, 2.0])
        """
        super().__init__(symbol, magic)
        self.lookback_candles = lookback_candles
        self.breakout_buffer = breakout_buffer
        self.sl_atr_multiple = sl_atr_multiple
        self.atr_period = atr_period
        self.atr_multiples = atr_multiples or [0.5, 1.0, 2.0]
        self.min_rr_multiples = min_rr_multiples or [1.0, 1.5, 2.0]

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
        min_candles = max(self.lookback_candles + 1, self.atr_period + 1)
        if len(df) < min_candles:
            return None

        high = recent_high(df.iloc[:-1], self.lookback_candles)
        low = recent_low(df.iloc[:-1], self.lookback_candles)

        atr_series = atr(df, period=self.atr_period)
        atr_value = float(atr_series.iloc[-1])
        if pd.isna(atr_value) or atr_value <= 0:
            return None

        msg_id = int(df.index[-1].timestamp())
        sl_distance = self.sl_atr_multiple * atr_value

        # BUY breakout
        if current_price > high + self.breakout_buffer:
            entry = current_price
            sl = round(entry - sl_distance, 2)
            tps = self._calculate_tps("BUY", entry, sl, atr_value)
            return self._make_signal("BUY", round(entry, 2), sl, tps, msg_id)

        # SELL breakout
        if current_price < low - self.breakout_buffer:
            entry = current_price
            sl = round(entry + sl_distance, 2)
            tps = self._calculate_tps("SELL", entry, sl, atr_value)
            return self._make_signal("SELL", round(entry, 2), sl, tps, msg_id)

        return None