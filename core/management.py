# core/management.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import re

import core.logger as logger
from core.state import BotState

@dataclass(frozen=True)
class ManagementAction:
    kind: str  # NONE / BE / CLOSE_TP_AT / CLOSE_ALL_AT
    tp_index: Optional[int] = None
    price: Optional[float] = None

_BE_RE = re.compile(r"\bBE\b|MOVER\s+EL\s+STOP\s*LOSS\s+A\s+BE|CERRAR\s+A\s+BE", re.I)
_CLOSE_TP_RE = re.compile(r"CERRAR\s+EL\s+TP\s*(\d+)\s*A\s*(\d+(?:\.\d+)?)", re.I)
_CLOSE_ALL_RE = re.compile(r"CERRAR\s+AHORA\s+A\s*(\d+(?:\.\d+)?)", re.I)

def classify_management(text: str) -> ManagementAction:
    t = text.strip()

    m = _CLOSE_TP_RE.search(t)
    if m:
        return ManagementAction(kind="CLOSE_TP_AT", tp_index=int(m.group(1)), price=float(m.group(2)))

    m = _CLOSE_ALL_RE.search(t)
    if m:
        return ManagementAction(kind="CLOSE_ALL_AT", price=float(m.group(1)))

    if _BE_RE.search(t):
        return ManagementAction(kind="BE")

    return ManagementAction(kind="NONE")

def apply_management(state: BotState, msg_id: int, reply_to: Optional[int], mg: ManagementAction) -> None:
    if reply_to is None:
        logger.log({"event": "MGMT_IGNORED_NO_REPLY", "msg_id": msg_id, "kind": mg.kind})
        return

    sig_state = state.get_signal(reply_to)
    if sig_state is None:
        if mg.kind == "BE":
            logger.log({"event": "BE_IGNORED_NO_SIGNAL_STATE", "msg_id": msg_id, "reply_to": reply_to})
        else:
            logger.log({"event": "MGMT_IGNORED_NO_SIGNAL_STATE", "msg_id": msg_id, "reply_to": reply_to, "kind": mg.kind})
        return

    if mg.kind == "BE":
        logger.log({"event": "BE_DETECTED", "msg_id": msg_id, "reply_to": reply_to})
        for sp in sig_state.splits:
            if sp.be_done:
                continue
            sp.be_armed = True
            logger.log({
                "event": "BE_ARMED",
                "signal_msg_id": reply_to,
                "split": sp.split_index,
                "status": sp.status,
                "order_ticket": sp.order_ticket,
                "position_ticket": sp.position_ticket,
            })
        return

    if mg.kind == "CLOSE_TP_AT":
        logger.log({"event": "CLOSE_DETECTED", "msg_id": msg_id, "reply_to": reply_to, "tp_index": mg.tp_index, "price": mg.price})
        split_idx = (mg.tp_index - 1) if mg.tp_index else None
        if split_idx is None or split_idx < 0 or split_idx >= len(sig_state.splits):
            logger.log({"event": "CLOSE_IGNORED_BAD_TP_INDEX", "msg_id": msg_id, "reply_to": reply_to, "tp_index": mg.tp_index})
            return
        sp = sig_state.splits[split_idx]
        sp.close_armed = True
        sp.close_target = mg.price
        return

    if mg.kind == "CLOSE_ALL_AT":
        logger.log({"event": "CLOSE_DETECTED", "msg_id": msg_id, "reply_to": reply_to, "price": mg.price})
        for sp in sig_state.splits:
            sp.close_armed = True
            sp.close_target = mg.price
        return
