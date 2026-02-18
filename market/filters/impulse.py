# market/filters/impulse.py
"""
Confirmacion de impulso en velas recientes.

Un impulso es una vela cuyo cuerpo supera N veces el ATR actual,
indicando movimiento institucional con conviction.
"""
from __future__ import annotations

import pandas as pd

from market.indicators import atr


def has_recent_impulse(
    df: pd.DataFrame,
    side: str,
    impulse_multiplier: float = 1.5,
    atr_period: int = 14,
    lookback: int = 5,
) -> bool:
    """
    Verifica si hubo una vela de impulso reciente en la direccion del trade.

    Args:
        df: DataFrame con OHLCV
        side: "BUY" o "SELL"
        impulse_multiplier: Multiplicador de ATR para considerar impulso
        atr_period: Periodo para calcular ATR
        lookback: Velas recientes a revisar

    Returns:
        True si hay al menos una vela de impulso en la direccion correcta.
        True tambien si no hay datos suficientes (no bloquea el trade).
    """
    if len(df) < lookback + atr_period:
        return True

    atr_val = float(atr(df, period=atr_period).iloc[-1])
    if pd.isna(atr_val) or atr_val <= 0:
        return True

    recent_candles = df.tail(lookback)

    for i in range(len(recent_candles)):
        candle = recent_candles.iloc[i]
        candle_size = abs(candle["close"] - candle["open"])
        is_bullish = candle["close"] > candle["open"]
        is_bearish = candle["close"] < candle["open"]

        if side == "BUY" and is_bullish and candle_size > (impulse_multiplier * atr_val):
            return True
        if side == "SELL" and is_bearish and candle_size > (impulse_multiplier * atr_val):
            return True

    return False