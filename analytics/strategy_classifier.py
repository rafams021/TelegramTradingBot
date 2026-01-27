# analytics/strategy_classifier.py
"""
Clasificador de estrategias de trading.

Identifica patrones en las señales para categorizar en:
- SCALPING: TPs pequeños (<10 pips)
- INTRADAY: TPs medianos (10-50 pips)
- SWING: TPs grandes (50+ pips)
- BREAKOUT: Entry lejos del precio actual
- PULLBACK: Entry cerca del precio actual
"""
from __future__ import annotations

from typing import Optional
from datetime import datetime


class StrategyClassifier:
    """Clasifica señales en estrategias conocidas."""
    
    # Thresholds (ajustables según observación)
    SCALPING_MAX_PIPS = 10.0
    INTRADAY_MAX_PIPS = 50.0
    BREAKOUT_MIN_DISTANCE = 5.0  # Entry > 5 pips del precio actual
    
    @classmethod
    def classify_by_tp_distance(cls, signal_entry: float, tps: list[float]) -> str:
        """
        Clasifica por distancia del TP.
        
        Args:
            signal_entry: Precio de entrada de la señal
            tps: Lista de take profits
            
        Returns:
            "SCALPING" | "INTRADAY" | "SWING"
        """
        if not tps:
            return "UNKNOWN"
        
        # Usar primer TP para clasificar
        first_tp = tps[0]
        distance = abs(first_tp - signal_entry)
        
        if distance < cls.SCALPING_MAX_PIPS:
            return "SCALPING"
        elif distance < cls.INTRADAY_MAX_PIPS:
            return "INTRADAY"
        else:
            return "SWING"
    
    @classmethod
    def classify_by_entry_distance(
        cls,
        signal_entry: float,
        current_price: float
    ) -> str:
        """
        Clasifica por distancia del entry al precio actual.
        
        Returns:
            "BREAKOUT" | "PULLBACK"
        """
        distance = abs(current_price - signal_entry)
        
        if distance >= cls.BREAKOUT_MIN_DISTANCE:
            return "BREAKOUT"
        else:
            return "PULLBACK"
    
    @classmethod
    def classify_by_session(cls, timestamp: str) -> str:
        """
        Clasifica por sesión de trading.
        
        Sessions:
        - ASIAN: 00:00 - 09:00 UTC
        - EUROPEAN: 07:00 - 16:00 UTC
        - US: 13:00 - 22:00 UTC
        
        Returns:
            "ASIAN" | "EUROPEAN" | "US" | "OVERLAP"
        """
        try:
            dt = datetime.fromisoformat(timestamp)
            hour = dt.hour
            
            # Overlaps
            if 7 <= hour < 9:
                return "ASIAN_EUROPEAN_OVERLAP"
            elif 13 <= hour < 16:
                return "EUROPEAN_US_OVERLAP"
            
            # Main sessions
            if 0 <= hour < 9:
                return "ASIAN"
            elif 9 <= hour < 13:
                return "EUROPEAN"
            elif 13 <= hour < 22:
                return "US"
            else:
                return "ASIAN"
                
        except Exception:
            return "UNKNOWN"
    
    @classmethod
    def calculate_risk_reward(
        cls,
        entry: float,
        tp: float,
        sl: float
    ) -> Optional[float]:
        """
        Calcula risk/reward ratio.
        
        Returns:
            Ratio (e.g., 2.0 significa reward es 2x el risk)
        """
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        
        if risk == 0:
            return None
        
        return reward / risk
    
    @classmethod
    def classify_signal(
        cls,
        entry: float,
        tps: list[float],
        sl: float,
        current_price: float,
        timestamp: str,
    ) -> dict:
        """
        Clasificación completa de una señal.
        
        Returns:
            Dict con todas las clasificaciones
        """
        return {
            "style": cls.classify_by_tp_distance(entry, tps),
            "type": cls.classify_by_entry_distance(entry, current_price),
            "session": cls.classify_by_session(timestamp),
            "risk_reward": cls.calculate_risk_reward(entry, tps[0] if tps else entry, sl),
        }