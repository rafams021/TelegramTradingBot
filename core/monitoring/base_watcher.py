# core/monitoring/base_watcher.py
"""
Clase base para watchers.
"""
from abc import ABC, abstractmethod
import time

from infrastructure.logging import get_logger
from core.state import BotState


class BaseWatcher(ABC):
    """
    Clase base para todos los watchers.
    
    Proporciona:
    - Logger compartido
    - Loop de polling
    - Control de running state
    """
    
    def __init__(self, state: BotState, poll_interval: float = 1.0):
        """
        Args:
            state: Estado del bot
            poll_interval: Intervalo de polling en segundos
        """
        self.state = state
        self.poll_interval = poll_interval
        self.logger = get_logger()
        self.running = False
    
    def start(self) -> None:
        """Inicia el watcher (blocking)."""
        self.running = True
        self.logger.info(f"{self.__class__.__name__} iniciado")
        
        while self.running:
            try:
                self.watch_cycle()
            except Exception as ex:
                self.logger.error(
                    f"Error en {self.__class__.__name__}",
                    exc_info=True,
                    error=str(ex),
                )
            
            time.sleep(self.poll_interval)
    
    def stop(self) -> None:
        """Detiene el watcher."""
        self.running = False
        self.logger.info(f"{self.__class__.__name__} detenido")
    
    @abstractmethod
    def watch_cycle(self) -> None:
        """
        Ciclo de monitoreo (debe ser implementado por subclases).
        
        Este método se ejecuta cada poll_interval segundos.
        """
        pass