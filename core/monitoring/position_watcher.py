# core/monitoring/position_watcher.py
"""
Watcher para posiciones abiertas.

FASE B - LIMPIEZA: Implementado watch_cycle().
Detecta posiciones cerradas externamente (SL hit, TP hit, cierre manual
desde MT5) y sincroniza el BotState para que no queden posiciones
fantasma con status OPEN indefinidamente.
"""
import time
from adapters import mt5_client as mt5c
from .base_watcher import BaseWatcher


class PositionWatcher(BaseWatcher):
    """
    Monitorea posiciones abiertas y detecta cierres externos.

    Responsabilidades:
    - Consultar MT5 cada ciclo por posiciones abiertas del bot
    - Comparar con el BotState interno
    - Si una posición OPEN ya no existe en MT5 → marcarla CLOSED
    - Loggear el evento con todos los datos disponibles
    """

    def watch_cycle(self) -> None:
        """
        Ciclo de monitoreo de posiciones abiertas.

        Lógica:
        1. Obtener tickets activos en MT5 (solo del bot por MAGIC)
        2. Recorrer splits con status OPEN en BotState
        3. Si el ticket ya no está en MT5 → CLOSED externamente
        """
        # Obtener tickets reales en MT5 ahora mismo
        live_positions = mt5c.positions_get_all()
        live_tickets = {
            int(getattr(p, "ticket", 0))
            for p in live_positions
        }

        # Recorrer todos los splits OPEN en el estado interno
        for msg_id, sig_state in list(self.state.signals.items()):
            for split in sig_state.splits:
                if split.status != "OPEN":
                    continue

                if not split.position_ticket:
                    continue

                ticket = int(split.position_ticket)

                # Si el ticket ya no existe en MT5 → cerrado externamente
                if ticket not in live_tickets:
                    self._handle_external_close(split, msg_id, ticket)

    def _handle_external_close(self, split, msg_id: int, ticket: int) -> None:
        """
        Marca un split como CLOSED y loggea el evento.

        Se llama cuando MT5 ya no tiene la posición pero el BotState
        todavía la tiene como OPEN. Puede ser por:
        - SL hit
        - TP hit (el broker cerró automáticamente)
        - Cierre manual desde la plataforma MT5
        - Margin call

        Args:
            split: SplitState a marcar como cerrado
            msg_id: ID del mensaje de señal (para logging)
            ticket: Ticket de la posición cerrada
        """
        split.status = "CLOSED"
        split.close_done = True
        closed_ts = time.time()

        self.logger.event(
            "POSITION_CLOSED_EXTERNAL",
            signal_msg_id=msg_id,
            split=split.split_index,
            ticket=ticket,
            side=split.side,
            entry=split.entry,
            tp=split.tp,
            sl=split.sl,
            open_price=split.open_price,
            closed_ts=closed_ts,
        )