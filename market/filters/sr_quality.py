# market/filters/sr_quality.py
"""
Calidad de niveles de Soporte/Resistencia y confirmacion de volumen.
"""
from __future__ import annotations

import pandas as pd


def count_level_touches(
    df: pd.DataFrame,
    level: float,
    lookback: int = 50,
    tolerance: float = 3.0,
) -> int:
    """
    Cuenta cuantas velas tocaron un nivel S/R.

    Args:
        df: DataFrame con OHLCV
        level: Nivel de precio a evaluar
        lookback: Velas a revisar
        tolerance: Distancia maxima en puntos para considerar toque

    Returns:
        Numero de toques al nivel
    """
    if len(df) < lookback:
        lookback = len(df)

    recent_df = df.tail(lookback)
    touches = 0

    for i in range(len(recent_df)):
        candle = recent_df.iloc[i]
        if (abs(candle["low"] - level) < tolerance or
                abs(candle["high"] - level) < tolerance):
            touches += 1

    return touches


def is_quality_level(
    df: pd.DataFrame,
    level: float,
    min_touches: int = 2,
    lookback: int = 50,
) -> bool:
    """
    Verifica si un nivel S/R tiene suficiente calidad.

    Args:
        df: DataFrame con OHLCV
        level: Nivel a evaluar
        min_touches: Minimo de toques requeridos
        lookback: Velas a revisar

    Returns:
        True si el nivel tiene al menos min_touches toques
    """
    touches = count_level_touches(df, level, lookback=lookback)
    return touches >= min_touches


def has_volume_confirmation(
    df: pd.DataFrame,
    multiplier: float = 1.3,
    lookback: int = 20,
) -> bool:
    """
    Verifica si el volumen actual es superior al promedio.

    Args:
        df: DataFrame con OHLCV
        multiplier: Multiplicador sobre el volumen promedio
        lookback: Velas para calcular el promedio

    Returns:
        True si volumen actual >= promedio * multiplier
    """
    if len(df) < lookback:
        return True

    current_volume = float(df["tick_volume"].iloc[-1])
    avg_volume = float(df["tick_volume"].tail(lookback).mean())

    return current_volume >= (avg_volume * multiplier)