# market/strategies/trend.py
"""
Estrategia de Trend Following con pullbacks a SMA20.

Entrada: MARKET en toque de SMA20.
SL/TP: Fijos desde config (sl_distance, tp_distances).

OPTIMIZADO (backtest 6 meses):
- session_filter: EU+NY (08:00-22:00 UTC)

FASE 1 FILTROS (NUEVOS):
✅ Momentum confirmation: últimas 2 velas en dirección del trade
✅ Volume filter: volumen > 1.2x promedio de 20 velas
✅ ATR filter: skip si ATR < 8, ajustar si ATR > 25

Resultados esperados con filtros:
- Win rate: ~53-54% (antes: 51%)
- P&L: ~$1.10/trade (antes: $0.95)
"""
from __future__ import annotations

from typing import Optional
import logging

import pandas as pd

import config as CFG
from core.models import Signal
from market.indicators import sma, atr
from .base import BaseStrategy

logger = logging.getLogger(__name__)


class TrendStrategy(BaseStrategy):

    def __init__(
        self,
        symbol: str,
        magic: int,
        fast_period: int = 20,
        slow_period: int = 50,
        proximity_pips: float = 2.0,
        atr_period: int = 14,
        # NUEVOS PARÁMETROS - FASE 1
        enable_filters: bool = True,       # Activar filtros Fase 1
        momentum_periods: int = 2,         # Velas para momentum check
        volume_multiplier: float = 1.2,    # Multiplicador de volumen
        min_atr: float = 8.0,             # ATR mínimo para operar
        max_atr: float = 25.0,            # ATR máximo antes de ajustar
    ):
        super().__init__(symbol, magic)
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.proximity_pips = proximity_pips
        self.atr_period = atr_period
        
        # Fase 1 filters
        self.enable_filters = enable_filters
        self.momentum_periods = momentum_periods
        self.volume_multiplier = volume_multiplier
        self.min_atr = min_atr
        self.max_atr = max_atr

    @property
    def name(self) -> str:
        return "TREND"

    def _calculate_tps(self, side: str, entry: float, tp_distances: tuple = None) -> list:
        """TPs desde config o ajustados por ATR."""
        if tp_distances is None:
            tp_distances = tuple(getattr(CFG, "TP_DISTANCES", (5.0, 11.0, 16.0)))
        
        if side == "BUY":
            return [round(entry + d, 2) for d in tp_distances]
        else:
            return [round(entry - d, 2) for d in tp_distances]

    def _is_valid_session(self, ts: pd.Timestamp) -> bool:
        """Filtro de sesión: solo Europa + NY (08:00-22:00 UTC)."""
        session_filter = getattr(CFG, "SESSION_FILTER", "24h")
        
        if session_filter == "24h":
            return True
        
        hour_utc = ts.hour
        
        if session_filter == "eu_ny":
            return 8 <= hour_utc < 22
        
        if session_filter == "ny_only":
            return 13 <= hour_utc < 22
        
        return True

    # ========================================================================
    # FASE 1 FILTROS (COPIADOS DE REVERSAL)
    # ========================================================================
    
    def _check_momentum_confirmation(self, df: pd.DataFrame, side: str) -> bool:
        """Filtro 1: Confirmación de Momentum"""
        if not self.enable_filters:
            return True
        
        if len(df) < self.momentum_periods:
            return True
        
        last_candles = df.tail(self.momentum_periods)
        
        if side == 'BUY':
            bullish_count = (last_candles['close'] > last_candles['open']).sum()
            confirmed = bullish_count >= self.momentum_periods
            
            if not confirmed:
                logger.info(f"❌ Momentum filter: BUY rejected - "
                          f"solo {bullish_count}/{self.momentum_periods} velas alcistas")
            else:
                logger.info(f"✓ Momentum filter: BUY approved")
            
            return confirmed
        
        elif side == 'SELL':
            bearish_count = (last_candles['close'] < last_candles['open']).sum()
            confirmed = bearish_count >= self.momentum_periods
            
            if not confirmed:
                logger.info(f"❌ Momentum filter: SELL rejected - "
                          f"solo {bearish_count}/{self.momentum_periods} velas bajistas")
            else:
                logger.info(f"✓ Momentum filter: SELL approved")
            
            return confirmed
        
        return False

    def _check_volume_filter(self, df: pd.DataFrame, volume_periods: int = 20) -> bool:
        """Filtro 2: Volumen Relativo"""
        if not self.enable_filters:
            return True
        
        if len(df) < volume_periods:
            return True
        
        avg_volume = df['tick_volume'].tail(volume_periods).mean()
        current_volume = df['tick_volume'].iloc[-1]
        
        threshold = avg_volume * self.volume_multiplier
        
        if current_volume < threshold:
            logger.info(f"❌ Volume filter: rejected - {current_volume:.0f} < {threshold:.0f}")
            return False
        else:
            logger.info(f"✓ Volume filter: approved - {current_volume:.0f} > {threshold:.0f}")
            return True

    def _check_atr_filter(self, atr_value: float) -> Optional[dict]:
        """Filtro 3: Volatilidad ATR"""
        if not self.enable_filters:
            return {
                'sl': float(getattr(CFG, "SL_DISTANCE", 6.0)),
                'tp_distances': tuple(getattr(CFG, "TP_DISTANCES", (5.0, 11.0, 16.0)))
            }
        
        BASE_ATR = 15.0
        
        if atr_value < self.min_atr:
            logger.info(f"❌ ATR filter: rejected - ATR={atr_value:.1f} < {self.min_atr}")
            return None
        
        if atr_value > self.max_atr:
            multiplier = atr_value / BASE_ATR
            
            base_sl = float(getattr(CFG, "SL_DISTANCE", 6.0))
            base_tps = tuple(getattr(CFG, "TP_DISTANCES", (5.0, 11.0, 16.0)))
            
            adjusted = {
                'sl': base_sl * multiplier,
                'tp_distances': tuple(tp * multiplier for tp in base_tps)
            }
            
            logger.info(f"⚠ ATR filter: adjusted - ATR={atr_value:.1f} (multiplier={multiplier:.2f})")
            return adjusted
        
        logger.info(f"✓ ATR filter: normal - ATR={atr_value:.1f}")
        return {
            'sl': float(getattr(CFG, "SL_DISTANCE", 6.0)),
            'tp_distances': tuple(getattr(CFG, "TP_DISTANCES", (5.0, 11.0, 16.0)))
        }

    # ========================================================================
    # SCAN PRINCIPAL
    # ========================================================================

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

        msg_id = int(df.index[-1].timestamp())

        # ====================================================================
        # DETECTAR SIDE POTENCIAL
        # ====================================================================
        
        potential_side = None
        
        # UPTREND: BUY MARKET en toque de SMA20
        if current_sma_fast > current_sma_slow and current_price >= current_sma_fast:
            potential_side = "BUY"
        
        # DOWNTREND: SELL MARKET en toque de SMA20
        elif current_sma_fast < current_sma_slow and current_price <= current_sma_fast:
            potential_side = "SELL"
        
        if potential_side is None:
            return None
        
        # ====================================================================
        # APLICAR FILTROS FASE 1
        # ====================================================================
        
        logger.info(f"{'='*60}")
        logger.info(f"TREND SIGNAL DETECTED - Side: {potential_side}")
        logger.info(f"Price: {current_price} | SMA20: {current_sma_fast:.2f} | SMA50: {current_sma_slow:.2f}")
        logger.info(f"{'='*60}")
        
        # Filtro 1: Momentum
        if not self._check_momentum_confirmation(df, potential_side):
            logger.info("🚫 Trade RECHAZADO por filtro de Momentum")
            return None
        
        # Filtro 2: Volumen
        if not self._check_volume_filter(df):
            logger.info("🚫 Trade RECHAZADO por filtro de Volumen")
            return None
        
        # Filtro 3: ATR
        atr_config = self._check_atr_filter(atr_value)
        if atr_config is None:
            logger.info("🚫 Trade RECHAZADO por filtro de ATR")
            return None
        
        logger.info("✅ Trade APROBADO - Todos los filtros pasados")
        logger.info(f"{'='*60}")
        
        # ====================================================================
        # GENERAR SEÑAL
        # ====================================================================
        
        entry = round(current_price, 2)
        sl_distance = atr_config['sl']
        tp_distances = atr_config['tp_distances']
        
        if potential_side == "BUY":
            sl = round(entry - sl_distance, 2)
            tps = self._calculate_tps("BUY", entry, tp_distances)
            return self._make_signal("BUY", entry, sl, tps, msg_id)
        
        else:  # SELL
            sl = round(entry + sl_distance, 2)
            tps = self._calculate_tps("SELL", entry, tp_distances)
            return self._make_signal("SELL", entry, sl, tps, msg_id)