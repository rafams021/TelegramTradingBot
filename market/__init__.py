# market/__init__.py
"""
Módulo de análisis de mercado autónomo.

Interfaz pública:
    - MarketAnalyzer: Orquestador principal

Uso:
    from market import MarketAnalyzer

    analyzer = MarketAnalyzer()
    signals = analyzer.scan()
"""
from .analyzer import MarketAnalyzer

__init__ = ["MarketAnalyzer"]