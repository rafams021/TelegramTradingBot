# market/strategies/reversal.py
"""
Estrategia de Reversión en Soporte/Resistencia.

Entrada: MARKET en soporte/resistencia con RSI extremo.
SL/TP: Fijos desde config (sl_distance, tp_distances).

PARÁMETROS OPTIMIZADOS (backtest 6 meses):
- proximity_pips: 8.0 (era 3.0)
- rsi_oversold: 45.0 (era 40.0)
- rsi_overbought: 55.0 (era 60.0)
- session_filter: EU+NY (08:00-22:00 UTC)

Resultados esperados:
- Win rate: ~47%
- P&L: ~$0.60/trade
- TP2/TP3 frecuentes (mejor que lookback optimista)
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

import config as CFG
from core.models import Signal
from market.indicators import support_resistance_levels, rsi, atr
from .base import BaseStrategy


class ReversalStrategy(BaseStrategy):

    def __init__(
        self,
        symbol: str,
        magic: int,
        lookback_candles: int = 20,
        proximity_pips: float = 8.0,       # Optimizado: era 3.0
        atr_period: int = 14,
        rsi_period: int = 14,
        rsi_oversold: float = 45.0,        # Optimizado: era 40.0
        rsi_overbought: float = 55.0,      # Optimizado: era 60.0
    ):
        super().__init__(symbol, magic)
        self.lookback_candles = lookback_candles
        self.proximity_pips = proximity_pips
        self.atr_period = atr_period
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought

    @property
    def name(self) -> str:
        return "REVERSAL"

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
        
        Sesión asiática (00:00-08:00) descartada por:
        - Bajo volumen
        - Movimientos falsos
        - Win rate inferior en backtest
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
        min_candles = max(self.lookback_candles, self.rsi_period + 1, self.atr_period + 1)
        if len(df) < min_candles:
            return None

        # Filtro de sesión
        ts = df.index[-1]
        if not self._is_valid_session(ts):
            return None

        levels = support_resistance_levels(df, lookback=self.lookback_candles)
        if not levels:
            return None

        current_rsi = float(rsi(df, period=self.rsi_period).iloc[-1])

        atr_series = atr(df, period=self.atr_period)
        atr_value = float(atr_series.iloc[-1])
        if pd.isna(atr_value) or atr_value <= 0:
            return None

        sl_distance = float(getattr(CFG, "SL_DISTANCE", 6.0))
        msg_id = int(df.index[-1].timestamp())

        closest_level = min(levels, key=lambda l: abs(l - current_price))
        if abs(current_price - closest_level) > self.proximity_pips:
            return None

        # BUY MARKET: en soporte + sobreventa
        if current_price <= closest_level and current_rsi < self.rsi_oversold:
            entry = round(current_price, 2)
            sl = round(entry - sl_distance, 2)
            tps = self._calculate_tps("BUY", entry)
            return self._make_signal("BUY", entry, sl, tps, msg_id)

        # SELL MARKET: en resistencia + sobrecompra
        if current_price >= closest_level and current_rsi > self.rsi_overbought:
            entry = round(current_price, 2)
            sl = round(entry + sl_distance, 2)
            tps = self._calculate_tps("SELL", entry)
            return self._make_signal("SELL", entry, sl, tps, msg_id)

        return None