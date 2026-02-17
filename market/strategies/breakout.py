# market/strategies/breakout.py
"""
Estrategia de Breakout.

Entrada: SELL/BUY LIMIT en el nivel roto (pullback).
SL/TP: Fijos desde config (sl_distance, tp_distances).

Mejoras v2:
  - Zona de breakout basada en High/Low del día anterior (D1)
    en vez de las últimas 24 velas H1
  - Filtro EMA 50/200: confirma dirección de tendencia mayor.
    Modo SUAVE: no bloquea la entrada pero loguea EMA_FILTER_SKIP
    para analizar impacto antes de hacerlo duro.

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
from infrastructure.logging import get_logger
from market.data_provider import DataProvider
from market.indicators import atr, ema
from .base import BaseStrategy


class BreakoutStrategy(BaseStrategy):
    """
    Setup SELL: precio < Low del día anterior - breakout_buffer
                → SELL LIMIT en el nivel roto (pullback al low)

    Setup BUY:  precio > High del día anterior + breakout_buffer
                → BUY LIMIT en el nivel roto (pullback al high)

    Filtro EMA (suave): solo loguea cuando EMA50/200 no confirman.
    """

    def __init__(
        self,
        symbol: str,
        magic: int,
        breakout_buffer: float = 2.0,
        atr_period: int = 14,
        # Filtro 1: Frescura
        fresh_candles: int = 4,
        # Filtro 2: Volumen
        volume_period: int = 20,
        volume_factor: float = 1.0,
        # Filtro 3: No perseguir precio
        max_chase_atr: float = 1.0,
        # EMA para filtro de tendencia mayor
        ema_fast: int = 50,
        ema_slow: int = 200,
    ):
        super().__init__(symbol, magic)
        self.breakout_buffer = breakout_buffer
        self.atr_period = atr_period
        self.fresh_candles = fresh_candles
        self.volume_period = volume_period
        self.volume_factor = volume_factor
        self.max_chase_atr = max_chase_atr
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.logger = get_logger()

        # DataProvider interno para velas D1
        self._d1_provider = DataProvider(symbol)

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

    def _get_daily_levels(self) -> tuple[Optional[float], Optional[float]]:
        """
        Obtiene High/Low del día anterior desde velas D1.

        Returns:
            (daily_high, daily_low) o (None, None) si no hay datos.
        """
        try:
            df_d1 = self._d1_provider.get_candles(timeframe="D1", count=5)
            if df_d1 is None or len(df_d1) < 2:
                return None, None
            # iloc[-2] = día anterior (el último es el día actual, incompleto)
            prev_day = df_d1.iloc[-2]
            return float(prev_day["high"]), float(prev_day["low"])
        except Exception as ex:
            self.logger.error("BREAKOUT_D1_ERROR", error=str(ex))
            return None, None

    def _check_ema_direction(
        self,
        df: pd.DataFrame,
        side: str,
    ) -> bool:
        """
        Verifica que EMA50 y EMA200 confirman la dirección.

        Returns:
            True si confirma, False si no confirma (filtro suave: solo loguea).
        """
        min_candles_needed = self.ema_slow + 1
        if len(df) < min_candles_needed:
            return True  # Sin datos suficientes, no filtrar

        ema_fast_series = ema(df, self.ema_fast)
        ema_slow_series = ema(df, self.ema_slow)

        ema_fast_val = float(ema_fast_series.iloc[-1])
        ema_slow_val = float(ema_slow_series.iloc[-1])

        if pd.isna(ema_fast_val) or pd.isna(ema_slow_val):
            return True  # Sin datos, no filtrar

        if side == "BUY":
            return ema_fast_val > ema_slow_val
        else:
            return ema_fast_val < ema_slow_val

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
        search_limit = min(self.fresh_candles + 24, len(df))

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
        min_candles = max(25, self.atr_period + 1)
        if len(df) < min_candles:
            return None

        atr_series = atr(df, period=self.atr_period)
        atr_value = float(atr_series.iloc[-1])
        if pd.isna(atr_value) or atr_value <= 0:
            return None

        # Obtener niveles del día anterior (D1)
        daily_high, daily_low = self._get_daily_levels()
        if daily_high is None or daily_low is None:
            return None

        sl_distance = float(getattr(CFG, "SL_DISTANCE", 6.0))
        max_chase = self.max_chase_atr * atr_value
        msg_id = int(df.index[-1].timestamp())

        # ==========================================
        # SELL BREAKOUT → SELL LIMIT en nivel roto
        # ==========================================
        sell_level = daily_low - self.breakout_buffer
        if current_price < sell_level:

            # Filtro 3: No perseguir
            if (sell_level - current_price) > max_chase:
                return None

            # Filtro 1: Frescura
            breakout_idx = self._find_breakout_candle(df, daily_low, "SELL")
            if breakout_idx is None or breakout_idx > self.fresh_candles:
                return None

            # Filtro 2: Volumen
            if not self._check_volume(df, breakout_idx):
                return None

            # Filtro EMA (suave): loguea si no confirma pero no bloquea
            if not self._check_ema_direction(df, "SELL"):
                self.logger.event(
                    "EMA_FILTER_SKIP",
                    side="SELL",
                    entry=round(daily_low, 2),
                    current_price=current_price,
                    detail="EMA50 > EMA200, tendencia alcista pero señal SELL generada",
                )

            entry = round(daily_low, 2)
            sl = round(entry + sl_distance, 2)
            tps = self._calculate_tps("SELL", entry)
            return self._make_signal("SELL", entry, sl, tps, msg_id)

        # ==========================================
        # BUY BREAKOUT → BUY LIMIT en nivel roto
        # ==========================================
        buy_level = daily_high + self.breakout_buffer
        if current_price > buy_level:

            # Filtro 3: No perseguir
            if (current_price - buy_level) > max_chase:
                return None

            # Filtro 1: Frescura
            breakout_idx = self._find_breakout_candle(df, daily_high, "BUY")
            if breakout_idx is None or breakout_idx > self.fresh_candles:
                return None

            # Filtro 2: Volumen
            if not self._check_volume(df, breakout_idx):
                return None

            # Filtro EMA (suave): loguea si no confirma pero no bloquea
            if not self._check_ema_direction(df, "BUY"):
                self.logger.event(
                    "EMA_FILTER_SKIP",
                    side="BUY",
                    entry=round(daily_high, 2),
                    current_price=current_price,
                    detail="EMA50 < EMA200, tendencia bajista pero señal BUY generada",
                )

            entry = round(daily_high, 2)
            sl = round(entry - sl_distance, 2)
            tps = self._calculate_tps("BUY", entry)
            return self._make_signal("BUY", entry, sl, tps, msg_id)

        return None