# market/strategies/momentum.py
"""
Estrategia de Momentum — "riding the move".

Detecta movimientos explosivos del XAUUSD y entra a mercado inmediatamente.

Condiciones para activar:
  1. Velocidad: el precio se movió > move_threshold dólares en los
     últimos tick_window ticks (velas M1)
  2. Volumen explosivo: volumen de las últimas velas > volume_multiplier × promedio
  3. Dirección clara: consecutive_candles velas consecutivas del mismo color

Entrada: MARKET inmediato
SL: Fijo desde config (sl_distance, ~$6)
TP: Fijo desde config (tp_distances: $5, $11, $16)

Ejemplo real:
  04:58 — XAUUSD cae $75 en 2 horas
  → 3 velas rojas consecutivas
  → volumen 3x promedio
  → velocidad: $15/vela
  → SELL MARKET inmediato, SL $6 arriba, TP1=$5, TP2=$11, TP3=$16
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

import config as CFG
from core.state import Signal
from market.indicators import atr
from .base import BaseStrategy


class MomentumStrategy(BaseStrategy):
    """
    Detecta movimientos explosivos y entra a mercado.

    Usa velas M1 pasadas por el AutonomousTrader en su tick_loop.
    El MarketAnalyzer principal corre en H1; el MomentumStrategy
    se instancia con timeframe M1 y candles=20 en el _tick_loop.
    """

    def __init__(
        self,
        symbol: str,
        magic: int,
        # Condición 1: Velocidad del movimiento
        move_threshold: float = 10.0,     # mínimo $10 de movimiento en tick_window velas
        tick_window: int = 3,             # velas M1 a revisar
        # Condición 2: Volumen explosivo
        volume_multiplier: float = 3.0,   # 3x el volumen promedio
        volume_lookback: int = 20,        # velas para calcular promedio de volumen
        # Condición 3: Dirección clara
        consecutive_candles: int = 3,     # velas consecutivas del mismo color
        # ATR para validación interna
        atr_period: int = 14,
    ):
        super().__init__(symbol, magic)
        self.move_threshold = move_threshold
        self.tick_window = tick_window
        self.volume_multiplier = volume_multiplier
        self.volume_lookback = volume_lookback
        self.consecutive_candles = consecutive_candles
        self.atr_period = atr_period

    @property
    def name(self) -> str:
        return "MOMENTUM"

    def _calculate_tps(self, side: str, entry: float) -> list:
        """TPs fijos desde config."""
        distances = list(getattr(CFG, "TP_DISTANCES", (5.0, 11.0, 16.0)))
        if side == "BUY":
            return [round(entry + d, 2) for d in distances]
        else:
            return [round(entry - d, 2) for d in distances]

    def _check_velocity(self, df: pd.DataFrame) -> Optional[str]:
        """
        Verifica si el precio se movió > move_threshold en tick_window velas.

        Returns:
            "BUY" si el movimiento es alcista fuerte
            "SELL" si el movimiento es bajista fuerte
            None si no hay momentum suficiente
        """
        if len(df) < self.tick_window:
            return None

        recent = df.iloc[-self.tick_window:]
        price_start = float(recent.iloc[0]["open"])
        price_end = float(recent.iloc[-1]["close"])
        move = price_end - price_start

        if abs(move) >= self.move_threshold:
            return "BUY" if move > 0 else "SELL"

        return None

    def _check_volume(self, df: pd.DataFrame) -> bool:
        """
        Verifica que las últimas tick_window velas tienen volumen explosivo.

        El promedio de volumen de las últimas tick_window velas debe superar
        volume_multiplier × el promedio histórico de volume_lookback velas.
        """
        lookback_total = self.volume_lookback + self.tick_window
        if len(df) < lookback_total:
            return False

        # Volumen histórico (baseline)
        baseline = df.iloc[-(lookback_total):-self.tick_window]["tick_volume"]
        avg_baseline = float(baseline.mean())

        if avg_baseline <= 0:
            return False

        # Volumen reciente
        recent_vol = float(df.iloc[-self.tick_window:]["tick_volume"].mean())

        return recent_vol >= (avg_baseline * self.volume_multiplier)

    def _check_consecutive_candles(self, df: pd.DataFrame) -> Optional[str]:
        """
        Verifica que hay consecutive_candles velas del mismo color.

        Returns:
            "BUY" si son velas alcistas (bull)
            "SELL" si son velas bajistas (bear)
            None si la dirección no es clara
        """
        if len(df) < self.consecutive_candles:
            return None

        recent = df.iloc[-self.consecutive_candles:]
        directions = []

        for _, candle in recent.iterrows():
            if float(candle["close"]) > float(candle["open"]):
                directions.append("BUY")
            elif float(candle["close"]) < float(candle["open"]):
                directions.append("SELL")
            else:
                directions.append("NEUTRAL")

        if all(d == "BUY" for d in directions):
            return "BUY"
        if all(d == "SELL" for d in directions):
            return "SELL"

        return None

    def scan(self, df: pd.DataFrame, current_price: float) -> Optional[Signal]:
        """
        Detecta momentum explosivo y genera señal MARKET.

        Las 3 condiciones deben cumplirse y apuntar a la misma dirección.
        """
        min_candles = max(
            self.tick_window,
            self.volume_lookback + self.tick_window,
            self.consecutive_candles,
            self.atr_period + 1,
        )
        if len(df) < min_candles:
            return None

        # Condición 1: Velocidad
        velocity_side = self._check_velocity(df)
        if velocity_side is None:
            return None

        # Condición 2: Volumen explosivo
        if not self._check_volume(df):
            return None

        # Condición 3: Dirección clara (velas consecutivas)
        candle_side = self._check_consecutive_candles(df)
        if candle_side is None:
            return None

        # Las 3 condiciones deben coincidir en dirección
        if velocity_side != candle_side:
            return None

        side = velocity_side
        sl_distance = float(getattr(CFG, "SL_DISTANCE", 6.0))
        entry = round(current_price, 2)
        msg_id = int(df.index[-1].timestamp())

        if side == "BUY":
            sl = round(entry - sl_distance, 2)
        else:
            sl = round(entry + sl_distance, 2)

        tps = self._calculate_tps(side, entry)
        return self._make_signal(side, entry, sl, tps, msg_id)