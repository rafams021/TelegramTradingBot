"""
Feature Extractor para ML - Fase 2

Extrae ~25 features de cada señal de trading para entrenar el modelo.

Features incluyen:
- Indicadores técnicos (RSI, ATR, EMAs, etc)
- Price action (momentum, volatility, ranges)
- Market context (hora, día, volumen)
- S/R levels info (para Reversal)
- Trend info (para Trend strategy)
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
# MAIN FEATURE EXTRACTOR
# ============================================================================

def extract_features(
    df: pd.DataFrame,
    signal_side: str,
    sr_level: Optional[float] = None,
    sma_fast: Optional[float] = None,
    sma_slow: Optional[float] = None,
) -> Dict[str, float]:
    """
    Extrae ~25 features de una señal de trading.
    
    Args:
        df: DataFrame con velas H1 (debe tener al menos 200 velas para calcular todo)
        signal_side: 'BUY' o 'SELL'
        sr_level: Nivel S/R detectado (para Reversal strategy) - opcional
        sma_fast: SMA rápida actual (para Trend strategy) - opcional
        sma_slow: SMA lenta actual (para Trend strategy) - opcional
    
    Returns:
        Dict con ~25 features numéricas
    
    Example:
        >>> features = extract_features(df, 'BUY', sr_level=3320.5)
        >>> features['rsi']
        43.2
        >>> features['momentum_3']
        2
    """
    if len(df) < 20:
        raise ValueError(f"DataFrame muy corto ({len(df)} velas), necesita al menos 20")
    
    features = {}
    current_price = float(df['close'].iloc[-1])
    
    # ========================================================================
    # 1. INDICADORES TÉCNICOS
    # ========================================================================
    
    # RSI
    rsi_val = calculate_rsi(df['close'], period=14)
    features['rsi'] = rsi_val
    features['rsi_extreme'] = 1 if (rsi_val < 30 or rsi_val > 70) else 0
    
    # RSI slope (cambio en últimas 3 velas)
    if len(df) >= 17:
        rsi_series = df['close'].rolling(15).apply(lambda x: calculate_rsi(x, 14), raw=False)
        rsi_slope = float(rsi_series.iloc[-1] - rsi_series.iloc[-4]) if not pd.isna(rsi_series.iloc[-4]) else 0.0
        features['rsi_slope'] = rsi_slope
    else:
        features['rsi_slope'] = 0.0
    
    # ATR (volatilidad)
    atr_val = calculate_atr(df, period=14)
    features['atr'] = atr_val
    features['atr_pct'] = (atr_val / current_price) * 100  # ATR como % del precio
    
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
        # Si no hay suficientes velas, usar defaults
        features['ema_50'] = current_price
        features['ema_200'] = current_price
        features['ema_gap_pct'] = 0.0
        features['price_above_ema50'] = 1
        features['price_above_ema200'] = 1
    
    # ========================================================================
    # 2. PRICE ACTION & MOMENTUM
    # ========================================================================
    
    # Momentum últimas 2 velas (para filtro Fase 1)
    last_2 = df.tail(2)
    bullish_2 = int((last_2['close'] > last_2['open']).sum())
    features['momentum_2'] = bullish_2  # 0, 1, o 2
    features['momentum_2_aligned'] = 1 if (
        (signal_side == 'BUY' and bullish_2 == 2) or
        (signal_side == 'SELL' and bullish_2 == 0)
    ) else 0
    
    # Momentum últimas 3 velas
    last_3 = df.tail(3)
    bullish_3 = int((last_3['close'] > last_3['open']).sum())
    features['momentum_3'] = bullish_3  # 0-3
    
    # Momentum últimas 5 velas
    last_5 = df.tail(5)
    bullish_5 = int((last_5['close'] > last_5['open']).sum())
    features['momentum_5'] = bullish_5  # 0-5
    
    # Price change (%) últimas 10 velas
    if len(df) >= 11:
        price_10_ago = float(df['close'].iloc[-11])
        price_change_pct = ((current_price - price_10_ago) / price_10_ago) * 100
        features['price_change_pct_10'] = price_change_pct
    else:
        features['price_change_pct_10'] = 0.0
    
    # Range (high - low) últimas 10 velas
    if len(df) >= 10:
        high_10 = float(df['high'].tail(10).max())
        low_10 = float(df['low'].tail(10).min())
        features['range_10'] = high_10 - low_10
        features['range_10_pct'] = ((high_10 - low_10) / current_price) * 100
    else:
        features['range_10'] = 0.0
        features['range_10_pct'] = 0.0
    
    # ========================================================================
    # 3. VOLUMEN
    # ========================================================================
    
    current_volume = float(df['tick_volume'].iloc[-1])
    
    # Volume ratio vs avg 20
    if len(df) >= 20:
        avg_volume_20 = float(df['tick_volume'].tail(20).mean())
        features['volume_ratio'] = current_volume / avg_volume_20 if avg_volume_20 > 0 else 1.0
    else:
        features['volume_ratio'] = 1.0
    
    # Volume trend (últimas 5 vs últimas 10)
    if len(df) >= 10:
        avg_vol_5 = float(df['tick_volume'].tail(5).mean())
        avg_vol_10 = float(df['tick_volume'].tail(10).mean())
        features['volume_trend'] = avg_vol_5 / avg_vol_10 if avg_vol_10 > 0 else 1.0
    else:
        features['volume_trend'] = 1.0
    
    # ========================================================================
    # 4. MARKET CONTEXT
    # ========================================================================
    
    # Hora del día (UTC) - normalizada 0-23
    features['hour_utc'] = int(df.index[-1].hour)
    
    # Día de semana (0=Monday, 4=Friday) - normalizada 0-4
    features['day_of_week'] = int(df.index[-1].weekday())
    
    # Session score (basado en backtests: EU+NY es mejor)
    hour = features['hour_utc']
    if 8 <= hour < 22:  # EU+NY session
        features['session_score'] = 1.0
    else:  # Asian session
        features['session_score'] = 0.5
    
    # ========================================================================
    # 5. SUPPORT/RESISTANCE INFO (para Reversal)
    # ========================================================================
    
    if sr_level is not None:
        # Distancia al nivel S/R
        distance = abs(current_price - sr_level)
        features['distance_to_sr'] = distance
        features['distance_to_sr_pct'] = (distance / current_price) * 100
        
        # Touches del nivel en últimas 20 velas
        touches = 0
        if len(df) >= 20:
            for i in range(-20, 0):
                low_touch = abs(df['low'].iloc[i] - sr_level) < 3.0
                high_touch = abs(df['high'].iloc[i] - sr_level) < 3.0
                if low_touch or high_touch:
                    touches += 1
        features['sr_touches_20'] = touches
    else:
        features['distance_to_sr'] = 0.0
        features['distance_to_sr_pct'] = 0.0
        features['sr_touches_20'] = 0
    
    # ========================================================================
    # 6. TREND INFO (para Trend strategy)
    # ========================================================================
    
    if sma_fast is not None and sma_slow is not None:
        # Gap entre SMAs
        sma_gap = sma_fast - sma_slow
        features['sma_gap'] = sma_gap
        features['sma_gap_pct'] = (sma_gap / current_price) * 100
        
        # Trend strength (qué tan separadas están las SMAs)
        features['trend_strength'] = abs(sma_gap / current_price) * 100
        
        # Distancia al SMA fast
        distance_sma = abs(current_price - sma_fast)
        features['distance_to_sma_fast'] = distance_sma
    else:
        features['sma_gap'] = 0.0
        features['sma_gap_pct'] = 0.0
        features['trend_strength'] = 0.0
        features['distance_to_sma_fast'] = 0.0
    
    # ========================================================================
    # 7. SIDE (BUY/SELL como feature binaria)
    # ========================================================================
    
    features['is_buy'] = 1 if signal_side == 'BUY' else 0
    
    # ========================================================================
    # VALIDACIÓN
    # ========================================================================
    
    # Asegurar que no hay NaN
    for key, value in features.items():
        if pd.isna(value):
            logger.warning(f"Feature '{key}' es NaN, reemplazando con 0.0")
            features[key] = 0.0
    
    return features


# ============================================================================
# FUNCIÓN PARA CREAR DATASET DE ENTRENAMIENTO
# ============================================================================

def create_training_dataset_from_backtest(
    backtest_csv_path: str,
    output_csv_path: str = "ml/training_data.csv"
) -> pd.DataFrame:
    """
    Crea dataset de entrenamiento desde CSV de backtest.
    
    NOTA: Esta función requiere re-ejecutar el backtest con acceso
    a las velas históricas para extraer features. No puede extraer
    features solo desde el CSV de trades porque necesita las velas.
    
    Para usarla:
    1. Modifica backtest.py para llamar extract_features() en cada señal
    2. Guarda features junto con el resultado del trade
    3. Exporta todo a CSV
    
    Args:
        backtest_csv_path: Path al CSV de trades del backtest
        output_csv_path: Path donde guardar el dataset con features
    
    Returns:
        DataFrame con features y target (won)
    """
    # Cargar trades
    trades_df = pd.read_csv(backtest_csv_path)
    
    # Crear target: 1 si ganó (TP1/TP2/TP3), 0 si perdió (SL)
    trades_df['won'] = trades_df['result'].isin(['TP1', 'TP2', 'TP3']).astype(int)
    
    logger.info(f"Trades cargados: {len(trades_df)}")
    logger.info(f"Win rate: {trades_df['won'].mean():.1%}")
    
    # ADVERTENCIA: No podemos extraer features solo del CSV
    # Necesitamos las velas históricas
    logger.warning("⚠️  Para crear dataset completo, debes modificar backtest.py")
    logger.warning("    para que guarde features junto con cada trade.")
    
    return trades_df


if __name__ == "__main__":
    # Test básico
    print("Feature Extractor - Fase 2")
    print("=" * 60)
    
    # Crear DataFrame de prueba
    test_data = {
        'open': [3300, 3305, 3310, 3315, 3320] * 50,  # 250 velas
        'high': [3310, 3315, 3320, 3325, 3330] * 50,
        'low': [3295, 3300, 3305, 3310, 3315] * 50,
        'close': [3305, 3310, 3315, 3320, 3325] * 50,
        'tick_volume': [1000, 1200, 1100, 1300, 1150] * 50,
    }
    test_df = pd.DataFrame(test_data)
    test_df.index = pd.date_range('2025-01-01', periods=250, freq='1H')
    
    # Extraer features
    features = extract_features(
        df=test_df,
        signal_side='BUY',
        sr_level=3320.0,
        sma_fast=3318.0,
        sma_slow=3310.0
    )
    
    print(f"\n✅ Features extraídas: {len(features)}")
    print("\nPrimeras 10 features:")
    for i, (key, value) in enumerate(list(features.items())[:10]):
        print(f"  {key:<25} = {value:.2f}")
    
    print(f"\n✅ Feature extractor funcionando correctamente")