# core/monitoring/position_watcher.py
"""
Watcher para posiciones abiertas.
Actualmente placeholder - la gestión la hace ManagementApplier.
"""
from .base_watcher import BaseWatcher


class PositionWatcher(BaseWatcher):
    """
    Monitorea posiciones abiertas.
    
    Actualmente es un placeholder.
    La gestión (BE, MOVE_SL, CLOSE) la hace ManagementApplier.
    """
    
    def watch_cycle(self) -> None:
        """Ciclo de monitoreo de posiciones."""
        # Placeholder - la gestión la hace ManagementApplier
        # Aquí podrías agregar lógica adicional como:
        # - Detectar posiciones cerradas por broker
        # - Tracking de P&L
        # - Alertas de drawdown
        pass