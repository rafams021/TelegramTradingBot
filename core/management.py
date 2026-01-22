import time
import re
from dataclasses import dataclass
from typing import Optional

from core import logger
from core.state import BotState


# Ejemplos:
# "CERRAR AHORA A 4856"
# "CERRAR A 4850"
_re_close_at = re.compile(r"\bCERRAR\b(?:\s+AHORA)?\s+\bA\b\s*(\d+(?:\.\d+)?)", re.IGNORECASE)


@dataclass
class ManagementCmd:
    kind: str  # "NONE", "BE", "CLOSE", "CLOSE_AT"
    price: Optional[float] = None


def classify_management(text: str) -> ManagementCmd:
    t = (text or "").strip()
    if not t:
        return ManagementCmd("NONE", None)

    up = t.upper()

    # BE: cualquier mensaje que contenga "BE"
    if "BE" in up:
        return ManagementCmd("BE", None)

    m = _re_close_at.search(t)
    if m:
        try:
            return ManagementCmd("CLOSE_AT", float(m.group(1)))
        except ValueError:
            return ManagementCmd("NONE", None)

    if "CERRAR" in up:
        return ManagementCmd("CLOSE", None)

    return ManagementCmd("NONE", None)


def apply_management(state: BotState, msg_id: int, reply_to: Optional[int], mg: ManagementCmd) -> None:
    """
    Aplica management SOLO si viene como reply_to a una señal existente en memoria.
    - BE: arma be_armed=True para splits OPEN o PENDING.
    - CLOSE_AT: arma close_armed=True y target.
    - CLOSE: por ahora lo tratamos como CLOSE_AT a precio de mercado (lo dejamos como pendiente si quieres).
    """
    if mg.kind == "NONE":
        return

    if reply_to is None:
        logger.log({"event": f"{mg.kind}_IGNORED_NO_REPLY", "msg_id": msg_id})
        return

    sig = state.get_signal(reply_to)
    if sig is None:
        logger.log({"event": f"{mg.kind}_IGNORED_NO_SIGNAL_STATE", "msg_id": msg_id, "reply_to": reply_to})
        return

    now = time.time()

    if mg.kind == "BE":
        logger.log({"event": "BE_DETECTED", "msg_id": msg_id, "reply_to": reply_to})
        for s in sig.splits:
            # solo tiene sentido armar para PENDING/OPEN
            if s.status in ("PENDING", "OPEN") and not s.be_done:
                s.be_armed = True
                s.be_requested_ts = now
                logger.log(
                    {
                        "event": "BE_ARMED",
                        "signal_msg_id": reply_to,
                        "split": s.split_index,
                        "status": s.status,
                        "order_ticket": s.order_ticket,
                        "position_ticket": s.position_ticket,
                    }
                )
        return

    if mg.kind == "CLOSE_AT":
        logger.log({"event": "CLOSE_DETECTED", "msg_id": msg_id, "reply_to": reply_to, "target": mg.price})
        for s in sig.splits:
            if s.status in ("PENDING", "OPEN") and not s.close_done:
                s.close_target = mg.price
                s.close_armed = True
                s.close_requested_ts = now
        return

    if mg.kind == "CLOSE":
        logger.log({"event": "CLOSE_DETECTED", "msg_id": msg_id, "reply_to": reply_to, "target": None})
        # Política mínima: si está PENDING, cancelarlo; si está OPEN, armamos close_armed sin target (futuro).
        for s in sig.splits:
            if s.status == "PENDING":
                s.close_armed = True  # watcher lo interpreta como cancel by close (si lo implementas ahí)
            elif s.status == "OPEN":
                s.close_armed = True
                s.close_requested_ts = now
        return

