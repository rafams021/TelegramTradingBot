# market/strategies/breakout.py
"""
Estrategia de Breakout.

Entrada: SELL/BUY LIMIT en el nivel roto (pullback).
SL/TP: Fijos desde config (sl_distance, tp_distances).

Filtros de calidad:
  1. Frescura: ruptura máximo fresh_candles velas atrás
  2. Volumen: vela de ruptura > promedio × volume_factor
  3. No perseguir: precio no más de max_chase_atr × ATR desde nivel
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

import config as CFG
from core.models import Signal
from market.indicators import recent_high, recent_low, atr
from .base import BaseStrategy


class BreakoutStrategy(BaseStrategy):
    """
    Setup SELL: precio < low(N velas) - breakout_buffer
                → SELL LIMIT en el nivel roto (pullback al low)

    Setup BUY:  precio > high(N velas) + breakout_buffer
                → BUY LIMIT en el nivel roto (pullback al high)
    """

    def __init__(
        self,
        symbol: str,
        magic: int,
        lookback_candles: int = 24,
        breakout_buffer: float = 2.0,
        atr_period: int = 14,
        # Filtro 1: Frescura
        fresh_candles: int = 2,
        # Filtro 2: Volumen
        volume_period: int = 20,
        volume_factor: float = 1.2,
        # Filtro 3: No perseguir precio
        max_chase_atr: float = 1.0,
    ):
        super().__init__(symbol, magic)
        self.lookback_candles = lookback_candles
        self.breakout_buffer = breakout_buffer
        self.atr_period = atr_period
        self.fresh_candles = fresh_candles
        self.volume_period = volume_period
        self.volume_factor = volume_factor
        self.max_chase_atr = max_chase_atr

    @property
    def name(self) -> str:
        return "BREAKOUT"

    def _calculate_tps(self, side: str, entry: float) -> list:
        """TPs fijos desde config."""
        distances = list(getattr(CFG, "TP_DISTANCES", (5.0, 11.0, 16.0)))
        if side == "BUY":
            return [round(entry + d, 2) for d in distances]
        else:
            return [round(entry - d, 2) for d in distances]

    def _find_breakout_candle(
        self,
        df: pd.DataFrame,
        level: float,
        side: str,
    ) -> Optional[int]:
        """
        Busca la vela donde ocurrió la ruptura del nivel.

        Returns:
            Índice desde el final (0 = más reciente) o None si no encuentra.
        """
        search_limit = min(self.fresh_candles + self.lookback_candles, len(df))

        for i in range(search_limit):
            idx = -(i + 1)
            candle = df.iloc[idx]

            if side == "SELL":
                if float(candle["close"]) < level:
                    return i
            else:
                if float(candle["close"]) > level:
                    return i

        return None

    def _check_volume(self, df: pd.DataFrame, breakout_candle_idx: int) -> bool:
        """Verifica que la vela de ruptura tuvo volumen significativo."""
        if len(df) < self.volume_period + 1:
            return True  # Sin datos suficientes, no filtrar

        idx = -(breakout_candle_idx + 1)
        breakout_vol = float(df.iloc[idx]["tick_volume"])

        avg_start = -(breakout_candle_idx + self.volume_period + 1)
        avg_end = -(breakout_candle_idx + 1)
        if avg_end == 0:
            avg_end = None
        avg_vol = float(df.iloc[avg_start:avg_end]["tick_volume"].mean())

        if avg_vol <= 0:
            return True

        return breakout_vol >= (avg_vol * self.volume_factor)

    def scan(self, df: pd.DataFrame, current_price: float) -> Optional[Signal]:
        min_candles = max(self.lookback_candles + 1, self.atr_period + 1)
        if len(df) < min_candles:
            return None

        atr_series = atr(df, period=self.atr_period)
        atr_value = float(atr_series.iloc[-1])
        if pd.isna(atr_value) or atr_value <= 0:
            return None

        sl_distance = float(getattr(CFG, "SL_DISTANCE", 6.0))
        max_chase = self.max_chase_atr * atr_value
        high = recent_high(df, self.lookback_candles)
        low = recent_low(df, self.lookback_candles)
        msg_id = int(df.index[-1].timestamp())

        # ==========================================
        # SELL BREAKOUT → SELL LIMIT en nivel roto
        # ==========================================
        sell_level = low - self.breakout_buffer
        if current_price < sell_level:

            # Filtro 3: No perseguir
            if (sell_level - current_price) > max_chase:
                return None

            # Filtro 1: Frescura
            breakout_idx = self._find_breakout_candle(df, low, "SELL")
            if breakout_idx is None or breakout_idx > self.fresh_candles:
                return None

            # Filtro 2: Volumen
            if not self._check_volume(df, breakout_idx):
                return None

            # Entrada: LIMIT en el nivel roto (pullback al low)
            entry = round(low, 2)
            sl = round(entry + sl_distance, 2)
            tps = self._calculate_tps("SELL", entry)
            return self._make_signal("SELL", entry, sl, tps, msg_id)

        # ==========================================
        # BUY BREAKOUT → BUY LIMIT en nivel roto
        # ==========================================
        buy_level = high + self.breakout_buffer
        if current_price > buy_level:

            # Filtro 3: No perseguir
            if (current_price - buy_level) > max_chase:
                return None

            # Filtro 1: Frescura
            breakout_idx = self._find_breakout_candle(df, high, "BUY")
            if breakout_idx is None or breakout_idx > self.fresh_candles:
                return None

            # Filtro 2: Volumen
            if not self._check_volume(df, breakout_idx):
                return None

            # Entrada: LIMIT en el nivel roto (pullback al high)
            entry = round(high, 2)
            sl = round(entry - sl_distance, 2)
            tps = self._calculate_tps("BUY", entry)
            return self._make_signal("BUY", entry, sl, tps, msg_id)

        return None