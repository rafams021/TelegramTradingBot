# autonomous/__init__.py
"""
Módulo de trading autónomo.

Interfaz pública:
    - AutonomousTrader: Loop principal de scanning y ejecución

Uso:
    from autonomous import AutonomousTrader

    trader = AutonomousTrader(scan_interval=300)
    await trader.run()
"""
from .trader import AutonomousTrader

__all__ = ["AutonomousTrader"]