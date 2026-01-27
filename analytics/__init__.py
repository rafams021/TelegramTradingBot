# analytics/__init__.py
"""
Sistema de analytics y métricas del trading bot.

Exports:
    - MetricsTracker: Tracking principal
    - StrategyClassifier: Clasificación de estrategias
    - get_metrics_tracker: Singleton del tracker
"""

from .metrics_tracker import MetricsTracker, get_metrics_tracker

__all__ = [
    "MetricsTracker",
    "get_metrics_tracker",
]