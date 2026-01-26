# core/executor.py
from __future__ import annotations

from typing import Optional

import config as CFG
from adapters import mt5_client as mt5c

from core import logger
from core.management import classify_management, apply_management
from core.parser import parse_signal
from core.rules import decide_execution
from core.state import BOT_STATE, BotState


def _current_price_for_side(side: str, bid: float, ask: float) -> float:
    side_u = (side or "").upper().strip()
    return float(ask) if side_u == "BUY" else float(bid)


def _maybe_skip_if_tp_already_reached(side: str, tp: float, bid: float, ask: float) -> bool:
    """
    Si el TP ya fue tocado al momento de procesar, no abrimos split.
    BUY: si bid >= tp
    SELL: si ask <= tp
    """
    side_u = (side or "").upper().strip()
    if side_u == "BUY":
        return float(bid) >= float(tp)
    return float(ask) <= float(tp)


async def execute_signal(
    msg_id: int,
    text: str,
    reply_to: Optional[int],
    date_iso: Optional[str] = None,
    is_edit: bool = False,
    state: BotState = BOT_STATE,
) -> None:
    """
    Telegram handler: recibe msg_id/text/reply_to y decide:
      - si es management (BE/CLOSE...) => aplica a state
      - si es signal => parsea, decide MARKET/LIMIT/SKIP, abre splits en MT5, guarda state y loggea

    Nota: Esta función ES async porque main.py la await-ea, pero internamente todo lo que hace es sync.
    """
    text = text or ""

    # --- 0) Management messages (BE / CLOSE...) ---
    mg = classify_management(text)
    if mg.kind != "NONE":
        apply_management(state=state, msg_id=msg_id, reply_to=reply_to, mg=mg)
        return

    # --- 1) Cache de mensajes para re-procesar edits (typos etc.) ---
    cache = state.upsert_msg_cache(msg_id=msg_id, text=text)

    # Si ya existe señal para este msg_id y no es edit, ignoramos duplicados
    if state.has_signal(msg_id) and not is_edit:
        logger.log_event(
            {
                "event": "SIGNAL_DUPLICATE_IGNORED",
                "msg_id": msg_id,
                "date": date_iso,
            }
        )
        return

    # Si es edit pero fuera de ventana o demasiados intentos, no reprocesar
    if is_edit:
        if not cache.within_edit_window(int(getattr(CFG, "TG_EDIT_REPROCESS_WINDOW_S", 180))):
            logger.log_event(
                {
                    "event": "EDIT_IGNORED_OUTSIDE_WINDOW",
                    "msg_id": msg_id,
                    "date": date_iso,
                    "first_seen_ts": cache.first_seen_ts,
                    "last_seen_ts": cache.last_seen_ts,
                    "window_s": int(getattr(CFG, "TG_EDIT_REPROCESS_WINDOW_S", 180)),
                }
            )
            return
        if cache.parse_attempts >= int(getattr(CFG, "TG_EDIT_REPROCESS_MAX_ATTEMPTS", 3)):
            logger.log_event(
                {
                    "event": "EDIT_IGNORED_MAX_ATTEMPTS",
                    "msg_id": msg_id,
                    "date": date_iso,
                    "attempts": cache.parse_attempts,
                    "max": int(getattr(CFG, "TG_EDIT_REPROCESS_MAX_ATTEMPTS", 3)),
                }
            )
            return

    # --- 2) Parse Signal ---
    sig = parse_signal(msg_id=msg_id, text=text)
    state.mark_parse_attempt(msg_id=msg_id, parse_failed=(sig is None))

    if sig is None:
        logger.log_event(
            {
                "event": "SIGNAL_PARSE_FAILED",
                "msg_id": msg_id,
                "reply_to": reply_to,
                "date": date_iso,
                "is_edit": is_edit,
                "text": text,
                "attempts": state.msg_cache.get(msg_id).parse_attempts if state.msg_cache.get(msg_id) else None,
            }
        )
        return

    logger.log_event(
        {
            "event": "SIGNAL_PARSED",
            "msg_id": msg_id,
            "reply_to": reply_to,
            "date": date_iso,
            "side": sig.side,
            "entry": sig.entry,
            "tps": sig.tps,
            "sl": sig.sl,
        }
    )

    # Guardar señal en estado (si ya existía por edit, add_signal lo ignora; está ok)
    state.add_signal(sig)

    # Asegurar MT5 listo
    if not mt5c.is_ready():
        logger.log_event({"event": "MT5_NOT_READY", "msg_id": msg_id})
        return

    tick = mt5c.get_tick()
    if not tick:
        logger.log_event({"event": "MT5_NO_TICK", "msg_id": msg_id})
        return

    current_price = _current_price_for_side(sig.side, tick.bid, tick.ask)
    mode = decide_execution(sig.side, sig.entry, current_price)

    logger.log_event(
        {
            "event": "EXECUTION_DECIDED",
            "msg_id": msg_id,
            "side": sig.side,
            "entry": sig.entry,
            "bid": tick.bid,
            "ask": tick.ask,
            "current_price": current_price,
            "mode": mode,
        }
    )

    if mode == "SKIP":
        logger.log_event(
            {
                "event": "SIGNAL_SKIPPED_HARD_DRIFT",
                "msg_id": msg_id,
                "side": sig.side,
                "entry": sig.entry,
                "bid": tick.bid,
                "ask": tick.ask,
                "current_price": current_price,
            }
        )
        return

    # Splits (TP1/TP2/...) se manejan por estado
    splits = state.build_splits_for_signal(sig.message_id)

    # En ediciones, build_splits_for_signal puede devolver splits ya existentes.
    # Para evitar duplicados (y re-abrir operaciones) sólo enviamos los splits NUEVOS.
    splits_to_send = [sp for sp in splits if getattr(sp, "status", None) == "NEW"]
    if not splits_to_send:
        logger.log_event(
            {
                "event": "SIGNAL_NO_NEW_SPLITS",
                "msg_id": msg_id,
                "is_edit": is_edit,
                "date": date_iso,
            }
        )
        return

    # Si ya está en TP al momento, no vale la pena abrir
    for sp in splits_to_send:
        if _maybe_skip_if_tp_already_reached(sig.side, sp.tp, tick.bid, tick.ask):
            sp.status = "CANCELED"
            logger.log_event(
                {
                    "event": "SPLIT_SKIPPED_TP_ALREADY_REACHED",
                    "signal_msg_id": msg_id,
                    "split": sp.split_index,
                    "tp": sp.tp,
                    "bid": tick.bid,
                    "ask": tick.ask,
                }
            )

    # Enviar órdenes
    for sp in splits_to_send:
        if sp.status != "NEW":
            continue

        vol = float(getattr(CFG, "DEFAULT_LOT", 0.01))
        if mode == "MARKET":
            req, res = mt5c.open_market(sig.side, vol=vol, sl=sig.sl, tp=sp.tp)
            sp.last_req = req
            sp.last_res = str(res)
            if res and getattr(res, "retcode", None) == 10009:
                sp.status = "OPEN"
                sp.position_ticket = getattr(res, "order", None)
            else:
                sp.status = "ERROR"

            logger.log_event(
                {
                    "event": "MARKET_ORDER_SENT",
                    "signal_msg_id": msg_id,
                    "split": sp.split_index,
                    "side": sig.side,
                    "vol": vol,
                    "sl": sig.sl,
                    "tp": sp.tp,
                    "result": str(res),
                }
            )
        else:
            # pending order (LIMIT o STOP, ya decidido en rules)
            req, res = mt5c.open_pending(
                sig.side,
                price=sig.entry,
                vol=vol,
                sl=sig.sl,
                tp=sp.tp,
                mode=mode,
            )
            sp.last_req = req
            sp.last_res = str(res)
            if res and getattr(res, "retcode", None) == 10009:
                sp.status = "PENDING"
                sp.order_ticket = getattr(res, "order", None)
                sp.pending_created_ts = mt5c.time_now()
            else:
                sp.status = "ERROR"

            logger.log_event(
                {
                    "event": "PENDING_ORDER_SENT",
                    "signal_msg_id": msg_id,
                    "split": sp.split_index,
                    "side": sig.side,
                    "mode": mode,
                    "entry": sig.entry,
                    "vol": vol,
                    "sl": sig.sl,
                    "tp": sp.tp,
                    "result": str(res),
                }
            )
