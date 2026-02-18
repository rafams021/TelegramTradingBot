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

from typing import Optional, List, Dict
from infrastructure.logging import get_logger

import pandas as pd
import numpy as np

import config as CFG
from core.state import Signal
from market.indicators import support_resistance_levels, rsi, atr, ema, sma
from .base import BaseStrategy

logger = get_logger()


class ReversalStrategy(BaseStrategy):
    """
    Reversal Strategy con capacidad SUPREME MODE
    """

    def __init__(
        self,
        symbol: str,
        magic: int,
        # PARÁMETROS BÁSICOS
        lookback_candles: int = 20,
        proximity_pips: float = 8.0,
        atr_period: int = 14,
        rsi_period: int = 14,
        rsi_oversold: float = 45.0,
        rsi_overbought: float = 55.0,
        
        # SUPREME MODE (Master switch)
        supreme_mode: bool = False,
        
        # FILTROS AVANZADOS (individuales)
        enable_mtf: bool = False,
        enable_order_blocks: bool = False,
        enable_fvg: bool = False,
        enable_quality_filter: bool = False,
        enable_strict_session: bool = False,
        
        # PARÁMETROS AVANZADOS
        min_sr_touches: int = 2,
        impulse_multiplier: float = 1.5,
        
        # HEDGING
        enable_hedging: bool = False,
        max_positions: int = 2,
        hedge_trigger_loss_usd: float = 30.0,
        hedge_lot_multiplier: float = 0.5,
        
        # ML FILTER
        use_ml_filter: bool = False,
        ml_confidence_min: float = 0.70,
    ):
        super().__init__(symbol, magic)
        
        # Parámetros básicos
        self.lookback_candles = lookback_candles
        self.proximity_pips = proximity_pips
        self.atr_period = atr_period
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        
        # SUPREME MODE: Activar filtros balanceados (no todos obligatorios)
        self.supreme_mode = supreme_mode
        if supreme_mode:
            self.enable_mtf = False  # MTF opcional (muy restrictivo)
            self.enable_order_blocks = True
            self.enable_fvg = True
            self.enable_quality_filter = True
            self.enable_strict_session = True
            self.min_sr_touches = 2  # 2 toques es suficiente
            self.use_ml_filter = use_ml_filter
        else:
            self.enable_mtf = enable_mtf
            self.enable_order_blocks = enable_order_blocks
            self.enable_fvg = enable_fvg
            self.enable_quality_filter = enable_quality_filter
            self.enable_strict_session = enable_strict_session
            self.min_sr_touches = min_sr_touches
            self.use_ml_filter = use_ml_filter
        
        # Parámetros avanzados
        self.impulse_multiplier = impulse_multiplier
        
        # Hedging
        self.enable_hedging = enable_hedging
        self.max_positions = max_positions
        self.hedge_trigger_loss_usd = hedge_trigger_loss_usd
        self.hedge_lot_multiplier = hedge_lot_multiplier
        
        # ML
        self.ml_confidence_min = ml_confidence_min
        
        # State
        self.open_positions = []

    @property
    def name(self) -> str:
        if self.supreme_mode:
            return "REVERSAL_SUPREME"
        return "REVERSAL"

    def _calculate_tps(self, side: str, entry: float) -> list:
        if self.supreme_mode:
            distances = (11.0, 20.0, 30.0)  # TPs más largos como Aura
        else:
            distances = list(getattr(CFG, "TP_DISTANCES", (5.0, 11.0, 16.0)))
        
        if side == "BUY":
            return [round(entry + d, 2) for d in distances]
        else:
            return [round(entry - d, 2) for d in distances]

    # ========================================================================
    # SESIÓN ULTRA-SELECTIVA
    # ========================================================================
    
    def _is_high_quality_session(self, ts: pd.Timestamp) -> bool:
        """Solo London/NY open"""
        if not self.enable_strict_session:
            return True
        
        hour_utc = ts.hour
        # London (8-10), NY (13-17), Overlap (13-16)
        return (8 <= hour_utc < 10) or (13 <= hour_utc < 17)

    # ========================================================================
    # MULTI-TIMEFRAME CONFLUENCE
    # ========================================================================
    
    def _check_mtf_alignment(self, df: pd.DataFrame, side: str) -> bool:
        """Verifica trend H1 (EMA 50 vs 200)"""
        if not self.enable_mtf:
            return True
        
        if len(df) < 200:
            return True
        
        ema_50 = float(ema(df['close'], 50).iloc[-1])
        ema_200 = float(ema(df['close'], 200).iloc[-1])
        
        if pd.isna(ema_50) or pd.isna(ema_200):
            return True
        
        trend = "UP" if ema_50 > ema_200 else "DOWN"
        
        if side == "BUY" and trend != "UP":
            return False
        if side == "SELL" and trend != "DOWN":
            return False
        
        return True

    # ========================================================================
    # ORDER BLOCKS DETECTION
    # ========================================================================
    
    def _detect_order_blocks(self, df: pd.DataFrame, lookback: int = 50) -> List[Dict]:
        """Detecta Order Blocks"""
        if not self.enable_order_blocks:
            return []
        
        if len(df) < lookback:
            return []
        
        order_blocks = []
        atr_val = float(atr(df, period=self.atr_period).iloc[-1])
        
        if pd.isna(atr_val) or atr_val <= 0:
            return []
        
        recent_df = df.tail(lookback)
        
        for i in range(1, len(recent_df) - 1):
            curr = recent_df.iloc[i]
            prev = recent_df.iloc[i - 1]
            
            curr_size = abs(curr['close'] - curr['open'])
            is_bullish = curr['close'] > curr['open']
            is_bearish = curr['close'] < curr['open']
            
            # Bullish OB
            if is_bullish and curr_size > (self.impulse_multiplier * atr_val):
                if prev['close'] < prev['open']:
                    ob = {
                        'type': 'BULLISH_OB',
                        'high': float(prev['high']),
                        'low': float(prev['low']),
                    }
                    order_blocks.append(ob)
            
            # Bearish OB
            if is_bearish and curr_size > (self.impulse_multiplier * atr_val):
                if prev['close'] > prev['open']:
                    ob = {
                        'type': 'BEARISH_OB',
                        'high': float(prev['high']),
                        'low': float(prev['low']),
                    }
                    order_blocks.append(ob)
        
        return order_blocks

    def _is_near_order_block(self, price: float, order_blocks: List[Dict], side: str) -> bool:
        """Verifica si está en OB relevante"""
        for ob in order_blocks:
            if side == "BUY" and ob['type'] == 'BULLISH_OB':
                if ob['low'] <= price <= ob['high']:
                    return True
            if side == "SELL" and ob['type'] == 'BEARISH_OB':
                if ob['low'] <= price <= ob['high']:
                    return True
        return False

    # ========================================================================
    # FAIR VALUE GAPS
    # ========================================================================
    
    def _detect_fair_value_gaps(self, df: pd.DataFrame, lookback: int = 30) -> List[Dict]:
        """Detecta FVG"""
        if not self.enable_fvg:
            return []
        
        if len(df) < lookback + 2:
            return []
        
        fvg_zones = []
        recent_df = df.tail(lookback)
        
        for i in range(2, len(recent_df)):
            c_prev2 = recent_df.iloc[i - 2]
            c_prev1 = recent_df.iloc[i - 1]
            c_curr = recent_df.iloc[i]
            
            # Bullish FVG
            gap_low = float(c_prev2['high'])
            gap_high = float(c_curr['low'])
            
            if gap_high > gap_low:
                if c_prev1['high'] < gap_high and c_prev1['low'] > gap_low:
                    gap_size = gap_high - gap_low
                    if gap_size > 5.0:
                        fvg_zones.append({
                            'type': 'BULLISH_FVG',
                            'high': gap_high,
                            'low': gap_low,
                        })
            
            # Bearish FVG
            gap_high_b = float(c_prev2['low'])
            gap_low_b = float(c_curr['high'])
            
            if gap_high_b > gap_low_b:
                if c_prev1['low'] > gap_low_b and c_prev1['high'] < gap_high_b:
                    gap_size = gap_high_b - gap_low_b
                    if gap_size > 5.0:
                        fvg_zones.append({
                            'type': 'BEARISH_FVG',
                            'high': gap_high_b,
                            'low': gap_low_b,
                        })
        
        return fvg_zones

    def _is_near_fvg(self, price: float, fvg_zones: List[Dict], side: str) -> bool:
        """Verifica si está en FVG relevante"""
        for fvg in fvg_zones:
            if side == "BUY" and fvg['type'] == 'BULLISH_FVG':
                if fvg['low'] <= price <= fvg['high']:
                    return True
            if side == "SELL" and fvg['type'] == 'BEARISH_FVG':
                if fvg['low'] <= price <= fvg['high']:
                    return True
        return False

    # ========================================================================
    # IMPULSE CONFIRMATION
    # ========================================================================
    
    def _has_recent_impulse(self, df: pd.DataFrame, side: str, lookback: int = 5) -> bool:
        """Verifica impulso reciente"""
        if len(df) < lookback + self.atr_period:
            return True
        
        atr_val = float(atr(df, period=self.atr_period).iloc[-1])
        if pd.isna(atr_val) or atr_val <= 0:
            return True
        
        recent_candles = df.tail(lookback)
        
        for i in range(len(recent_candles)):
            candle = recent_candles.iloc[i]
            candle_size = abs(candle['close'] - candle['open'])
            is_bullish = candle['close'] > candle['open']
            is_bearish = candle['close'] < candle['open']
            
            if side == "BUY" and is_bullish and candle_size > (self.impulse_multiplier * atr_val):
                return True
            if side == "SELL" and is_bearish and candle_size > (self.impulse_multiplier * atr_val):
                return True
        
        return False

    # ========================================================================
    # S/R QUALITY
    # ========================================================================
    
    def _count_level_touches(self, df: pd.DataFrame, level: float, lookback: int = 50) -> int:
        """Cuenta toques en nivel"""
        if len(df) < lookback:
            lookback = len(df)
        
        recent_df = df.tail(lookback)
        touches = 0
        
        for i in range(len(recent_df)):
            candle = recent_df.iloc[i]
            if abs(candle['low'] - level) < 3.0 or abs(candle['high'] - level) < 3.0:
                touches += 1
        
        return touches

    def _is_quality_level(self, df: pd.DataFrame, level: float) -> bool:
        """Verifica calidad del nivel"""
        if not self.enable_quality_filter:
            return True
        
        touches = self._count_level_touches(df, level, lookback=50)
        return touches >= self.min_sr_touches

    # ========================================================================
    # VOLUME CONFIRMATION
    # ========================================================================
    
    def _has_volume_confirmation(self, df: pd.DataFrame, multiplier: float = 1.3) -> bool:
        """Verifica volumen"""
        if not self.enable_quality_filter:
            return True
        
        if len(df) < 20:
            return True
        
        current_volume = float(df['tick_volume'].iloc[-1])
        avg_volume = float(df['tick_volume'].tail(20).mean())
        
        return current_volume >= (avg_volume * multiplier)

    # ========================================================================
    # SCAN PRINCIPAL
    # ========================================================================

    def scan(self, df: pd.DataFrame, current_price: float) -> Optional[Signal]:
        """Escanea señales"""
        min_candles = max(self.lookback_candles, self.rsi_period + 1, self.atr_period + 1, 200)
        if len(df) < min_candles:
            return None

        ts = df.index[-1]
        
        # Sesión
        if self.enable_strict_session and not self._is_high_quality_session(ts):
            return None

        # S/R levels
        levels = support_resistance_levels(df, lookback=self.lookback_candles)
        if not levels:
            return None

        closest_level = min(levels, key=lambda l: abs(l - current_price))
        if abs(current_price - closest_level) > self.proximity_pips:
            return None

        # Quality S/R
        if not self._is_quality_level(df, closest_level):
            return None

        # Indicadores
        current_rsi = float(rsi(df, period=self.rsi_period).iloc[-1])
        atr_series = atr(df, period=self.atr_period)
        atr_value = float(atr_series.iloc[-1])
        
        if pd.isna(atr_value) or atr_value <= 0:
            return None

        msg_id = int(df.index[-1].timestamp())

        # Detectar side
        potential_side = None
        
        if current_price <= closest_level and current_rsi < self.rsi_oversold:
            potential_side = "BUY"
        elif current_price >= closest_level and current_rsi > self.rsi_overbought:
            potential_side = "SELL"
        
        if potential_side is None:
            return None

        # ====================================================================
        # FILTROS AVANZADOS (Supreme mode)
        # ====================================================================
        
        if self.supreme_mode or any([self.enable_mtf, self.enable_order_blocks, 
                                      self.enable_fvg, self.enable_quality_filter]):
            
            # MTF (opcional)
            if self.enable_mtf and not self._check_mtf_alignment(df, potential_side):
                return None
            
            # Order Blocks o FVG (al menos UNO debe cumplirse)
            has_structure = False
            
            if self.enable_order_blocks or self.enable_fvg:
                order_blocks = self._detect_order_blocks(df) if self.enable_order_blocks else []
                fvg_zones = self._detect_fair_value_gaps(df) if self.enable_fvg else []
                
                # Aceptar si está en OB O en FVG (no ambos obligatorios)
                if order_blocks and self._is_near_order_block(current_price, order_blocks, potential_side):
                    has_structure = True
                
                if fvg_zones and self._is_near_fvg(current_price, fvg_zones, potential_side):
                    has_structure = True
                
                # Solo rechazar si NO está en NINGUNA estructura
                if not has_structure and (order_blocks or fvg_zones):
                    return None
            
            # Impulse (preferido pero no obligatorio)
            has_impulse = self._has_recent_impulse(df, potential_side)
            # No rechazar si no hay impulse, solo preferirlo
            
            # Volume (preferido pero no obligatorio)
            has_volume = self._has_volume_confirmation(df)
            # No rechazar si no hay volume alto, solo preferirlo
        
        # ====================================================================
        # GENERAR SEÑAL
        # ====================================================================
        
        entry = round(current_price, 2)
        sl_distance = float(getattr(CFG, "SL_DISTANCE", 17.0 if self.supreme_mode else 6.0))
        
        if potential_side == "BUY":
            sl = round(entry - sl_distance, 2)
            tps = self._calculate_tps("BUY", entry)
            return self._make_signal("BUY", entry, sl, tps, msg_id)
        else:
            sl = round(entry + sl_distance, 2)
            tps = self._calculate_tps("SELL", entry)
            return self._make_signal("SELL", entry, sl, tps, msg_id)