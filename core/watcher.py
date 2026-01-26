# core/watcher.py
"""
REFACTORIZADO EN FASE 5:
- Lógica movida a core/monitoring/
- Este archivo mantiene backward compatibility

Watchers separados:
- PendingOrderWatcher: Monitorea órdenes pendientes
- ManagementApplier: Aplica BE/MOVE_SL/CLOSE
"""
import asyncio
import threading

from core.state import BotState
from core.monitoring import PendingOrderWatcher, ManagementApplier


async def run_watcher(state: BotState, poll_interval: float = 1.0) -> None:
    """
    Función principal del watcher (backward compatible).
    
    Inicia watchers en threads separados:
    - PendingOrderWatcher: Cancela órdenes si TP alcanzado o timeout
    - ManagementApplier: Aplica BE, MOVE_SL, CLOSE_AT
    
    Args:
        state: Estado del bot
        poll_interval: Intervalo de polling en segundos
    """
    from infrastructure.logging import get_logger
    logger = get_logger()
    
    logger.info("Watcher iniciando", poll_interval=poll_interval)
    
    # Crear watchers
    pending_watcher = PendingOrderWatcher(state, poll_interval)
    management_applier = ManagementApplier(state, poll_interval)
    
    # Iniciar en threads separados
    pending_thread = threading.Thread(
        target=pending_watcher.start,
        daemon=True,
        name="PendingWatcher"
    )
    
    management_thread = threading.Thread(
        target=management_applier.start,
        daemon=True,
        name="ManagementApplier"
    )
    
    pending_thread.start()
    management_thread.start()
    
    logger.info(
        "Watcher threads iniciados",
        threads=[pending_thread.name, management_thread.name]
    )
    
    # Mantener la coroutine viva y monitorear threads
    while True:
        await asyncio.sleep(60)
        
        # Reiniciar threads si mueren
        if not pending_thread.is_alive():
            logger.warning("PendingWatcher murió, reiniciando...")
            pending_thread = threading.Thread(
                target=pending_watcher.start,
                daemon=True,
                name="PendingWatcher"
            )
            pending_thread.start()
        
        if not management_thread.is_alive():
            logger.warning("ManagementApplier murió, reiniciando...")
            management_thread = threading.Thread(
                target=management_applier.start,
                daemon=True,
                name="ManagementApplier"
            )
            management_thread.start()


# Backward compatibility exports
__all__ = [
    "run_watcher",
]