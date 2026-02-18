# market/strategies/trend.py
"""
Estrategia de Trend Following con pullbacks a SMA20.

Entrada: MARKET en toque de SMA20.
SL/TP: Fijos desde config (sl_distance, tp_distances).

Optimizado (backtest 6 meses):
- session_filter: EU+NY (08:00-22:00 UTC)

Filtros activos:
- Momentum confirmation: ultimas 2 velas en direccion del trade
- Volume filter: volumen > 1.2x promedio de 20 velas
- ATR filter: skip si ATR < 8, ajustar si ATR > 25
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

import config as CFG
from core.state import Signal
from infrastructure.logging import get_logger
from market.indicators import sma, atr
from .base import BaseStrategy

logger = get_logger()


class TrendStrategy(BaseStrategy):

    def __init__(
        self,
        symbol: str,
        magic: int,
        fast_period: int = 20,
        slow_period: int = 50,
        proximity_pips: float = 2.0,
        atr_period: int = 14,
        enable_filters: bool = True,
        momentum_periods: int = 2,
        volume_multiplier: float = 1.2,
        min_atr: float = 8.0,
        max_atr: float = 25.0,
    ):
        super().__init__(symbol, magic)
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.proximity_pips = proximity_pips
        self.atr_period = atr_period
        self.enable_filters = enable_filters
        self.momentum_periods = momentum_periods
        self.volume_multiplier = volume_multiplier
        self.min_atr = min_atr
        self.max_atr = max_atr

    @property
    def name(self) -> str:
        return "TREND"

    def _calculate_tps(self, side: str, entry: float, tp_distances: tuple = None) -> list:
        if tp_distances is None:
            tp_distances = tuple(getattr(CFG, "TP_DISTANCES", (5.0, 11.0, 16.0)))
        if side == "BUY":
            return [round(entry + d, 2) for d in tp_distances]
        else:
            return [round(entry - d, 2) for d in tp_distances]

    def _check_momentum_confirmation(self, df: pd.DataFrame, side: str) -> bool:
        if not self.enable_filters:
            return True
        if len(df) < self.momentum_periods:
            return True

        last_candles = df.tail(self.momentum_periods)

        if side == "BUY":
            bullish_count = (last_candles["close"] > last_candles["open"]).sum()
            confirmed = bullish_count >= self.momentum_periods
            if not confirmed:
                logger.event("TREND_FILTER_REJECTED",
                             filter="momentum", side="BUY",
                             bullish=int(bullish_count), required=self.momentum_periods)
            return confirmed

        elif side == "SELL":
            bearish_count = (last_candles["close"] < last_candles["open"]).sum()
            confirmed = bearish_count >= self.momentum_periods
            if not confirmed:
                logger.event("TREND_FILTER_REJECTED",
                             filter="momentum", side="SELL",
                             bearish=int(bearish_count), required=self.momentum_periods)
            return confirmed

        return False

    def _check_volume_filter(self, df: pd.DataFrame, volume_periods: int = 20) -> bool:
        if not self.enable_filters:
            return True
        if len(df) < volume_periods:
            return True

        avg_volume = df["tick_volume"].tail(volume_periods).mean()
        current_volume = df["tick_volume"].iloc[-1]
        threshold = avg_volume * self.volume_multiplier

        if current_volume < threshold:
            logger.event("TREND_FILTER_REJECTED",
                         filter="volume",
                         current=float(current_volume),
                         threshold=float(threshold))
            return False
        return True

    def _check_atr_filter(self, atr_value: float) -> Optional[dict]:
        if not self.enable_filters:
            return {
                "sl": float(getattr(CFG, "SL_DISTANCE", 6.0)),
                "tp_distances": tuple(getattr(CFG, "TP_DISTANCES", (5.0, 11.0, 16.0))),
            }

        BASE_ATR = 15.0

        if atr_value < self.min_atr:
            logger.event("TREND_FILTER_REJECTED",
                         filter="atr", atr=round(atr_value, 2), min=self.min_atr)
            return None

        base_sl = float(getattr(CFG, "SL_DISTANCE", 6.0))
        base_tps = tuple(getattr(CFG, "TP_DISTANCES", (5.0, 11.0, 16.0)))

        if atr_value > self.max_atr:
            multiplier = atr_value / BASE_ATR
            logger.event("TREND_ATR_ADJUSTED",
                         atr=round(atr_value, 2), multiplier=round(multiplier, 2))
            return {
                "sl": base_sl * multiplier,
                "tp_distances": tuple(tp * multiplier for tp in base_tps),
            }

        return {"sl": base_sl, "tp_distances": base_tps}

    def scan(self, df: pd.DataFrame, current_price: float) -> Optional[Signal]:
        min_candles = max(self.slow_period + 1, self.atr_period + 1)
        if len(df) < min_candles:
            return None

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

        msg_id = int(df.index[-1].timestamp())

        potential_side = None
        if current_sma_fast > current_sma_slow and current_price >= current_sma_fast:
            potential_side = "BUY"
        elif current_sma_fast < current_sma_slow and current_price <= current_sma_fast:
            potential_side = "SELL"

        if potential_side is None:
            return None

        logger.event("TREND_SIGNAL_DETECTED",
                     side=potential_side,
                     price=current_price,
                     sma20=round(current_sma_fast, 2),
                     sma50=round(current_sma_slow, 2))

        if not self._check_momentum_confirmation(df, potential_side):
            logger.event("TREND_TRADE_REJECTED", reason="momentum")
            return None

        if not self._check_volume_filter(df):
            logger.event("TREND_TRADE_REJECTED", reason="volume")
            return None

        atr_config = self._check_atr_filter(atr_value)
        if atr_config is None:
            logger.event("TREND_TRADE_REJECTED", reason="atr")
            return None

        logger.event("TREND_TRADE_APPROVED",
                     side=potential_side, entry=current_price)

        entry = round(current_price, 2)
        sl_distance = atr_config["sl"]
        tp_distances = atr_config["tp_distances"]

        if potential_side == "BUY":
            sl = round(entry - sl_distance, 2)
            tps = self._calculate_tps("BUY", entry, tp_distances)
            return self._make_signal("BUY", entry, sl, tps, msg_id)
        else:
            sl = round(entry + sl_distance, 2)
            tps = self._calculate_tps("SELL", entry, tp_distances)
            return self._make_signal("SELL", entry, sl, tps, msg_id)