# core/monitoring/pending_watcher.py
"""
Watcher para órdenes pendientes.
"""
import time
import config as CFG
from adapters import mt5_client as mt5c
from core.rules import tp_reached
from .base_watcher import BaseWatcher


class PendingOrderWatcher(BaseWatcher):
    """Monitorea órdenes pendientes y las cancela si es necesario."""
    
    def watch_cycle(self) -> None:
        """Monitorea todas las órdenes pendientes."""
        tick = mt5c.symbol_tick()
        if not tick:
            return
        
        for msg_id, sig_state in list(self.state.signals.items()):
            for split in sig_state.splits:
                if split.status != "PENDING" or not split.order_ticket:
                    continue
                
                # Verificar si existe la orden
                orders = mt5c.orders_get()
                order_found = any(o.ticket == split.order_ticket for o in orders) if orders else False
                
                if not order_found:
                    # Orden ejecutada o cancelada
                    split.status = "OPEN"
                    split.open_ts = time.time()
                    self.logger.event(
                        "PENDING_FILLED_DETECTED",
                        signal_msg_id=msg_id,
                        split=split.split_index,
                        ticket=split.order_ticket,
                    )
                    continue
                
                # Cancelar si TP alcanzado
                side = split.side or self._infer_side(split.entry, split.tp)
                if tp_reached(side, split.tp, tick.bid, tick.ask):
                    self._cancel_order(split, msg_id, "TP_REACHED", tick)
                    continue
                
                # Cancelar por timeout
                age_s = time.time() - (split.pending_created_ts or time.time())
                timeout = float(getattr(CFG, "PENDING_TIMEOUT_MIN", 10) or 10) * 60.0
                if age_s > timeout:
                    self._cancel_order(split, msg_id, "TIMEOUT", tick)
    
    def _infer_side(self, entry: float, tp: float) -> str:
        """Infiere lado si no está guardado."""
        return "BUY" if float(tp) > float(entry) else "SELL"
    
    def _cancel_order(self, split, msg_id: int, reason: str, tick) -> None:
        """Cancela una orden pendiente."""
        req, res = mt5c.cancel_order(split.order_ticket)
        split.status = "CANCELED"
        
        self.logger.event(
            f"PENDING_CANCELED_{reason}",
            signal_msg_id=msg_id,
            split=split.split_index,
            ticket=split.order_ticket,
            tp=split.tp,
            bid=tick.bid,
            ask=tick.ask,
            result=str(res),
        )