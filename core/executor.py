# core/executor.py
"""
Ejecutor principal del bot.

FASE AUTONOMOUS: Agrega execute_signal_direct() para señales
del MarketAnalyzer que ya vienen construidas (sin parseo de texto).
"""
from __future__ import annotations

from typing import Optional
from datetime import datetime, timezone

import config as CFG
from adapters.mt5 import MT5Client

from core import logger
from core.domain.enums import OrderSide, ExecutionMode
from core.management import classify_management, apply_management
from core.models import Signal
from core.rules import decide_execution_legacy
from core.services import SignalService
from core.state import BOT_STATE, BotState
from analytics.metrics_tracker import get_metrics_tracker
from analytics.strategy_classifier import StrategyClassifier
import time


_signal_service: Optional[SignalService] = None
_mt5_client: Optional[MT5Client] = None


def set_mt5_client(client: MT5Client) -> None:
    global _mt5_client
    _mt5_client = client


def _get_mt5_client() -> Optional[MT5Client]:
    return _mt5_client


def _get_signal_service(state: BotState) -> SignalService:
    global _signal_service
    if _signal_service is None:
        _signal_service = SignalService(state)
    return _signal_service


def _current_price_for_side(side: str, bid: float, ask: float) -> float:
    side_u = (side or "").upper().strip()
    return float(ask) if side_u == "BUY" else float(bid)


def _check_max_positions(mt5: MT5Client, msg_id: int) -> bool:
    """
    Verifica si se puede abrir una nueva posición.
    Consulta MT5 directamente para evitar depender del BotState.
    """
    max_positions = int(getattr(CFG, "MAX_OPEN_POSITIONS", 0) or 0)
    if max_positions <= 0:
        return True

    current_count = len(mt5.get_all_positions())
    if current_count >= max_positions:
        logger.log_event({
            "event": "MAX_POSITIONS_REACHED",
            "msg_id": msg_id,
            "current": current_count,
            "max": max_positions,
        })
        return False
    return True


