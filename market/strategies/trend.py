# market/strategies/trend.py
"""
Estrategia de Trend Following con pullbacks a SMA20.

Entrada: MARKET en toque de SMA20.
SL/TP: Fijos desde config (sl_distance, tp_distances).

OPTIMIZADO (backtest 6 meses):
- session_filter: EU+NY (08:00-22:00 UTC)

Resultados esperados:
- Win rate: ~51%
- P&L: ~$0.95/trade
- Mejor performer de las dos estrategias activas
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

import config as CFG
from core.models import Signal
from market.indicators import sma, atr
from .base import BaseStrategy


class TrendStrategy(BaseStrategy):

    def __init__(
        self,
        symbol: str,
        magic: int,
        fast_period: int = 20,
        slow_period: int = 50,
        proximity_pips: float = 2.0,
        atr_period: int = 14,
    ):
        super().__init__(symbol, magic)
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.proximity_pips = proximity_pips
        self.atr_period = atr_period

    @property
    def name(self) -> str:
        return "TREND"

    def _calculate_tps(self, side: str, entry: float) -> list:
        """TPs fijos desde config."""
        distances = list(getattr(CFG, "TP_DISTANCES", (5.0, 11.0, 16.0)))
        if side == "BUY":
            return [round(entry + d, 2) for d in distances]
        else:
            return [round(entry - d, 2) for d in distances]

    def _is_valid_session(self, ts: pd.Timestamp) -> bool:
        """
        Filtro de sesión: solo Europa + NY (08:00-22:00 UTC).
        """
        session_filter = getattr(CFG, "SESSION_FILTER", "24h")
        
        if session_filter == "24h":
            return True
        
        hour_utc = ts.hour
        
        if session_filter == "eu_ny":
            return 8 <= hour_utc < 22
        
        if session_filter == "ny_only":
            return 13 <= hour_utc < 22
        
        return True

    def scan(self, df: pd.DataFrame, current_price: float) -> Optional[Signal]:
        min_candles = max(self.slow_period + 1, self.atr_period + 1)
        if len(df) < min_candles:
            return None

        # Filtro de sesión
        ts = df.index[-1]
        if not self._is_valid_session(ts):
            return None

        sma_fast = sma(df, self.fast_period)
        sma_slow = sma(df, self.slow_period)

        current_sma_fast = float(sma_fast.iloc[-1])
        current_sma_slow = float(sma_slow.iloc[-1])

        if pd.isna(current_sma_fast) or pd.isna(current_sma_slow):
            return None

        atr_series = atr(df, period=self.atr_period)
        atr_value = float(atr_series.iloc[-1])
        if pd.isna(atr_value) or atr_value <= 0:
            return None

        if abs(current_price - current_sma_fast) > self.proximity_pips:
            return None

        sl_distance = float(getattr(CFG, "SL_DISTANCE", 6.0))
        msg_id = int(df.index[-1].timestamp())

        # UPTREND: BUY MARKET en toque de SMA20
        if current_sma_fast > current_sma_slow and current_price >= current_sma_fast:
            entry = round(current_price, 2)
            sl = round(entry - sl_distance, 2)
            tps = self._calculate_tps("BUY", entry)
            return self._make_signal("BUY", entry, sl, tps, msg_id)

        # DOWNTREND: SELL MARKET en toque de SMA20
        if current_sma_fast < current_sma_slow and current_price <= current_sma_fast:
            entry = round(current_price, 2)
            sl = round(entry + sl_distance, 2)
            tps = self._calculate_tps("SELL", entry)
            return self._make_signal("SELL", entry, sl, tps, msg_id)

        return None