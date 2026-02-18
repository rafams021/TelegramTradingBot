"""
Machine Learning module for TelegramTradingBot - Phase 2

Este módulo implementa ML para mejorar win rate de ~50% a 58-68%.

Componentes:
- feature_extractor: Extrae 20+ features de cada trade
- model_trainer: Entrena LightGBM con datos históricos  
- predictor: Usa modelo entrenado en live trading
"""

__version__ = "2.0.0"