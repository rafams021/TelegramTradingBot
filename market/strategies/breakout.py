# market/strategies/breakout.py
"""
Estrategia de Breakout con filtros de calidad.

Filtros:
  1. Frescura: ruptura máximo fresh_candles velas atrás
  2. Volumen: vela de ruptura > promedio de últimas N velas
  3. No perseguir: precio no más de max_chase_atr × ATR desde el nivel roto

SL: entry ± (sl_atr_multiple × ATR)
TPs: ATR escalonado [0.5, 1.0, 2.0] con R:R mínimo [1.0, 1.5, 2.0]
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
                + ruptura fresca + volumen + no perseguir

    Setup SELL: precio < low(N velas) - breakout_buffer
                + ruptura fresca + volumen + no perseguir
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
        # Filtro 1: Frescura
        fresh_candles: int = 2,
        # Filtro 2: Volumen
        volume_period: int = 20,
        volume_factor: float = 1.2,
        # Filtro 3: No perseguir precio
        max_chase_atr: float = 1.0,
    ):
        """
        Args:
            symbol: Símbolo a operar
            magic: Número mágico
            lookback_candles: Velas para detectar high/low (default: 24)
            breakout_buffer: Pips sobre high/bajo low para confirmar ruptura
            sl_atr_multiple: Múltiplo ATR para SL (default: 1.5)
            atr_period: Período ATR (default: 14)
            atr_multiples: Múltiplos ATR para TPs (default: [0.5, 1.0, 2.0])
            min_rr_multiples: R:R mínimo por TP (default: [1.0, 1.5, 2.0])
            fresh_candles: Máximo de velas desde la ruptura (default: 2)
            volume_period: Velas para calcular volumen promedio (default: 20)
            volume_factor: Factor mínimo sobre volumen promedio (default: 1.2)
            max_chase_atr: Máximo drift desde el nivel en múltiplos ATR (default: 1.0)
        """
        super().__init__(symbol, magic)
        self.lookback_candles = lookback_candles
        self.breakout_buffer = breakout_buffer
        self.sl_atr_multiple = sl_atr_multiple
        self.atr_period = atr_period
        self.atr_multiples = atr_multiples or [0.5, 1.0, 2.0]
        self.min_rr_multiples = min_rr_multiples or [1.0, 1.5, 2.0]
        self.fresh_candles = fresh_candles
        self.volume_period = volume_period
        self.volume_factor = volume_factor
        self.max_chase_atr = max_chase_atr

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

    def _find_breakout_candle(
        self,
        df: pd.DataFrame,
        level: float,
        side: str,
    ) -> Optional[int]:
        """
        Busca la vela donde ocurrió la ruptura del nivel.

        Busca hacia atrás desde la vela más reciente hasta
        encontrar la primera vela que rompió el nivel.

        Returns:
            Índice desde el final (0 = vela actual, 1 = anterior, etc.)
            o None si no encuentra ruptura en las últimas fresh_candles+lookback velas
        """
        search_limit = min(self.fresh_candles + self.lookback_candles, len(df))

        for i in range(search_limit):
            idx = -(i + 1)  # desde el final
            candle = df.iloc[idx]

            if side == "SELL":
                # Ruptura SELL: close de la vela rompió bajo el nivel
                if float(candle["close"]) < level:
                    return i
            else:
                # Ruptura BUY: close de la vela rompió sobre el nivel
                if float(candle["close"]) > level:
                    return i

        return None

    def _check_volume(
        self,
        df: pd.DataFrame,
        breakout_candle_idx: int,
    ) -> bool:
        """
        Verifica que la vela de ruptura tuvo volumen significativo.

        Args:
            breakout_candle_idx: Índice desde el final (0=actual, 1=anterior...)

        Returns:
            True si el volumen de la ruptura supera el factor mínimo
        """
        if "tick_volume" not in df.columns:
            return True  # Si no hay volumen, no filtramos

        # Volumen de la vela de ruptura
        breakout_vol = float(df.iloc[-(breakout_candle_idx + 1)]["tick_volume"])

        # Volumen promedio excluyendo las últimas fresh_candles velas
        vol_data = df["tick_volume"].iloc[-(self.volume_period + self.fresh_candles):-self.fresh_candles]
        if len(vol_data) == 0:
            return True

        avg_vol = float(vol_data.mean())
        if avg_vol <= 0:
            return True

        return breakout_vol >= (self.volume_factor * avg_vol)

    def scan(self, df: pd.DataFrame, current_price: float) -> Optional[Signal]:
        min_candles = max(
            self.lookback_candles + 1,
            self.atr_period + 1,
            self.volume_period + self.fresh_candles + 1,
        )
        if len(df) < min_candles:
            return None

        # Calcular high/low excluyendo la vela actual
        high = recent_high(df.iloc[:-1], self.lookback_candles)
        low = recent_low(df.iloc[:-1], self.lookback_candles)

        atr_series = atr(df, period=self.atr_period)
        atr_value = float(atr_series.iloc[-1])
        if pd.isna(atr_value) or atr_value <= 0:
            return None

        msg_id = int(df.index[-1].timestamp())
        sl_distance = self.sl_atr_multiple * atr_value
        max_chase = self.max_chase_atr * atr_value

        # ==========================================
        # SELL BREAKOUT
        # ==========================================
        sell_level = low - self.breakout_buffer
        if current_price < sell_level:

            # Filtro 3: No perseguir — precio no demasiado lejos del nivel
            if (sell_level - current_price) > max_chase:
                return None

            # Filtro 1: Frescura — ruptura reciente
            breakout_idx = self._find_breakout_candle(df, low, "SELL")
            if breakout_idx is None or breakout_idx > self.fresh_candles:
                return None

            # Filtro 2: Volumen — ruptura con convicción
            if not self._check_volume(df, breakout_idx):
                return None

            entry = current_price
            sl = round(entry + sl_distance, 2)
            tps = self._calculate_tps("SELL", round(entry, 2), sl, atr_value)
            return self._make_signal("SELL", round(entry, 2), sl, tps, msg_id)

        # ==========================================
        # BUY BREAKOUT
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

            entry = current_price
            sl = round(entry - sl_distance, 2)
            tps = self._calculate_tps("BUY", round(entry, 2), sl, atr_value)
            return self._make_signal("BUY", round(entry, 2), sl, tps, msg_id)

        return None