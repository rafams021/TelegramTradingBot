# core/services/management_service.py
"""
Servicio de gestión de posiciones.
Aplica comandos de gestión (BE, MOVE_SL, CLOSE) a posiciones.
"""
from __future__ import annotations

from typing import List, Optional

from infrastructure.logging import get_logger
from core.domain.enums import ManagementType
from core.parsers.management_parser import ManagementAction
from core.state import BotState, SplitState


class ManagementService:
    """
    Servicio para aplicar comandos de gestión a posiciones.
    
    Responsabilidades:
    - Armar break even
    - Armar movimiento de SL
    - Armar cierre en TP específico
    - Armar cierre de todas las posiciones
    """
    
    def __init__(self, state: BotState):
        """
        Args:
            state: Estado global del bot
        """
        self.state = state
        self.logger = get_logger()
    
    def apply(
        self,
        action: ManagementAction,
        msg_id: int,
        reply_to: Optional[int]
    ) -> bool:
        """
        Aplica un comando de gestión.
        
        Args:
            action: Acción de gestión parseada
            msg_id: ID del mensaje de comando
            reply_to: ID del mensaje de señal original
        
        Returns:
            True si se aplicó correctamente
        """
        # Validar que hay reply_to
        if reply_to is None:
            self.logger.event(
                "MANAGEMENT_IGNORED_NO_REPLY_TO",
                msg_id=msg_id,
                kind=action.type.value,
            )
            return False
        
        # Obtener señal
        sig_state = self.state.signals.get(reply_to)
        if not sig_state:
            self.logger.event(
                "MANAGEMENT_IGNORED_NO_SIGNAL",
                msg_id=msg_id,
                reply_to=reply_to,
                kind=action.type.value,
            )
            return False
        
        # Aplicar según tipo
        if action.type == ManagementType.BE:
            return self._apply_be(sig_state.splits, msg_id, reply_to)
        
        elif action.type == ManagementType.MOVE_SL:
            return self._apply_move_sl(
                sig_state.splits,
                action.price,
                msg_id,
                reply_to
            )
        
        elif action.type == ManagementType.CLOSE_TP_AT:
            return self._apply_close_tp(
                sig_state.splits,
                action.tp_index,
                sig_state.signal.tps,
                msg_id,
                reply_to
            )
        
        elif action.type == ManagementType.CLOSE_ALL_AT:
            return self._apply_close_all(sig_state.splits, msg_id, reply_to)
        
        return False
    
    # ==========================================
    # Métodos Privados
    # ==========================================
    
    def _apply_be(
        self,
        splits: List[SplitState],
        msg_id: int,
        reply_to: int
    ) -> bool:
        """Arma break even en posiciones OPEN."""
        self.logger.event(
            "BE_DETECTED",
            msg_id=msg_id,
            reply_to=reply_to,
        )
        
        count = 0
        for sp in splits:
            if sp.status == "OPEN":
                sp.be_armed = True
                sp.be_done = False
                count += 1
                
                self.logger.event(
                    "BE_ARMED",
                    msg_id=reply_to,
                    split_id=getattr(sp, 'split_id', f'split_{sp.split_index}'),
                )
        
        self.logger.info(
            "Break Even armado",
            reply_to=reply_to,
            positions=count,
        )
        
        return count > 0
    
    def _apply_move_sl(
        self,
        splits: List[SplitState],
        new_sl: Optional[float],
        msg_id: int,
        reply_to: int
    ) -> bool:
        """Arma movimiento de SL."""
        if new_sl is None:
            self.logger.warning(
                "MOVE_SL sin precio",
                msg_id=msg_id,
                reply_to=reply_to,
            )
            return False
        
        self.logger.event(
            "MOVE_SL_DETECTED",
            msg_id=msg_id,
            reply_to=reply_to,
            price=new_sl,
        )
        
        count = 0
        for sp in splits:
            # Actualizar SL deseado (watcher lo aplicará)
            sp.sl = float(new_sl)
            sp.sl_move_armed = True
            sp.sl_move_done = False
            count += 1
            
            self.logger.event(
                "MOVE_SL_ARMED",
                msg_id=reply_to,
                split_id=getattr(sp, 'split_id', f'split_{sp.split_index}'),
                price=new_sl,
            )
        
        self.logger.info(
            "Move SL armado",
            reply_to=reply_to,
            new_sl=new_sl,
            positions=count,
        )
        
        return count > 0
    
    def _apply_close_tp(
        self,
        splits: List[SplitState],
        tp_index: Optional[int],
        signal_tps: List[float],
        msg_id: int,
        reply_to: int
    ) -> bool:
        """Arma cierre en TP específico."""
        if tp_index is None or tp_index <= 0:
            self.logger.event(
                "CLOSE_TP_INVALID_INDEX",
                msg_id=msg_id,
                reply_to=reply_to,
                tp_index=tp_index,
            )
            return False
        
        self.logger.event(
            "CLOSE_TP_DETECTED",
            msg_id=msg_id,
            reply_to=reply_to,
            tp_index=tp_index,
        )
        
        # Obtener precio del TP
        tp_price = None
        if (tp_index - 1) < len(signal_tps):
            tp_price = float(signal_tps[tp_index - 1])
        
        count = 0
        for sp in splits:
            if sp.status == "OPEN":
                sp.close_armed = True
                sp.close_done = False
                sp.close_target = tp_price
                count += 1
                
                self.logger.event(
                    "CLOSE_TP_ARMED",
                    msg_id=reply_to,
                    split_id=getattr(sp, 'split_id', f'split_{sp.split_index}'),
                    target=tp_price,
                )
        
        self.logger.info(
            "Close TP armado",
            reply_to=reply_to,
            tp_index=tp_index,
            tp_price=tp_price,
            positions=count,
        )
        
        return count > 0
    
    def _apply_close_all(
        self,
        splits: List[SplitState],
        msg_id: int,
        reply_to: int
    ) -> bool:
        """Arma cierre de todas las posiciones."""
        self.logger.event(
            "CLOSE_ALL_DETECTED",
            msg_id=msg_id,
            reply_to=reply_to,
        )
        
        count = 0
        for sp in splits:
            if sp.status == "OPEN":
                sp.close_armed = True
                sp.close_done = False
                sp.close_target = None  # None = cerrar inmediatamente
                count += 1
                
                self.logger.event(
                    "CLOSE_ALL_ARMED",
                    msg_id=reply_to,
                    split_id=getattr(sp, 'split_id', f'split_{sp.split_index}'),
                )
        
        self.logger.info(
            "Close All armado",
            reply_to=reply_to,
            positions=count,
        )
        
        return count > 0