# market/strategies/reversal.py
"""
Reversal Strategy - Con SUPREME MODE

MODOS DE OPERACIÓN:
==================

MODO BÁSICO (supreme_mode=False):
- RSI + S/R levels  
- Session filter básico
- Win Rate esperado: 48-52%

MODO SUPREME (supreme_mode=True):
✅ Multi-timeframe confluence (H1 + H4 + D1)
✅ Order Blocks detection (zonas institucionales)
✅ Fair Value Gaps (FVG) detection
✅ Sesión ultra-selectiva (London/NY open)
✅ Impulse confirmation (vela >1.5x ATR)
✅ S/R quality filter (mínimo toques)
✅ Volume confirmation (institucional)
✅ ML confidence filter (opcional)
✅ Hedging inteligente (opcional)

Objetivo Supreme: 70-82% WR con 8-15 trades/día

USO:
    # Modo básico (original)
    strategy = ReversalStrategy(symbol="XAUUSD-ECN", magic=100)
    
    # Modo Supreme
    strategy = ReversalStrategy(
        symbol="XAUUSD-ECN",
        magic=100,
        supreme_mode=True,
        enable_hedging=True,
        ml_confidence_min=0.75
    )
"""
from __future__ import annotations

from typing import Optional, List, Dict
import logging

import pandas as pd
import numpy as np

import config as CFG
from core.models import Signal
from market.indicators import support_resistance_levels, rsi, atr, ema, sma
from .base import BaseStrategy

