# core/services/management_finder.py
"""
Encuentra señales objetivo cuando comandos de gestión no tienen reply_to.
"""
from typing import Optional, List
from core.state import BotState
from infrastructure.logging import get_logger

logger = get_logger()


class ManagementSignalFinder:
    """
    Encuentra la señal correcta cuando un comando de gestión
    no especifica reply_to.
    """
    
    def __init__(self, state: BotState):
        self.state = state
    
    def find_target_signal(self, management_msg_id: int) -> Optional[int]:
        """
        Encuentra el signal_msg_id correcto para aplicar gestión.
        
        Estrategia:
        1. Si solo hay 1 señal OPEN → usar esa
        2. Si hay múltiples OPEN → usar la más reciente
        3. Si no hay OPEN → retornar None
        
        Args:
            management_msg_id: ID del mensaje de gestión
        
        Returns:
            signal_msg_id o None si no se puede determinar
        
        Example:
            >>> finder.find_target_signal(4629)
            4628  # Última señal OPEN
        """
        open_signals = self._get_open_signals()
        
        if not open_signals:
            logger.warning(
                "No open signals found for management command",
                management_msg_id=management_msg_id
            )
            return None
        
        if len(open_signals) == 1:
            target = open_signals[0]
            logger.info(
                "Single open signal found, using it",
                management_msg_id=management_msg_id,
                target_signal=target
            )
            return target
        
        # Múltiples señales OPEN: usar la más reciente
        # (asumiendo que msg_id más alto = más reciente)
        most_recent = max(open_signals)
        
        logger.info(
            "Multiple open signals, using most recent",
            management_msg_id=management_msg_id,
            open_signals=open_signals,
            selected=most_recent
        )
        
        return most_recent
    
    def _get_open_signals(self) -> List[int]:
        """
        Obtiene lista de signal_msg_ids con splits activos (OPEN o PENDING).
        
        Returns:
            Lista de msg_ids con posiciones activas
        """
        open_signals = []
        
        for msg_id, sig_state in self.state.signals.items():
            # Verificar si tiene al menos un split OPEN o PENDING
            has_active = any(
                split.status in ("OPEN", "PENDING")
                for split in sig_state.splits
            )
            
            if has_active:
                open_signals.append(msg_id)
        
        return open_signals
    
    def should_prompt_user(self, management_msg_id: int) -> bool:
        """
        Determina si se debe pedir al usuario que especifique
        a qué señal aplicar el comando.
        
        Args:
            management_msg_id: ID del mensaje de gestión
        
        Returns:
            True si hay ambigüedad y debe pedir clarificación
        """
        open_signals = self._get_open_signals()
        
        # Si no hay señales abiertas, no hay ambigüedad (simplemente falla)
        if not open_signals:
            return False
        
        # Si hay 1 sola, no hay ambigüedad
        if len(open_signals) == 1:
            return False
        
        # Si hay múltiples, por defecto usar la más reciente
        # pero podríamos pedir confirmación
        # Por ahora: NO pedir, usar la más reciente automáticamente
        return False
    
    def get_signal_info_for_prompt(self) -> List[dict]:
        """
        Obtiene información de señales activas para mostrar al usuario.
        
        Útil si se decide implementar confirmación interactiva.
        
        Returns:
            Lista de dicts con info de cada señal activa
        """
        info = []
        
        for msg_id, sig_state in self.state.signals.items():
            active_splits = [
                split for split in sig_state.splits
                if split.status in ("OPEN", "PENDING")
            ]
            
            if not active_splits:
                continue
            
            signal = sig_state.signal
            
            info.append({
                "msg_id": msg_id,
                "side": signal.side,
                "entry": signal.entry,
                "active_splits": len(active_splits),
                "pending_count": sum(1 for s in active_splits if s.status == "PENDING"),
                "open_count": sum(1 for s in active_splits if s.status == "OPEN"),
            })
        
        return info
    
    def validate_target(self, target_msg_id: int) -> bool:
        """
        Valida que el target tiene splits activos.
        
        Args:
            target_msg_id: ID de la señal objetivo
        
        Returns:
            True si es un target válido
        """
        sig_state = self.state.get_signal(target_msg_id)
        
        if not sig_state:
            return False
        
        has_active = any(
            split.status in ("OPEN", "PENDING")
            for split in sig_state.splits
        )
        
        return has_active