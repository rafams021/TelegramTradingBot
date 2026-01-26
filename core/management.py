# core/management.py
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional

from core.logger import Logger
from core.state import BotState, now_iso


@dataclass
class ManagementAction:
    kind: str  # NONE / BE / MOVE_SL / CLOSE_TP_AT / CLOSE_ALL_AT
    price: Optional[float] = None
    tp_index: Optional[int] = None


_BE_RE = re.compile(r"\bBE\b|MOVER\s+EL\s+STOP\s*LOSS\s+A\s+BE|CERRAR\s+A\s+BE", re.I)
_MOVE_SL_RE = re.compile(r"MOVER\s+EL\s+(?:SL|STOP\s*LOSS)\s+A\s*(\d+(?:\.\d+)?)", re.I)
_CLOSE_TP_RE = re.compile(r"\bCERRAR\b.*\bTP\s*(\d+)\b", re.I)
_CLOSE_ALL_RE = re.compile(r"\bCERRAR\b.*\bTODO\b|\bCLOSE\s+ALL\b", re.I)


def classify_management(text: str) -> ManagementAction:
    t = (text or "").strip()
    if not t:
        return ManagementAction(kind="NONE")

    m = _MOVE_SL_RE.search(t)
    if m:
        try:
            return ManagementAction(kind="MOVE_SL", price=float(m.group(1)))
        except Exception:
            return ManagementAction(kind="NONE")

    if _BE_RE.search(t):
        return ManagementAction(kind="BE")

    m = _CLOSE_TP_RE.search(t)
    if m:
        try:
            idx = int(m.group(1))
            return ManagementAction(kind="CLOSE_TP_AT", tp_index=idx)
        except Exception:
            return ManagementAction(kind="NONE")

    if _CLOSE_ALL_RE.search(t):
        return ManagementAction(kind="CLOSE_ALL_AT")

    return ManagementAction(kind="NONE")


def apply_management(state: BotState, msg_id: int, reply_to: Optional[int], mg: ManagementAction) -> None:
    logger = Logger()

    if reply_to is None:
        logger.log({"event": "MANAGEMENT_IGNORED_NO_REPLY_TO", "msg_id": msg_id, "kind": mg.kind})
        return

    sig_state = state.signals.get(reply_to)
    if not sig_state:
        logger.log({"event": "MANAGEMENT_IGNORED_NO_SIGNAL", "msg_id": msg_id, "reply_to": reply_to, "kind": mg.kind})
        return

    if mg.kind == "BE":
        logger.log({"event": "BE_DETECTED", "msg_id": msg_id, "reply_to": reply_to})
        for sp in sig_state.splits:
            if sp.status == "OPEN":
                sp.be_armed = True
                sp.be_done = False
                logger.log({"event": "BE_ARMED", "msg_id": reply_to, "split_id": sp.split_id, "ts": now_iso()})
        return

    if mg.kind == "MOVE_SL":
        logger.log({"event": "MOVE_SL_DETECTED", "msg_id": msg_id, "reply_to": reply_to, "price": mg.price})
        for sp in sig_state.splits:
            # Guardamos el SL deseado en el split; watcher lo aplicará al ticket real cuando exista.
            sp.sl = float(mg.price) if mg.price is not None else sp.sl
            sp.sl_move_armed = True
            sp.sl_move_done = False
            logger.log({"event": "MOVE_SL_ARMED", "msg_id": reply_to, "split_id": sp.split_id, "price": mg.price, "ts": now_iso()})
        return

    if mg.kind == "CLOSE_TP_AT":
        logger.log({"event": "CLOSE_TP_DETECTED", "msg_id": msg_id, "reply_to": reply_to, "tp_index": mg.tp_index})
        idx = int(mg.tp_index or 0)
        if idx <= 0:
            logger.log({"event": "CLOSE_TP_INVALID_INDEX", "msg_id": msg_id, "reply_to": reply_to, "tp_index": mg.tp_index})
            return
        for sp in sig_state.splits:
            if sp.status == "OPEN":
                sp.close_armed = True
                sp.close_done = False
                # Cierra cuando se alcance el TP(idx) del signal original (si existe)
                if idx - 1 < len(sig_state.signal.tps):
                    sp.close_target = float(sig_state.signal.tps[idx - 1])
                logger.log({"event": "CLOSE_TP_ARMED", "msg_id": reply_to, "split_id": sp.split_id, "target": sp.close_target, "ts": now_iso()})
        return

    if mg.kind == "CLOSE_ALL_AT":
        logger.log({"event": "CLOSE_ALL_DETECTED", "msg_id": msg_id, "reply_to": reply_to})
        for sp in sig_state.splits:
            if sp.status == "OPEN":
                sp.close_armed = True
                sp.close_done = False
                sp.close_target = None  # watcher interpretará como “cerrar inmediato” si decides implementarlo así
                logger.log({"event": "CLOSE_ALL_ARMED", "msg_id": reply_to, "split_id": sp.split_id, "ts": now_iso()})
        return