async def execute_signal(
    msg_id: int,
    text: str,
    reply_to: Optional[int],
    date_iso: Optional[str] = None,
    is_edit: bool = False,
    state: BotState = BOT_STATE,
) -> None:
    """Handler principal de mensajes de Telegram."""
    start_time = time.time()
    metrics = get_metrics_tracker()
    text = text or ""
    mt5 = _get_mt5_client()

    # 1. MANAGEMENT COMMANDS
    mg = classify_management(text)
    if mg.kind != "NONE":
        apply_management(state=state, msg_id=msg_id, reply_to=reply_to, mg=mg)
        return

    # 2. PROCESS SIGNAL
    signal_service = _get_signal_service(state)
    parse_start = time.time()
    sig = signal_service.process_signal(
        msg_id=msg_id,
        text=text,
        date_iso=date_iso,
        is_edit=is_edit,
    )
    parse_time_ms = (time.time() - parse_start) * 1000

    if sig is None:
        metrics.track_signal_failed(msg_id, "PARSE_FAILED")
        return

    metrics.track_signal_parsed(
        msg_id=msg_id,
        side=sig.side,
        entry=sig.entry,
        tps=sig.tps,
        sl=sig.sl,
        parse_time_ms=parse_time_ms,
    )

    # 3. VERIFY MT5 READY
    if not mt5 or not mt5.is_ready():
        metrics.track_signal_failed(msg_id, "MT5_NOT_READY")
        logger.log_event({"event": "MT5_NOT_READY", "msg_id": msg_id})
        return

    tick = mt5.get_tick()
    if not tick:
        metrics.track_signal_failed(msg_id, "MT5_NO_TICK")
        logger.log_event({"event": "MT5_NO_TICK", "msg_id": msg_id})
        return

    # 4. DECIDE EXECUTION MODE
    current_price = _current_price_for_side(sig.side, tick.bid, tick.ask)
    mode = decide_execution_legacy(sig.side, sig.entry, current_price)

    metrics.track_execution_decided(
        msg_id=msg_id, mode=mode, current_price=current_price,
    )

    timestamp = date_iso or datetime.now(timezone.utc).isoformat()
    classification = StrategyClassifier.classify_signal(
        entry=sig.entry, tps=sig.tps, sl=sig.sl,
        current_price=current_price, timestamp=timestamp,
    )
    if msg_id in metrics.signals:
        metrics.signals[msg_id].strategy = classification.get("style")
        metrics.signals[msg_id].session = classification.get("session")
        metrics.signals[msg_id].risk_reward_ratio = classification.get("risk_reward")

    logger.log_event({
        "event": "EXECUTION_DECIDED",
        "msg_id": msg_id,
        "side": sig.side,
        "entry": sig.entry,
        "bid": tick.bid,
        "ask": tick.ask,
        "current_price": current_price,
        "mode": mode,
    })

    if mode == "SKIP":
        metrics.track_signal_skipped(msg_id, "HARD_DRIFT")
        logger.log_event({
            "event": "SIGNAL_SKIPPED_HARD_DRIFT",
            "msg_id": msg_id,
            "side": sig.side,
            "entry": sig.entry,
            "current_price": current_price,
        })
        return

    # 4.5 GUARD: MAX_OPEN_POSITIONS
    if not _check_max_positions(mt5, msg_id):
        metrics.track_signal_skipped(msg_id, "MAX_POSITIONS_REACHED")
        return

    # 5. CREATE SPLITS
    splits = signal_service.create_splits(sig)
    splits_to_send = [sp for sp in splits if getattr(sp, "status", None) == "NEW"]
    if not splits_to_send:
        logger.log_event({
            "event": "SIGNAL_NO_NEW_SPLITS",
            "msg_id": msg_id,
            "is_edit": is_edit,
        })
        return

    # 6. SKIP IF TP ALREADY REACHED
    for sp in splits_to_send:
        if signal_service.should_skip_tp(sig.side, sp.tp, tick.bid, tick.ask):
            sp.status = "CANCELED"
            logger.log_event({
                "event": "SPLIT_SKIPPED_TP_ALREADY_REACHED",
                "signal_msg_id": msg_id,
                "split": sp.split_index,
                "tp": sp.tp,
            })

    # 7. EXECUTE ORDERS
    vol = float(getattr(CFG, "DEFAULT_LOT", 0.01))
    executed_count = 0
    for sp in splits_to_send:
        if sp.status != "NEW":
            continue
        if mode == "MARKET":
            success = _execute_market_order(sp, sig, vol, msg_id, mt5, metrics)
        else:
            success = _execute_pending_order(sp, sig, vol, mode, msg_id, mt5, metrics)
        if success:
            executed_count += 1

    if executed_count > 0:
        execution_time_ms = (time.time() - start_time) * 1000
        metrics.track_signal_executed(
            msg_id=msg_id,
            num_executed=executed_count,
            execution_time_ms=execution_time_ms,
        )


