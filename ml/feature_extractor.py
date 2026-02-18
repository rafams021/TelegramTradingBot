"""
Feature Extractor para ML - Fase 2 MEJORADO

NUEVAS FEATURES AGREGADAS:
- Consecutive candles (rachas alcistas/bajistas)
- Price action patterns (pin bars, engulfing)
- S/R quality (fuerza del nivel, tiempo desde toque)
- Market structure (swing highs/lows)
- Volatility ratios
- Time encoding mejorado
- Multi-period momentum

Total: ~45 features (antes: 30)
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# HELPER FUNCTIONS - INDICADORES
# ============================================================================

def calculate_rsi(series: pd.Series, period: int = 14) -> float:
    """Calcula RSI actual"""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0


def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    """Calcula ATR actual"""
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    atr = true_range.rolling(period).mean()
    return float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else 15.0


def calculate_ema(series: pd.Series, period: int) -> float:
    """Calcula EMA actual"""
    ema = series.ewm(span=period, adjust=False).mean()
    return float(ema.iloc[-1]) if not pd.isna(ema.iloc[-1]) else float(series.iloc[-1])


def calculate_sma(series: pd.Series, period: int) -> float:
    """Calcula SMA actual"""
    sma = series.rolling(window=period).mean()
    return float(sma.iloc[-1]) if not pd.isna(sma.iloc[-1]) else float(series.iloc[-1])


# ============================================================================
# NUEVAS HELPER FUNCTIONS - PRICE ACTION
# ============================================================================

def count_consecutive_candles(df: pd.DataFrame, direction: str = 'bullish') -> int:
    """
    Cuenta cuántas velas consecutivas en la misma dirección (desde el final).
    
    Args:
        df: DataFrame con OHLC
        direction: 'bullish' o 'bearish'
    
    Returns:
        Número de velas consecutivas
    """
    count = 0
    for i in range(len(df) - 1, -1, -1):
        candle = df.iloc[i]
        is_bullish = candle['close'] > candle['open']
        
        if direction == 'bullish' and is_bullish:
            count += 1
        elif direction == 'bearish' and not is_bullish:
            count += 1
        else:
            break
    
    return count


def detect_pin_bar(df: pd.DataFrame) -> int:
    """
    Detecta pin bar en la última vela.
    
    Pin bar = vela con mecha larga (>60% del total) y cuerpo pequeño.
    
    Returns:
        1 si es bullish pin bar, -1 si bearish, 0 si no es pin bar
    """
    if len(df) < 1:
        return 0
    
    candle = df.iloc[-1]
    body = abs(candle['close'] - candle['open'])
    total_range = candle['high'] - candle['low']
    
    if total_range == 0:
        return 0
    
    upper_wick = candle['high'] - max(candle['close'], candle['open'])
    lower_wick = min(candle['close'], candle['open']) - candle['low']
    
    body_pct = body / total_range
    
    # Pin bar = cuerpo < 30% y una mecha > 60%
    if body_pct < 0.3:
        if lower_wick / total_range > 0.6:
            return 1  # Bullish pin (rechazo en bajo)
        elif upper_wick / total_range > 0.6:
            return -1  # Bearish pin (rechazo en alto)
    
    return 0


def detect_engulfing(df: pd.DataFrame) -> int:
    """
    Detecta patrón engulfing en las últimas 2 velas.
    
    Returns:
        1 si bullish engulfing, -1 si bearish, 0 si no hay
    """
    if len(df) < 2:
        return 0
    
    prev = df.iloc[-2]
    curr = df.iloc[-1]
    
    prev_bullish = prev['close'] > prev['open']
    curr_bullish = curr['close'] > curr['open']
    
    # Bullish engulfing: vela anterior bajista, actual alcista que la engloba
    if not prev_bullish and curr_bullish:
        if curr['close'] > prev['open'] and curr['open'] < prev['close']:
            return 1
    
    # Bearish engulfing: vela anterior alcista, actual bajista que la engloba
    if prev_bullish and not curr_bullish:
        if curr['close'] < prev['open'] and curr['open'] > prev['close']:
            return -1
    
    return 0


def count_swing_highs_lows(df: pd.DataFrame, lookback: int = 20) -> tuple:
    """
    Cuenta swing highs y swing lows en últimas N velas.
    
    Swing high = vela con high mayor que 2 velas antes y 2 después
    Swing low = vela con low menor que 2 velas antes y 2 después
    
    Returns:
        (swing_highs_count, swing_lows_count)
    """
    if len(df) < lookback + 4:
        return (0, 0)
    
    recent = df.tail(lookback)
    swing_highs = 0
    swing_lows = 0
    
    for i in range(2, len(recent) - 2):
        candle = recent.iloc[i]
        
        # Swing high
        if (candle['high'] > recent.iloc[i-1]['high'] and
            candle['high'] > recent.iloc[i-2]['high'] and
            candle['high'] > recent.iloc[i+1]['high'] and
            candle['high'] > recent.iloc[i+2]['high']):
            swing_highs += 1
        
        # Swing low
        if (candle['low'] < recent.iloc[i-1]['low'] and
            candle['low'] < recent.iloc[i-2]['low'] and
            candle['low'] < recent.iloc[i+1]['low'] and
            candle['low'] < recent.iloc[i+2]['low']):
            swing_lows += 1
    
    return (swing_highs, swing_lows)


# ============================================================================
# MAIN FEATURE EXTRACTOR - MEJORADO
# ============================================================================

def extract_features(
    df: pd.DataFrame,
    signal_side: str,
    sr_level: Optional[float] = None,
    sma_fast: Optional[float] = None,
    sma_slow: Optional[float] = None,
) -> Dict[str, float]:
    """
    Extrae ~45 features de una señal de trading (MEJORADO).
    
    NUEVAS FEATURES vs versión anterior:
    - consecutive_candles_same_direction
    - pin_bar_detected
    - engulfing_pattern
    - swing_highs_count, swing_lows_count
    - atr_ratio (ATR actual vs promedio)
    - time_of_day_encoded (mañana/tarde/noche)
    - sr_level_strength
    - candles_since_sr_touch
    - body_to_range_ratio
    - wick_ratio
    - higher_highs_last_10, lower_lows_last_10
    - rsi_divergence
    - volume_spike
    - momentum_strength (weighted momentum)
    """
    if len(df) < 20:
        raise ValueError(f"DataFrame muy corto ({len(df)} velas), necesita al menos 20")
    
    features = {}
    current_price = float(df['close'].iloc[-1])
    
    # ========================================================================
    # 1. INDICADORES TÉCNICOS (EXISTENTES)
    # ========================================================================
    
    # RSI
    rsi_val = calculate_rsi(df['close'], period=14)
    features['rsi'] = rsi_val
    features['rsi_extreme'] = 1 if (rsi_val < 30 or rsi_val > 70) else 0
    
    # RSI slope
    if len(df) >= 17:
        rsi_series = df['close'].rolling(15).apply(lambda x: calculate_rsi(x, 14), raw=False)
        rsi_slope = float(rsi_series.iloc[-1] - rsi_series.iloc[-4]) if not pd.isna(rsi_series.iloc[-4]) else 0.0
        features['rsi_slope'] = rsi_slope
    else:
        features['rsi_slope'] = 0.0
    
    # NUEVA: RSI divergence (RSI sube pero precio baja, o viceversa)
    if len(df) >= 17:
        price_change_5 = df['close'].iloc[-1] - df['close'].iloc[-6]
        rsi_change_5 = rsi_series.iloc[-1] - rsi_series.iloc[-6] if not pd.isna(rsi_series.iloc[-6]) else 0
        # Divergencia = signos opuestos
        features['rsi_divergence'] = 1 if (price_change_5 * rsi_change_5 < 0) else 0
    else:
        features['rsi_divergence'] = 0
    
    # ATR
    atr_val = calculate_atr(df, period=14)
    features['atr'] = atr_val
    features['atr_pct'] = (atr_val / current_price) * 100
    
    # NUEVA: ATR ratio (volatilidad actual vs promedio)
    if len(df) >= 30:
        atr_20 = calculate_atr(df.iloc[:-10], period=14)  # ATR de hace 10 velas
        features['atr_ratio'] = atr_val / atr_20 if atr_20 > 0 else 1.0
    else:
        features['atr_ratio'] = 1.0
    
    # EMAs
    if len(df) >= 200:
        ema_50 = calculate_ema(df['close'], 50)
        ema_200 = calculate_ema(df['close'], 200)
        features['ema_50'] = ema_50
        features['ema_200'] = ema_200
        features['ema_gap_pct'] = ((ema_50 - ema_200) / current_price) * 100
        features['price_above_ema50'] = 1 if current_price > ema_50 else 0
        features['price_above_ema200'] = 1 if current_price > ema_200 else 0
    else:
        features['ema_50'] = current_price
        features['ema_200'] = current_price
        features['ema_gap_pct'] = 0.0
        features['price_above_ema50'] = 1
        features['price_above_ema200'] = 1
    
    # ========================================================================
    # 2. PRICE ACTION & MOMENTUM (MEJORADOS)
    # ========================================================================
    
    # Momentum básico (existente)
    last_2 = df.tail(2)
    bullish_2 = int((last_2['close'] > last_2['open']).sum())
    features['momentum_2'] = bullish_2
    features['momentum_2_aligned'] = 1 if (
        (signal_side == 'BUY' and bullish_2 == 2) or
        (signal_side == 'SELL' and bullish_2 == 0)
    ) else 0
    
    last_3 = df.tail(3)
    bullish_3 = int((last_3['close'] > last_3['open']).sum())
    features['momentum_3'] = bullish_3
    
    last_5 = df.tail(5)
    bullish_5 = int((last_5['close'] > last_5['open']).sum())
    features['momentum_5'] = bullish_5
    
    # NUEVA: Consecutive candles
    consecutive_bull = count_consecutive_candles(df, 'bullish')
    consecutive_bear = count_consecutive_candles(df, 'bearish')
    features['consecutive_candles'] = consecutive_bull if consecutive_bull > 0 else -consecutive_bear
    
    # NUEVA: Momentum strength (weighted by candle size)
    if len(df) >= 5:
        weighted_momentum = 0
        for i in range(-5, 0):
            candle = df.iloc[i]
            direction = 1 if candle['close'] > candle['open'] else -1
            size = abs(candle['close'] - candle['open'])
            weighted_momentum += direction * size
        features['momentum_strength'] = float(weighted_momentum)
    else:
        features['momentum_strength'] = 0.0
    
    # Price change
    if len(df) >= 11:
        price_10_ago = float(df['close'].iloc[-11])
        price_change_pct = ((current_price - price_10_ago) / price_10_ago) * 100
        features['price_change_pct_10'] = price_change_pct
    else:
        features['price_change_pct_10'] = 0.0
    
    # NUEVA: Higher highs / Lower lows count
    if len(df) >= 11:
        last_10_highs = df['high'].tail(10)
        last_10_lows = df['low'].tail(10)
        higher_highs = sum([1 for i in range(1, len(last_10_highs)) if last_10_highs.iloc[i] > last_10_highs.iloc[i-1]])
        lower_lows = sum([1 for i in range(1, len(last_10_lows)) if last_10_lows.iloc[i] < last_10_lows.iloc[i-1]])
        features['higher_highs_last_10'] = higher_highs
        features['lower_lows_last_10'] = lower_lows
    else:
        features['higher_highs_last_10'] = 0
        features['lower_lows_last_10'] = 0
    
    # Range
    if len(df) >= 10:
        high_10 = float(df['high'].tail(10).max())
        low_10 = float(df['low'].tail(10).min())
        features['range_10'] = high_10 - low_10
        features['range_10_pct'] = ((high_10 - low_10) / current_price) * 100
    else:
        features['range_10'] = 0.0
        features['range_10_pct'] = 0.0
    
    # NUEVA: Candle body/wick ratios
    last_candle = df.iloc[-1]
    body = abs(last_candle['close'] - last_candle['open'])
    total_range = last_candle['high'] - last_candle['low']
    if total_range > 0:
        features['body_to_range_ratio'] = body / total_range
        upper_wick = last_candle['high'] - max(last_candle['close'], last_candle['open'])
        lower_wick = min(last_candle['close'], last_candle['open']) - last_candle['low']
        features['wick_ratio'] = (upper_wick + lower_wick) / total_range
    else:
        features['body_to_range_ratio'] = 0.5
        features['wick_ratio'] = 0.5
    
    # NUEVA: Price action patterns
    features['pin_bar'] = float(detect_pin_bar(df))
    features['engulfing'] = float(detect_engulfing(df))
    
    # NUEVA: Swing highs/lows
    swing_h, swing_l = count_swing_highs_lows(df, lookback=20)
    features['swing_highs_20'] = swing_h
    features['swing_lows_20'] = swing_l
    
    # ========================================================================
    # 3. VOLUMEN (MEJORADO)
    # ========================================================================
    
    current_volume = float(df['tick_volume'].iloc[-1])
    
    if len(df) >= 20:
        avg_volume_20 = float(df['tick_volume'].tail(20).mean())
        features['volume_ratio'] = current_volume / avg_volume_20 if avg_volume_20 > 0 else 1.0
        
        # NUEVA: Volume spike (volumen > 2x promedio)
        features['volume_spike'] = 1 if current_volume > (avg_volume_20 * 2) else 0
    else:
        features['volume_ratio'] = 1.0
        features['volume_spike'] = 0
    
    if len(df) >= 10:
        avg_vol_5 = float(df['tick_volume'].tail(5).mean())
        avg_vol_10 = float(df['tick_volume'].tail(10).mean())
        features['volume_trend'] = avg_vol_5 / avg_vol_10 if avg_vol_10 > 0 else 1.0
    else:
        features['volume_trend'] = 1.0
    
    # ========================================================================
    # 4. MARKET CONTEXT (MEJORADO)
    # ========================================================================
    
    hour = int(df.index[-1].hour)
    features['hour_utc'] = hour
    
    # NUEVA: Time of day encoding (mejor que hora raw)
    if 8 <= hour < 13:
        features['time_of_day'] = 1.0  # Mañana europea
    elif 13 <= hour < 18:
        features['time_of_day'] = 2.0  # Tarde (overlap EU/NY)
    elif 18 <= hour < 22:
        features['time_of_day'] = 3.0  # Noche (NY)
    else:
        features['time_of_day'] = 0.0  # Fuera de sesión
    
    features['day_of_week'] = int(df.index[-1].weekday())
    
    # Session score (existente)
    if 8 <= hour < 22:
        features['session_score'] = 1.0
    else:
        features['session_score'] = 0.5
    
    # ========================================================================
    # 5. SUPPORT/RESISTANCE INFO (MEJORADO)
    # ========================================================================
    
    if sr_level is not None:
        distance = abs(current_price - sr_level)
        features['distance_to_sr'] = distance
        features['distance_to_sr_pct'] = (distance / current_price) * 100
        
        # Touches del nivel
        touches = 0
        if len(df) >= 20:
            for i in range(-20, 0):
                low_touch = abs(df['low'].iloc[i] - sr_level) < 3.0
                high_touch = abs(df['high'].iloc[i] - sr_level) < 3.0
                if low_touch or high_touch:
                    touches += 1
        features['sr_touches_20'] = touches
        
        # NUEVA: SR level strength (más toques = nivel más fuerte)
        features['sr_level_strength'] = min(touches / 5.0, 1.0)  # Normalizado 0-1
        
        # NUEVA: Candles since last touch
        candles_since_touch = 20  # Default
        if len(df) >= 20:
            for i in range(-1, -21, -1):
                if abs(df['low'].iloc[i] - sr_level) < 3.0 or abs(df['high'].iloc[i] - sr_level) < 3.0:
                    candles_since_touch = abs(i)
                    break
        features['candles_since_sr_touch'] = candles_since_touch
    else:
        features['distance_to_sr'] = 0.0
        features['distance_to_sr_pct'] = 0.0
        features['sr_touches_20'] = 0
        features['sr_level_strength'] = 0.0
        features['candles_since_sr_touch'] = 20
    
    # ========================================================================
    # 6. TREND INFO (existente para Trend strategy)
    # ========================================================================
    
    if sma_fast is not None and sma_slow is not None:
        sma_gap = sma_fast - sma_slow
        features['sma_gap'] = sma_gap
        features['sma_gap_pct'] = (sma_gap / current_price) * 100
        features['trend_strength'] = abs(sma_gap / current_price) * 100
        distance_sma = abs(current_price - sma_fast)
        features['distance_to_sma_fast'] = distance_sma
    else:
        features['sma_gap'] = 0.0
        features['sma_gap_pct'] = 0.0
        features['trend_strength'] = 0.0
        features['distance_to_sma_fast'] = 0.0
    
    # ========================================================================
    # 7. SIDE (existente)
    # ========================================================================
    
    features['is_buy'] = 1 if signal_side == 'BUY' else 0
    
    # ========================================================================
    # VALIDACIÓN
    # ========================================================================
    
    for key, value in features.items():
        if pd.isna(value):
            logger.warning(f"Feature '{key}' es NaN, reemplazando con 0.0")
            features[key] = 0.0
    
    return features


if __name__ == "__main__":
    print("Feature Extractor MEJORADO - Fase 2")
    print("=" * 60)
    
    # Test con datos sintéticos
    test_data = {
        'open': [3300, 3305, 3310, 3315, 3320] * 50,
        'high': [3310, 3315, 3320, 3325, 3330] * 50,
        'low': [3295, 3300, 3305, 3310, 3315] * 50,
        'close': [3305, 3310, 3315, 3320, 3325] * 50,
        'tick_volume': [1000, 1200, 1100, 1300, 1150] * 50,
    }
    test_df = pd.DataFrame(test_data)
    test_df.index = pd.date_range('2025-01-01', periods=250, freq='1H')
    
    features = extract_features(
        df=test_df,
        signal_side='BUY',
        sr_level=3320.0,
        sma_fast=3318.0,
        sma_slow=3310.0
    )
    
    print(f"\n✅ Features extraídas: {len(features)}")
    print("\nNUEVAS features (15+):")
    new_features = ['consecutive_candles', 'momentum_strength', 'higher_highs_last_10', 
                   'lower_lows_last_10', 'body_to_range_ratio', 'wick_ratio', 'pin_bar',
                   'engulfing', 'swing_highs_20', 'swing_lows_20', 'volume_spike',
                   'time_of_day', 'sr_level_strength', 'candles_since_sr_touch', 
                   'atr_ratio', 'rsi_divergence']
    
    for feat in new_features:
        if feat in features:
            print(f"  {feat:<30} = {features[feat]:.2f}")
    
    print(f"\n✅ Feature extractor mejorado funcionando correctamente")
    print(f"Total features: {len(features)} (antes: ~30)")