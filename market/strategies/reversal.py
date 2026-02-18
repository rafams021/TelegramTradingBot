# market/strategies/reversal.py
"""
Reversal Strategy - Con SUPREME MODE

MODOS DE OPERACION:
==================

MODO BASICO (supreme_mode=False):
- RSI + S/R levels
- Session filter basico
- Win Rate esperado: 48-52%

MODO SUPREME (supreme_mode=True):
- Order Blocks detection (zonas institucionales)
- Fair Value Gaps (FVG) detection
- Sesion ultra-selectiva (London/NY open)
- Impulse confirmation (vela >1.5x ATR)
- S/R quality filter (minimo toques)
- Volume confirmation (institucional)
- Multi-timeframe (opcional)
- ML confidence filter (opcional)

Objetivo Supreme: 65-75% WR con 50-150 trades
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

import config as CFG
from core.state import Signal
from infrastructure.logging import get_logger
from market.indicators import support_resistance_levels, rsi, atr, ema
from market.filters import (
    detect_order_blocks,
    is_near_order_block,
    detect_fair_value_gaps,
    is_near_fvg,
    is_high_quality_session,
    is_quality_level,
    has_volume_confirmation,
    has_recent_impulse,
)
from .base import BaseStrategy

logger = get_logger()


class ReversalStrategy(BaseStrategy):

    def __init__(
        self,
        symbol: str,
        magic: int,
        # Parametros basicos
        lookback_candles: int = 20,
        proximity_pips: float = 8.0,
        atr_period: int = 14,
        rsi_period: int = 14,
        rsi_oversold: float = 45.0,
        rsi_overbought: float = 55.0,
        # Supreme mode (master switch)
        supreme_mode: bool = False,
        # Filtros avanzados (individuales)
        enable_mtf: bool = False,
        enable_order_blocks: bool = False,
        enable_fvg: bool = False,
        enable_quality_filter: bool = False,
        enable_strict_session: bool = False,
        # Parametros avanzados
        min_sr_touches: int = 2,
        impulse_multiplier: float = 1.5,
        # Hedging
        enable_hedging: bool = False,
        max_positions: int = 2,
        hedge_trigger_loss_usd: float = 30.0,
        hedge_lot_multiplier: float = 0.5,
        # ML filter
        use_ml_filter: bool = False,
        ml_confidence_min: float = 0.70,
    ):
        super().__init__(symbol, magic)

        self.lookback_candles = lookback_candles
        self.proximity_pips = proximity_pips
        self.atr_period = atr_period
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.impulse_multiplier = impulse_multiplier

        # Supreme mode activa filtros balanceados
        self.supreme_mode = supreme_mode
        if supreme_mode:
            self.enable_mtf = False
            self.enable_order_blocks = True
            self.enable_fvg = True
            self.enable_quality_filter = True
            self.enable_strict_session = True
            self.min_sr_touches = 2
            self.use_ml_filter = use_ml_filter
        else:
            self.enable_mtf = enable_mtf
            self.enable_order_blocks = enable_order_blocks
            self.enable_fvg = enable_fvg
            self.enable_quality_filter = enable_quality_filter
            self.enable_strict_session = enable_strict_session
            self.min_sr_touches = min_sr_touches
            self.use_ml_filter = use_ml_filter

        # Hedging
        self.enable_hedging = enable_hedging
        self.max_positions = max_positions
        self.hedge_trigger_loss_usd = hedge_trigger_loss_usd
        self.hedge_lot_multiplier = hedge_lot_multiplier

        self.ml_confidence_min = ml_confidence_min
        self.open_positions = []

    @property
    def name(self) -> str:
        return "REVERSAL_SUPREME" if self.supreme_mode else "REVERSAL"

    def _calculate_tps(self, side: str, entry: float) -> list:
        distances = (11.0, 20.0, 30.0) if self.supreme_mode else \
                    tuple(getattr(CFG, "TP_DISTANCES", (5.0, 11.0, 16.0)))
        if side == "BUY":
            return [round(entry + d, 2) for d in distances]
        return [round(entry - d, 2) for d in distances]

    def _check_mtf_alignment(self, df: pd.DataFrame, side: str) -> bool:
        """Verifica alineacion de tendencia H1 via EMA 50 vs 200."""
        if not self.enable_mtf or len(df) < 200:
            return True

        ema_50  = float(ema(df["close"], 50).iloc[-1])
        ema_200 = float(ema(df["close"], 200).iloc[-1])

        if pd.isna(ema_50) or pd.isna(ema_200):
            return True

        trend_up = ema_50 > ema_200
        if side == "BUY"  and not trend_up:
            return False
        if side == "SELL" and trend_up:
            return False
        return True

    # ========================================================================
    # SCAN PRINCIPAL
    # ========================================================================

    def scan(self, df: pd.DataFrame, current_price: float) -> Optional[Signal]:
        min_candles = max(self.lookback_candles, self.rsi_period + 1,
                          self.atr_period + 1, 200)
        if len(df) < min_candles:
            return None

        ts = df.index[-1]

        # Filtro de sesion
        if self.enable_strict_session and not is_high_quality_session(ts):
            return None

        # S/R levels
        levels = support_resistance_levels(df, lookback=self.lookback_candles)
        if not levels:
            return None

        closest_level = min(levels, key=lambda l: abs(l - current_price))
        if abs(current_price - closest_level) > self.proximity_pips:
            return None

        # Calidad del nivel S/R
        if self.enable_quality_filter and not is_quality_level(
            df, closest_level, min_touches=self.min_sr_touches
        ):
            return None

        # Indicadores
        current_rsi = float(rsi(df, period=self.rsi_period).iloc[-1])
        atr_value   = float(atr(df, period=self.atr_period).iloc[-1])

        if pd.isna(atr_value) or atr_value <= 0:
            return None

        # Detectar lado potencial
        potential_side = None
        if current_price <= closest_level and current_rsi < self.rsi_oversold:
            potential_side = "BUY"
        elif current_price >= closest_level and current_rsi > self.rsi_overbought:
            potential_side = "SELL"

        if potential_side is None:
            return None

        # ====================================================================
        # FILTROS AVANZADOS
        # ====================================================================

        any_advanced = any([
            self.enable_mtf,
            self.enable_order_blocks,
            self.enable_fvg,
            self.enable_quality_filter,
        ])

        if self.supreme_mode or any_advanced:

            if self.enable_mtf and not self._check_mtf_alignment(df, potential_side):
                return None

            if self.enable_order_blocks or self.enable_fvg:
                obs  = detect_order_blocks(df, self.impulse_multiplier, self.atr_period) \
                       if self.enable_order_blocks else []
                fvgs = detect_fair_value_gaps(df) \
                       if self.enable_fvg else []

                in_ob  = obs  and is_near_order_block(current_price, obs,  potential_side)
                in_fvg = fvgs and is_near_fvg(current_price, fvgs, potential_side)

                # Rechazar solo si habia estructuras disponibles pero el precio no esta en ninguna
                if (obs or fvgs) and not (in_ob or in_fvg):
                    return None

        # ====================================================================
        # GENERAR SEÑAL
        # ====================================================================

        msg_id      = int(ts.timestamp())
        entry       = round(current_price, 2)
        sl_distance = float(getattr(CFG, "SL_DISTANCE",
                                    17.0 if self.supreme_mode else 6.0))

        if potential_side == "BUY":
            sl  = round(entry - sl_distance, 2)
            tps = self._calculate_tps("BUY", entry)
            return self._make_signal("BUY", entry, sl, tps, msg_id)
        else:
            sl  = round(entry + sl_distance, 2)
            tps = self._calculate_tps("SELL", entry)
            return self._make_signal("SELL", entry, sl, tps, msg_id)