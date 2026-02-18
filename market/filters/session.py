# market/filters/session.py
"""
Filtros de sesion de trading.
"""
from __future__ import annotations

import pandas as pd


def is_high_quality_session(ts: pd.Timestamp) -> bool:
    """
    Sesion ultra-selectiva: solo London open y NY open.

    Franjas:
        London open : 08:00 - 10:00 UTC
        NY open     : 13:00 - 17:00 UTC

    Args:
        ts: Timestamp de la vela

    Returns:
        True si esta dentro de una sesion de alta calidad
    """
    hour = ts.hour
    return (8 <= hour < 10) or (13 <= hour < 17)


def is_valid_session(ts: pd.Timestamp, session_filter: str = "24h") -> bool:
    """
    Filtro de sesion configurable.

    Args:
        ts: Timestamp de la vela
        session_filter: "24h" | "eu_ny" | "ny_only"

    Returns:
        True si esta dentro de la sesion permitida
    """
    if session_filter == "24h":
        return True

    hour = ts.hour

    if session_filter == "eu_ny":
        return 8 <= hour < 22

    if session_filter == "ny_only":
        return 13 <= hour < 22

    return True