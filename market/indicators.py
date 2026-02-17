# market/indicators.py
"""
Indicadores técnicos para análisis de mercado.

Todas las funciones son puras: reciben un DataFrame y devuelven
valores calculados. Sin estado, sin efectos secundarios.

El DataFrame de entrada debe tener columnas: open, high, low, close
con índice datetime (formato estándar de DataProvider).
"""
from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd


def sma(df: pd.DataFrame, period: int, column: str = "close") -> pd.Series:
    """
    Simple Moving Average.

    Args:
        df: DataFrame con datos OHLCV
        period: Período de la media móvil
        column: Columna a usar (default: "close")

    Returns:
        Serie con los valores de la SMA
    """
    return df[column].rolling(window=period).mean()


def rsi(df: pd.DataFrame, period: int = 14, column: str = "close") -> pd.Series:
    """
    Relative Strength Index.

    Args:
        df: DataFrame con datos OHLCV
        period: Período del RSI (default: 14)
        column: Columna a usar (default: "close")

    Returns:
        Serie con los valores del RSI (0-100)
    """
    delta = df[column].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()

    # Evitar división por cero
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_values = 100 - (100 / (1 + rs))

    return rsi_values.fillna(50)  # Neutral si no hay datos suficientes


def recent_high(df: pd.DataFrame, lookback: int) -> float:
    """
    Máximo más alto de las últimas N velas.

    Args:
        df: DataFrame con datos OHLCV
        lookback: Número de velas hacia atrás a considerar

    Returns:
        Precio máximo del período
    """
    if len(df) < lookback:
        return float(df["high"].max())
    return float(df["high"].iloc[-lookback:].max())


def recent_low(df: pd.DataFrame, lookback: int) -> float:
    """
    Mínimo más bajo de las últimas N velas.

    Args:
        df: DataFrame con datos OHLCV
        lookback: Número de velas hacia atrás a considerar

    Returns:
        Precio mínimo del período
    """
    if len(df) < lookback:
        return float(df["low"].min())
    return float(df["low"].iloc[-lookback:].min())


def support_resistance_levels(
    df: pd.DataFrame,
    lookback: int = 20,
    min_touches: int = 2,
    tolerance_pips: float = 2.0,
) -> List[float]:
    """
    Detecta niveles de soporte y resistencia por densidad de toques.

    Un nivel es válido si el precio lo ha tocado al menos min_touches
    veces dentro de una tolerancia de tolerance_pips.

    Args:
        df: DataFrame con datos OHLCV
        lookback: Velas hacia atrás a analizar
        min_touches: Mínimo de toques para considerar un nivel válido
        tolerance_pips: Tolerancia en pips para agrupar toques

    Returns:
        Lista de niveles ordenados de menor a mayor
    """
    if len(df) < lookback:
        return []

    recent = df.iloc[-lookback:]

    # Candidatos: highs y lows de cada vela
    candidates = list(recent["high"]) + list(recent["low"])
    candidates.sort()

    levels = []
    used = set()

    for i, price in enumerate(candidates):
        if i in used:
            continue

        # Contar cuántos precios están dentro de la tolerancia
        touches = [
            j for j, p in enumerate(candidates)
            if abs(p - price) <= tolerance_pips
        ]

        if len(touches) >= min_touches:
            # El nivel es el promedio de los toques
            level = float(np.mean([candidates[j] for j in touches]))
            levels.append(level)
            used.update(touches)

    return sorted(levels)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Average True Range — mide la volatilidad del mercado.

    Args:
        df: DataFrame con datos OHLCV
        period: Período del ATR (default: 14)

    Returns:
        Serie con los valores del ATR
    """
    high = df["high"]
    low = df["low"]
    close = df["close"].shift(1)

    tr = pd.concat([
        high - low,
        (high - close).abs(),
        (low - close).abs(),
    ], axis=1).max(axis=1)

    return tr.rolling(window=period).mean()