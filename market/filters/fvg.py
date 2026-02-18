# market/filters/fvg.py
"""
Deteccion de Fair Value Gaps (FVG).

Un FVG es un gap entre la vela N-2 y la vela N donde la vela N-1
no cubre completamente ese rango. Indica zonas de liquidez institucional.
"""
from __future__ import annotations

from typing import List, Dict

import pandas as pd


def detect_fair_value_gaps(
    df: pd.DataFrame,
    min_gap_size: float = 5.0,
    lookback: int = 30,
) -> List[Dict]:
    """
    Detecta Fair Value Gaps en el DataFrame.

    Args:
        df: DataFrame con OHLCV
        min_gap_size: Tamano minimo del gap en puntos
        lookback: Velas a analizar

    Returns:
        Lista de dicts con keys: type, high, low
    """
    if len(df) < lookback + 2:
        return []

    fvg_zones = []
    recent_df = df.tail(lookback)

    for i in range(2, len(recent_df)):
        c_prev2 = recent_df.iloc[i - 2]
        c_prev1 = recent_df.iloc[i - 1]
        c_curr  = recent_df.iloc[i]

        # Bullish FVG: gap entre high de N-2 y low de N
        gap_low  = float(c_prev2["high"])
        gap_high = float(c_curr["low"])

        if gap_high > gap_low:
            if c_prev1["high"] < gap_high and c_prev1["low"] > gap_low:
                if (gap_high - gap_low) > min_gap_size:
                    fvg_zones.append({
                        "type": "BULLISH_FVG",
                        "high": gap_high,
                        "low":  gap_low,
                    })

        # Bearish FVG: gap entre low de N-2 y high de N
        gap_high_b = float(c_prev2["low"])
        gap_low_b  = float(c_curr["high"])

        if gap_high_b > gap_low_b:
            if c_prev1["low"] > gap_low_b and c_prev1["high"] < gap_high_b:
                if (gap_high_b - gap_low_b) > min_gap_size:
                    fvg_zones.append({
                        "type": "BEARISH_FVG",
                        "high": gap_high_b,
                        "low":  gap_low_b,
                    })

    return fvg_zones


def is_near_fvg(
    price: float,
    fvg_zones: List[Dict],
    side: str,
) -> bool:
    """
    Verifica si el precio esta dentro de un FVG relevante.

    Args:
        price: Precio actual
        fvg_zones: Lista de FVGs detectados
        side: "BUY" o "SELL"

    Returns:
        True si el precio esta en un FVG del lado correcto
    """
    for fvg in fvg_zones:
        if side == "BUY" and fvg["type"] == "BULLISH_FVG":
            if fvg["low"] <= price <= fvg["high"]:
                return True
        if side == "SELL" and fvg["type"] == "BEARISH_FVG":
            if fvg["low"] <= price <= fvg["high"]:
                return True
    return False