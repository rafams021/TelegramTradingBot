# core/monitoring/management_applier.py
"""
Aplica comandos de gestión a posiciones abiertas.
"""
import config as CFG
from adapters import mt5_client as mt5c
from core.rules import be_allowed, close_at_triggered, min_stop_distance
from .base_watcher import BaseWatcher


class ManagementApplier(BaseWatcher):
    """
    Aplica gestión a posiciones OPEN:
    - Break Even (BE)
    - Move SL
    - Close At
    """
    
    def watch_cycle(self) -> None:
        """Aplica gestión a todas las posiciones que la tengan armada."""
        tick = mt5c.symbol_tick()
        if not tick:
            return
        
        constraints = mt5c.symbol_constraints()
        min_dist = min_stop_distance(constraints)
        
        for msg_id, sig_state in list(self.state.signals.items()):
            for split in sig_state.splits:
                if split.status != "OPEN" or not split.position_ticket:
                    continue
                
                # 1. Break Even
                if split.be_armed and not split.be_done:
                    self._apply_be(split, msg_id, tick, min_dist)
                
                # 2. Move SL
                if split.sl_move_armed and not split.sl_move_done:
                    self._apply_move_sl(split, msg_id, tick, min_dist)
                
                # 3. Close At
                if split.close_armed and not split.close_done:
                    self._apply_close_at(split, msg_id, tick)
    
    def _apply_be(self, split, msg_id: int, tick, min_dist: float) -> None:
        """Aplica break even."""
        be_price = split.open_price or split.entry
        be_price = mt5c.normalize_price(be_price)
        
        if not be_allowed(split.side, be_price, tick.bid, tick.ask, min_dist):
            return
        
        # Obtener TP actual
        pos = mt5c.position_get(split.position_ticket)
        tp_current = float(getattr(pos, "tp", 0) or 0) if pos else 0
        tp_use = tp_current if tp_current > 0 else split.tp
        
        req, res = mt5c.modify_sl(split.position_ticket, be_price, tp_use)
        
        if res and getattr(res, "retcode", None) == 10009:
            split.be_done = True
            split.be_armed = False
            self.logger.event(
                "BE_APPLIED",
                signal_msg_id=msg_id,
                split=split.split_index,
                ticket=split.position_ticket,
                be_price=be_price,
            )
        else:
            self.logger.warning(
                "BE_APPLY_FAILED",
                signal_msg_id=msg_id,
                split=split.split_index,
                result=str(res),
            )
    
    def _apply_move_sl(self, split, msg_id: int, tick, min_dist: float) -> None:
        """Aplica movimiento de SL."""
        new_sl = mt5c.normalize_price(split.sl)
        
        # Obtener TP actual
        pos = mt5c.position_get(split.position_ticket)
        if not pos:
            return
        
        tp_current = float(getattr(pos, "tp", 0) or 0)
        
        req, res = mt5c.modify_sltp(split.position_ticket, new_sl, tp_current)
        
        if res and getattr(res, "retcode", None) == 10009:
            split.sl_move_done = True
            split.sl_move_armed = False
            self.logger.event(
                "MOVE_SL_APPLIED",
                signal_msg_id=msg_id,
                split=split.split_index,
                ticket=split.position_ticket,
                new_sl=new_sl,
            )
        else:
            self.logger.warning(
                "MOVE_SL_FAILED",
                signal_msg_id=msg_id,
                split=split.split_index,
                result=str(res),
            )
    
    def _apply_close_at(self, split, msg_id: int, tick) -> None:
        """Aplica cierre en target."""
        # Si no hay target, cerrar inmediatamente
        if split.close_target is None:
            triggered = True
        else:
            buffer = float(getattr(CFG, "CLOSE_AT_BUFFER", 0) or 0)
            triggered = close_at_triggered(
                split.side,
                split.close_target,
                tick.bid,
                tick.ask,
                buffer
            )
        
        if not triggered:
            return
        
        vol = float(getattr(CFG, "VOLUME_PER_ORDER", 0.01))
        req, res = mt5c.close_position(split.position_ticket, split.side, vol)
        
        if res and getattr(res, "retcode", None) == 10009:
            split.close_done = True
            split.close_armed = False
            split.status = "CLOSED"
            self.logger.event(
                "CLOSE_AT_APPLIED",
                signal_msg_id=msg_id,
                split=split.split_index,
                ticket=split.position_ticket,
                target=split.close_target,
            )
        else:
            self.logger.warning(
                "CLOSE_AT_FAILED",
                signal_msg_id=msg_id,
                split=split.split_index,
                result=str(res),
            )