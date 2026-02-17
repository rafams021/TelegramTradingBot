# market/strategies/__init__.py
from .breakout import BreakoutStrategy
from .reversal import ReversalStrategy
from .trend import TrendStrategy
from .momentum import MomentumStrategy    # ← agregar esta línea

__all__ = [
    "BreakoutStrategy",
    "ReversalStrategy",
    "TrendStrategy",
    "MomentumStrategy",                   # ← y esta
]