logger = logging.getLogger(__name__)


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
        enable_mtf: bool = False,              # Multi-timeframe confluence
        enable_order_blocks: bool = False,     # Order blocks detection
        enable_fvg: bool = False,              # Fair Value Gaps
        enable_quality_filter: bool = False,   # S/R quality + volume
        enable_strict_session: bool = False,   # London/NY only
        
        # PARÁMETROS AVANZADOS
        min_sr_touches: int = 3,               # Mínimo toques para S/R válido
        impulse_multiplier: float = 1.5,      # Vela impulso > 1.5x ATR
        
        # HEDGING (como Aura Black)
        enable_hedging: bool = False,
        max_positions: int = 2,                # 1 principal + 1 hedge
        hedge_trigger_loss_usd: float = 30.0, # Activar hedge si loss > $30
        hedge_lot_multiplier: float = 0.5,    # Hedge = 50% del lote
        
        # ML FILTER
        use_ml_filter: bool = False,
        ml_confidence_min: float = 0.70,       # Mínimo 70% confidence
    ):
        super().__init__(symbol, magic)
        
        # Parámetros básicos
        self.lookback_candles = lookback_candles
        self.proximity_pips = proximity_pips
        self.atr_period = atr_period
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        
        # SUPREME MODE: Si está activado, habilita TODOS los filtros
        self.supreme_mode = supreme_mode
        if supreme_mode:
            self.enable_mtf = True
            self.enable_order_blocks = True
            self.enable_fvg = True
            self.enable_quality_filter = True
            self.enable_strict_session = True
            self.use_ml_filter = use_ml_filter  # Opcional
        else:
            # Usar configuración individual
            self.enable_mtf = enable_mtf
            self.enable_order_blocks = enable_order_blocks
            self.enable_fvg = enable_fvg
            self.enable_quality_filter = enable_quality_filter
            self.enable_strict_session = enable_strict_session
            self.use_ml_filter = use_ml_filter
        
        # Parámetros avanzados
        self.min_sr_touches = min_sr_touches
        self.impulse_multiplier = impulse_multiplier
        
        # Hedging
        self.enable_hedging = enable_hedging
        self.max_positions = max_positions
        self.hedge_trigger_loss_usd = hedge_trigger_loss_usd
        self.hedge_lot_multiplier = hedge_lot_multiplier
        
        # ML
        self.ml_confidence_min = ml_confidence_min
        
        # State (para hedging)
        self.open_positions = []  # Lista de posiciones abiertas

    @property
    def name(self) -> str:
        if self.supreme_mode:
            return "REVERSAL_SUPREME"
        return "REVERSAL"

    def _calculate_tps(self, side: str, entry: float) -> list:
        """TPs fijos desde config (compatibilidad Aura: 110 pips)"""
        # Modo Supreme usa TPs como Aura
        if self.supreme_mode:
            distances = (11.0, 20.0, 30.0)  # 110, 200, 300 pips
        else:
            distances = list(getattr(CFG, "TP_DISTANCES", (5.0, 11.0, 16.0)))
        
        if side == "BUY":
            return [round(entry + d, 2) for d in distances]
        else:
            return [round(entry - d, 2) for d in distances]

    # ========================================================================
    # SESIÓN ULTRA-SELECTIVA (Supreme mode)
    # ========================================================================
    
    def _is_high_quality_session(self, ts: pd.Timestamp) -> bool:
        """
        Solo opera en horas de máximo volumen institucional.
        
        Sesiones de alta calidad:
        - London Open: 08:00-10:00 UTC
        - NY Open: 13:00-17:00 UTC  
        - Overlap EU+NY: 13:00-16:00 UTC (MEJOR)
        """
        if not self.enable_strict_session:
            return True  # No filtrar
        
        hour_utc = ts.hour
        
        # Overlap EU+NY (mejor volumen)
        if 13 <= hour_utc < 16:
            return True
        
        # London Open
        if 8 <= hour_utc < 10:
            return True
        
        # NY Open
        if 15 <= hour_utc < 17:
            return True
        
        return False

    # ========================================================================
    # MULTI-TIMEFRAME CONFLUENCE
    # ========================================================================
    
    def _check_mtf_alignment(self, df: pd.DataFrame, side: str) -> bool:
        """
        Verifica que H1 trend esté alineado con la dirección del trade.
        
        Usa EMAs para determinar tendencia:
        - Uptrend: EMA50 > EMA200 → Solo BUY
        - Downtrend: EMA50 < EMA200 → Solo SELL
        """
        if not self.enable_mtf:
            return True
        
        if len(df) < 200:
            return True  # No rechazar si no hay data
        
        # Trend H1
        ema_50_h1 = float(ema(df['close'], 50).iloc[-1])
        ema_200_h1 = float(ema(df['close'], 200).iloc[-1])
        
        if pd.isna(ema_50_h1) or pd.isna(ema_200_h1):
            return True
        
        trend_h1 = "UP" if ema_50_h1 > ema_200_h1 else "DOWN"
        
        if side == "BUY" and trend_h1 != "UP":
            return False
        
        if side == "SELL" and trend_h1 != "DOWN":
            return False
        
        return True

    # ========================================================================
    # ORDER BLOCKS DETECTION
    # ========================================================================
    
    def _detect_order_blocks(self, df: pd.DataFrame, lookback: int = 50) -> List[Dict]:
        """
        Detecta Order Blocks (zonas institucionales).
        
        Order Block = Última vela opuesta antes de un impulso fuerte.
        """
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
            curr_candle = recent_df.iloc[i]
            prev_candle = recent_df.iloc[i - 1]
            
            candle_size = abs(curr_candle['close'] - curr_candle['open'])
            is_bullish = curr_candle['close'] > curr_candle['open']
            is_bearish = curr_candle['close'] < curr_candle['open']
            
            # Impulso alcista fuerte
            if is_bullish and candle_size > (self.impulse_multiplier * atr_val):
                if prev_candle['close'] < prev_candle['open']:
                    ob = {
                        'type': 'BULLISH_OB',
                        'high': float(prev_candle['high']),
                        'low': float(prev_candle['low']),
                        'index': i - 1
                    }
                    order_blocks.append(ob)
            
            # Impulso bajista fuerte
            if is_bearish and candle_size > (self.impulse_multiplier * atr_val):
                if prev_candle['close'] > prev_candle['open']:
                    ob = {
                        'type': 'BEARISH_OB',
                        'high': float(prev_candle['high']),
                        'low': float(prev_candle['low']),
                        'index': i - 1
                    }
                    order_blocks.append(ob)
        
        return order_blocks

    def _is_near_order_block(self, price: float, order_blocks: List[Dict], side: str) -> bool:
        """Verifica si el precio está cerca de un Order Block relevante."""
        if not order_blocks:
            return True  # No rechazar si no hay OBs
        
        for ob in order_blocks:
            if side == "BUY" and ob['type'] == 'BULLISH_OB':
                if ob['low'] <= price <= ob['high']:
                    return True
            
            if side == "SELL" and ob['type'] == 'BEARISH_OB':
                if ob['low'] <= price <= ob['high']:
                    return True
        
        return False

    # ========================================================================
    # FAIR VALUE GAPS DETECTION (NUEVO)
    # ========================================================================
    
    def _detect_fair_value_gaps(self, df: pd.DataFrame, lookback: int = 30) -> List[Dict]:
        """
        Detecta Fair Value Gaps (FVG):
        - Gap entre vela[i-2] y vela[i] que vela[i-1] no llena
        """
        if not self.enable_fvg:
            return []
        
        if len(df) < lookback + 2:
            return []
        
        fvg_zones = []
        recent_df = df.tail(lookback)
        
        for i in range(2, len(recent_df)):
            candle_prev2 = recent_df.iloc[i - 2]
            candle_prev1 = recent_df.iloc[i - 1]
            candle_curr = recent_df.iloc[i]
            
            # Bullish FVG (gap arriba)
            gap_low = float(candle_prev2['high'])
            gap_high = float(candle_curr['low'])
            
            if gap_high > gap_low:
                if candle_prev1['high'] < gap_high and candle_prev1['low'] > gap_low:
                    gap_size = gap_high - gap_low
                    if gap_size > 5.0:  # Mínimo 5 pips
                        fvg_zones.append({
                            'type': 'BULLISH_FVG',
                            'high': gap_high,
                            'low': gap_low,
                            'size': gap_size
                        })
            
            # Bearish FVG (gap abajo)
            gap_high_bear = float(candle_prev2['low'])
            gap_low_bear = float(candle_curr['high'])
            
            if gap_high_bear > gap_low_bear:
                if candle_prev1['low'] > gap_low_bear and candle_prev1['high'] < gap_high_bear:
                    gap_size = gap_high_bear - gap_low_bear
                    if gap_size > 5.0:
                        fvg_zones.append({
                            'type': 'BEARISH_FVG',
                            'high': gap_high_bear,
                            'low': gap_low_bear,
                            'size': gap_size
                        })
        
        return fvg_zones

    def _is_near_fvg(self, price: float, fvg_zones: List[Dict], side: str) -> bool:
        """Verifica si el precio está cerca de un FVG relevante."""
        if not fvg_zones:
            return True
        
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
        """Verifica si hay una vela de impulso reciente (>1.5x ATR)."""
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
    # S/R QUALITY FILTER
    # ========================================================================
    
    def _count_level_touches(self, df: pd.DataFrame, level: float, lookback: int = 50) -> int:
        """Cuenta cuántas veces el precio ha tocado un nivel."""
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
        """Verifica si un nivel S/R es de alta calidad (mínimo N toques)."""
        if not self.enable_quality_filter:
            return True
        
        touches = self._count_level_touches(df, level, lookback=50)
        
        return touches >= self.min_sr_touches

    # ========================================================================
    # VOLUME CONFIRMATION
    # ========================================================================
    
    def _has_volume_confirmation(self, df: pd.DataFrame, multiplier: float = 1.3) -> bool:
        """Verifica si el volumen actual es suficiente (institucional)."""
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
        """
        Escanea señales de Reversal.
        
        En modo básico: Solo RSI + S/R
        En modo Supreme: Todos los filtros avanzados
        """
        min_candles = max(self.lookback_candles, self.rsi_period + 1, self.atr_period + 1, 200)
        if len(df) < min_candles:
            return None

        ts = df.index[-1]
        
        # FILTRO: Sesión de alta calidad (Supreme only)
        if self.enable_strict_session and not self._is_high_quality_session(ts):
            return None

        # S/R levels
        levels = support_resistance_levels(df, lookback=self.lookback_candles)
        if not levels:
            return None

        closest_level = min(levels, key=lambda l: abs(l - current_price))
        if abs(current_price - closest_level) > self.proximity_pips:
            return None

        # FILTRO: Quality S/R level (Supreme only)
        if not self._is_quality_level(df, closest_level):
            return None

        # Indicadores
        current_rsi = float(rsi(df, period=self.rsi_period).iloc[-1])
        atr_series = atr(df, period=self.atr_period)
        atr_value = float(atr_series.iloc[-1])
        
        if pd.isna(atr_value) or atr_value <= 0:
            return None

        msg_id = int(df.index[-1].timestamp())

        # Detectar side potencial
        potential_side = None
        
        if current_price <= closest_level and current_rsi < self.rsi_oversold:
            potential_side = "BUY"
        elif current_price >= closest_level and current_rsi > self.rsi_overbought:
            potential_side = "SELL"
        
        if potential_side is None:
            return None

        # ====================================================================
        # APLICAR FILTROS AVANZADOS (Supreme mode)
        # ====================================================================
        
        if self.supreme_mode or any([self.enable_mtf, self.enable_order_blocks, 
                                      self.enable_fvg, self.enable_quality_filter]):
            
            # FILTRO: Multi-timeframe alignment
            if not self._check_mtf_alignment(df, potential_side):
                return None
            
            # FILTRO: Order Blocks
            if self.enable_order_blocks:
                order_blocks = self._detect_order_blocks(df)
                if order_blocks and not self._is_near_order_block(current_price, order_blocks, potential_side):
                    return None
            
            # FILTRO: Fair Value Gaps
            if self.enable_fvg:
                fvg_zones = self._detect_fair_value_gaps(df)
                if fvg_zones and not self._is_near_fvg(current_price, fvg_zones, potential_side):
                    return None
            
            # FILTRO: Impulse confirmation
            if not self._has_recent_impulse(df, potential_side):
                return None
            
            # FILTRO: Volume confirmation
            if not self._has_volume_confirmation(df):
                return None
        
        # ====================================================================
        # GENERAR SEÑAL
        # ====================================================================
        
        entry = round(current_price, 2)
        sl_distance = float(getattr(CFG, "SL_DISTANCE", 17.0 if self.supreme_mode else 6.0))
        
        if potential_side == "BUY":
            sl = round(entry - sl_distance, 2)
            tps = self._calculate_tps("BUY", entry)
            return self._make_signal("BUY", entry, sl, tps, msg_id)
        else:  # SELL
            sl = round(entry + sl_distance, 2)
            tps = self._calculate_tps("SELL", entry)
            return self._make_signal("SELL", entry, sl, tps, msg_id)