def execute_signal_direct(
    signal: Signal,
    state: BotState = BOT_STATE,
) -> bool:
    """
    Ejecuta una señal ya construida directamente en MT5.

    Usada por el módulo autónomo — las señales vienen del MarketAnalyzer
    ya construidas, sin necesidad de parseo de texto.

    A diferencia de execute_signal():
    - No parsea texto
    - No procesa comandos de management
    - No es async
    - Respeta MAX_OPEN_POSITIONS
    - Registra la señal en BotState para evitar duplicados

    Args:
        signal: Objeto Signal ya construido por una estrategia
        state: Estado global del bot

    Returns:
        True si se ejecutó al menos una orden exitosamente
    """
    mt5 = _get_mt5_client()
    metrics = get_metrics_tracker()
    msg_id = signal.message_id

    # 1. VERIFY MT5 READY
    if not mt5 or not mt5.is_ready():
        logger.log_event({"event": "AUTONOMOUS_MT5_NOT_READY", "msg_id": msg_id})
        return False

    tick = mt5.get_tick()
    if not tick:
        logger.log_event({"event": "AUTONOMOUS_NO_TICK", "msg_id": msg_id})
        return False

    # 2. GUARD: MAX_OPEN_POSITIONS
    if not _check_max_positions(mt5, msg_id):
        return False

    # 3. DECIDE EXECUTION MODE
    current_price = _current_price_for_side(signal.side, tick.bid, tick.ask)
    mode = decide_execution_legacy(signal.side, signal.entry, current_price)

    logger.log_event({
        "event": "AUTONOMOUS_EXECUTION_DECIDED",
        "msg_id": msg_id,
        "side": signal.side,
        "entry": signal.entry,
        "current_price": current_price,
        "mode": mode,
    })

    if mode == "SKIP":
        logger.log_event({
            "event": "AUTONOMOUS_SIGNAL_SKIPPED",
            "msg_id": msg_id,
            "reason": "HARD_DRIFT",
            "entry": signal.entry,
            "current_price": current_price,
        })
        return False

    # 4. EVITAR DUPLICADOS
    if state.has_signal(msg_id):
        logger.log_event({
            "event": "AUTONOMOUS_SIGNAL_DUPLICATE",
            "msg_id": msg_id,
        })
        return False

    state.add_signal(signal)

    # 5. CREATE SPLITS
    signal_service = _get_signal_service(state)
    splits = signal_service.create_splits(signal)
    splits_to_send = [sp for sp in splits if sp.status == "NEW"]
    if not splits_to_send:
        return False

    # 6. SKIP IF TP ALREADY REACHED
    for sp in splits_to_send:
        if signal_service.should_skip_tp(signal.side, sp.tp, tick.bid, tick.ask):
            sp.status = "CANCELED"

    # 7. EXECUTE ORDERS
    vol = float(getattr(CFG, "VOLUME_PER_ORDER", 0.01))
    executed_count = 0
    for sp in splits_to_send:
        if sp.status != "NEW":
            continue
        if mode == "MARKET":
            success = _execute_market_order(sp, signal, vol, msg_id, mt5, metrics)
        else:
            success = _execute_pending_order(sp, signal, vol, mode, msg_id, mt5, metrics)
        if success:
            executed_count += 1

    logger.log_event({
        "event": "AUTONOMOUS_SIGNAL_EXECUTED",
        "msg_id": msg_id,
        "side": signal.side,
        "entry": signal.entry,
        "executed_orders": executed_count,
        "mode": mode,
    })

    return executed_count > 0


def _execute_market_order(
    split, signal, volume: float, msg_id: int, mt5: MT5Client, metrics,
) -> bool:
    req, res = mt5.open_market(signal.side, volume=volume, sl=signal.sl, tp=split.tp)
    split.last_req = req
    split.last_res = str(res)

    success = False
    if res and getattr(res, "retcode", None) == 10009:
        split.status = "OPEN"
        split.position_ticket = getattr(res, "order", None)
        success = True
        metrics.track_position_opened(
            signal_msg_id=msg_id,
            split_index=split.split_index,
            ticket=split.position_ticket,
            side=signal.side,
            entry_intended=signal.entry,
            entry_actual=getattr(res, "price", signal.entry),
            tp=split.tp,
            sl=signal.sl,
            volume=volume,
        )
    else:
        split.status = "ERROR"

    logger.log_event({
        "event": "MARKET_ORDER_SENT",
        "signal_msg_id": msg_id,
        "split": split.split_index,
        "side": signal.side,
        "vol": volume,
        "sl": signal.sl,
        "tp": split.tp,
        "result": str(res),
    })
    return success


def _execute_pending_order(
    split, signal, volume: float, mode: str, msg_id: int, mt5: MT5Client, metrics,
) -> bool:
    req, res = mt5.open_pending(
        signal.side,
        mode=mode,
        volume=volume,
        price=signal.entry,
        sl=signal.sl,
        tp=split.tp,
    )
    split.last_req = req
    split.last_res = str(res)

    success = False
    if res and getattr(res, "retcode", None) == 10009:
        split.status = "PENDING"
        split.order_ticket = getattr(res, "order", None)
        split.pending_created_ts = mt5.time_now()
        success = True
        metrics.track_position_opened(
            signal_msg_id=msg_id,
            split_index=split.split_index,
            ticket=split.order_ticket,
            side=signal.side,
            entry_intended=signal.entry,
            entry_actual=signal.entry,
            tp=split.tp,
            sl=signal.sl,
            volume=volume,
        )
    else:
        split.status = "ERROR"

    logger.log_event({
        "event": "PENDING_ORDER_SENT",
        "signal_msg_id": msg_id,
        "split": split.split_index,
        "side": signal.side,
        "mode": mode,
        "entry": signal.entry,
        "vol": volume,
        "sl": signal.sl,
        "tp": split.tp,
        "result": str(res),
    })
    return success