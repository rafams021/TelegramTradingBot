# market/filters/order_blocks.py
"""
Deteccion de Order Blocks institucionales.
"""
from __future__ import annotations

from typing import List, Dict

import pandas as pd

from market.indicators import atr


def detect_order_blocks(
    df: pd.DataFrame,
    impulse_multiplier: float = 1.5,
    atr_period: int = 14,
    lookback: int = 50,
) -> List[Dict]:
    """
    Detecta Order Blocks en el DataFrame.

    Un OB bullish es una vela bajista previa a una vela alcista de impulso.
    Un OB bearish es una vela alcista previa a una vela bajista de impulso.

    Args:
        df: DataFrame con OHLCV
        impulse_multiplier: Multiplicador de ATR para considerar impulso
        atr_period: Periodo para calcular ATR
        lookback: Velas a analizar

    Returns:
        Lista de dicts con keys: type, high, low
    """
    if len(df) < lookback:
        return []

    atr_val = float(atr(df, period=atr_period).iloc[-1])
    if pd.isna(atr_val) or atr_val <= 0:
        return []

    order_blocks = []
    recent_df = df.tail(lookback)

    for i in range(1, len(recent_df) - 1):
        curr = recent_df.iloc[i]
        prev = recent_df.iloc[i - 1]

        curr_size = abs(curr["close"] - curr["open"])
        is_bullish = curr["close"] > curr["open"]
        is_bearish = curr["close"] < curr["open"]

        if is_bullish and curr_size > (impulse_multiplier * atr_val):
            if prev["close"] < prev["open"]:
                order_blocks.append({
                    "type": "BULLISH_OB",
                    "high": float(prev["high"]),
                    "low":  float(prev["low"]),
                })

        if is_bearish and curr_size > (impulse_multiplier * atr_val):
            if prev["close"] > prev["open"]:
                order_blocks.append({
                    "type": "BEARISH_OB",
                    "high": float(prev["high"]),
                    "low":  float(prev["low"]),
                })

    return order_blocks


def is_near_order_block(
    price: float,
    order_blocks: List[Dict],
    side: str,
) -> bool:
    """
    Verifica si el precio esta dentro de un Order Block relevante.

    Args:
        price: Precio actual
        order_blocks: Lista de OBs detectados
        side: "BUY" o "SELL"

    Returns:
        True si el precio esta en un OB del lado correcto
    """
    for ob in order_blocks:
        if side == "BUY" and ob["type"] == "BULLISH_OB":
            if ob["low"] <= price <= ob["high"]:
                return True
        if side == "SELL" and ob["type"] == "BEARISH_OB":
            if ob["low"] <= price <= ob["high"]:
                return True
    return False