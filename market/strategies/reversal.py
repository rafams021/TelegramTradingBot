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

FASE 1 FILTROS (NUEVOS):
✅ Momentum confirmation: últimas 2 velas en dirección del trade
✅ Volume filter: volumen > 1.2x promedio de 20 velas
✅ ATR filter: skip si ATR < 8, ajustar si ATR > 25

Resultados esperados con filtros:
- Win rate: ~50-51% (antes: 47%)
- P&L: ~$0.70/trade (antes: $0.60)
- Menos falsos positivos
"""
from __future__ import annotations

from typing import Optional
import logging

import pandas as pd

import config as CFG
from core.models import Signal
from market.indicators import support_resistance_levels, rsi, atr
from .base import BaseStrategy

logger = logging.getLogger(__name__)


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
        # NUEVOS PARÁMETROS - FASE 1
        enable_filters: bool = True,       # Activar filtros Fase 1
        momentum_periods: int = 2,         # Velas para momentum check
        volume_multiplier: float = 1.2,    # Multiplicador de volumen
        min_atr: float = 8.0,             # ATR mínimo para operar
        max_atr: float = 25.0,            # ATR máximo antes de ajustar
    ):
        super().__init__(symbol, magic)
        self.lookback_candles = lookback_candles
        self.proximity_pips = proximity_pips
        self.atr_period = atr_period
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        
        # Fase 1 filters
        self.enable_filters = enable_filters
        self.momentum_periods = momentum_periods
        self.volume_multiplier = volume_multiplier
        self.min_atr = min_atr
        self.max_atr = max_atr

    @property
    def name(self) -> str:
        return "REVERSAL"

    def _calculate_tps(self, side: str, entry: float, tp_distances: tuple = None) -> list:
        """
        TPs desde config o ajustados por ATR.
        
        Args:
            side: BUY o SELL
            entry: Precio de entrada
            tp_distances: Tuple de distancias (tp1, tp2, tp3) o None para usar config
        """
        if tp_distances is None:
            tp_distances = tuple(getattr(CFG, "TP_DISTANCES", (5.0, 11.0, 16.0)))
        
        if side == "BUY":
            return [round(entry + d, 2) for d in tp_distances]
        else:
            return [round(entry - d, 2) for d in tp_distances]

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

    # ========================================================================
    # FASE 1 FILTROS
    # ========================================================================
    
    def _check_momentum_confirmation(self, df: pd.DataFrame, side: str) -> bool:
        """
        Filtro 1: Confirmación de Momentum
        
        Requiere que las últimas N velas vayan en dirección del trade.
        """
        if not self.enable_filters:
            return True
        
        if len(df) < self.momentum_periods:
            return True  # No rechazar si no hay data
        
        # Tomar las últimas N velas
        last_candles = df.tail(self.momentum_periods)
        
        if side == 'BUY':
            # Contar velas alcistas
            bullish_count = (last_candles['close'] > last_candles['open']).sum()
            confirmed = bullish_count >= self.momentum_periods
            
            if not confirmed:
                logger.info(f"❌ Momentum filter: BUY rejected - "
                          f"solo {bullish_count}/{self.momentum_periods} velas alcistas")
            else:
                logger.info(f"✓ Momentum filter: BUY approved - "
                          f"{bullish_count}/{self.momentum_periods} velas alcistas")
            
            return confirmed
        
        elif side == 'SELL':
            # Contar velas bajistas
            bearish_count = (last_candles['close'] < last_candles['open']).sum()
            confirmed = bearish_count >= self.momentum_periods
            
            if not confirmed:
                logger.info(f"❌ Momentum filter: SELL rejected - "
                          f"solo {bearish_count}/{self.momentum_periods} velas bajistas")
            else:
                logger.info(f"✓ Momentum filter: SELL approved - "
                          f"{bearish_count}/{self.momentum_periods} velas bajistas")
            
            return confirmed
        
        return False

    def _check_volume_filter(self, df: pd.DataFrame, volume_periods: int = 20) -> bool:
        """
        Filtro 2: Volumen Relativo
        
        Solo permite entrar si volumen actual > promedio * multiplier.
        """
        if not self.enable_filters:
            return True
        
        if len(df) < volume_periods:
            return True  # No rechazar si no hay data
        
        # Calcular volumen promedio
        avg_volume = df['tick_volume'].tail(volume_periods).mean()
        current_volume = df['tick_volume'].iloc[-1]
        
        threshold = avg_volume * self.volume_multiplier
        
        if current_volume < threshold:
            logger.info(f"❌ Volume filter: rejected - {current_volume:.0f} < {threshold:.0f} "
                       f"(avg={avg_volume:.0f} x {self.volume_multiplier})")
            return False
        else:
            logger.info(f"✓ Volume filter: approved - {current_volume:.0f} > {threshold:.0f}")
            return True

    def _check_atr_filter(self, atr_value: float) -> Optional[dict]:
        """
        Filtro 3: Volatilidad ATR
        
        Returns:
            None si debe skipear el trade
            dict con SL/TP ajustados si debe entrar
        """
        if not self.enable_filters:
            # Retornar config default
            return {
                'sl': float(getattr(CFG, "SL_DISTANCE", 6.0)),
                'tp_distances': tuple(getattr(CFG, "TP_DISTANCES", (5.0, 11.0, 16.0)))
            }
        
        BASE_ATR = 15.0  # ATR "normal" de XAUUSD
        
        # ATR muy bajo: Skip trade
        if atr_value < self.min_atr:
            logger.info(f"❌ ATR filter: rejected - ATR={atr_value:.1f} < {self.min_atr} "
                       "(volatilidad muy baja)")
            return None
        
        # ATR muy alto: Ajustar distancias proporcionalmente
        if atr_value > self.max_atr:
            multiplier = atr_value / BASE_ATR
            
            base_sl = float(getattr(CFG, "SL_DISTANCE", 6.0))
            base_tps = tuple(getattr(CFG, "TP_DISTANCES", (5.0, 11.0, 16.0)))
            
            adjusted = {
                'sl': base_sl * multiplier,
                'tp_distances': tuple(tp * multiplier for tp in base_tps)
            }
            
            logger.info(f"⚠ ATR filter: adjusted - ATR={atr_value:.1f} > {self.max_atr} "
                       f"(multiplier={multiplier:.2f})")
            logger.info(f"   SL=${adjusted['sl']:.1f} | "
                       f"TPs=${adjusted['tp_distances'][0]:.1f}/"
                       f"${adjusted['tp_distances'][1]:.1f}/"
                       f"${adjusted['tp_distances'][2]:.1f}")
            
            return adjusted
        
        # ATR normal: Usar valores fijos
        logger.info(f"✓ ATR filter: normal - ATR={atr_value:.1f} (usando SL/TP fijos)")
        return {
            'sl': float(getattr(CFG, "SL_DISTANCE", 6.0)),
            'tp_distances': tuple(getattr(CFG, "TP_DISTANCES", (5.0, 11.0, 16.0)))
        }

    # ========================================================================
    # SCAN PRINCIPAL
    # ========================================================================

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

        msg_id = int(df.index[-1].timestamp())

        closest_level = min(levels, key=lambda l: abs(l - current_price))
        if abs(current_price - closest_level) > self.proximity_pips:
            return None

        # ====================================================================
        # DETECTAR SIDE POTENCIAL
        # ====================================================================
        
        potential_side = None
        
        # BUY MARKET: en soporte + sobreventa
        if current_price <= closest_level and current_rsi < self.rsi_oversold:
            potential_side = "BUY"
        
        # SELL MARKET: en resistencia + sobrecompra
        elif current_price >= closest_level and current_rsi > self.rsi_overbought:
            potential_side = "SELL"
        
        if potential_side is None:
            return None
        
        # ====================================================================
        # APLICAR FILTROS FASE 1
        # ====================================================================
        
        logger.info(f"{'='*60}")
        logger.info(f"REVERSAL SIGNAL DETECTED - Side: {potential_side}")
        logger.info(f"Price: {current_price} | Level: {closest_level} | RSI: {current_rsi:.1f}")
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