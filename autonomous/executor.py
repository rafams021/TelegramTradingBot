# autonomous/executor.py
from typing import Optional

import config as CFG
from adapters.mt5 import MT5Client
from core.state import Signal, BotState, BOT_STATE
from infrastructure.logging import get_logger

logger = get_logger()

_mt5_client: Optional[MT5Client] = None


def set_mt5_client(client: MT5Client) -> None:
    global _mt5_client
    _mt5_client = client


def get_mt5_client() -> Optional[MT5Client]:
    return _mt5_client


def execute_signal_direct(
    signal: Signal,
    state: BotState = BOT_STATE,
) -> bool:
    mt5 = get_mt5_client()
    msg_id = signal.message_id

    if not mt5 or not mt5.is_ready():
        logger.event("AUTONOMOUS_MT5_NOT_READY", msg_id=msg_id)
        return False

    tick = mt5.get_tick()
    if not tick:
        logger.event("AUTONOMOUS_NO_TICK", msg_id=msg_id)
        return False

    max_positions = int(CFG.MAX_OPEN_POSITIONS)
    if max_positions > 0:
        current_count = len(mt5.get_all_positions())
        if current_count >= max_positions:
            logger.event(
                "MAX_POSITIONS_REACHED",
                msg_id=msg_id,
                current=current_count,
                max=max_positions,
            )
            return False

    current_price = _get_current_price(signal.side, tick.bid, tick.ask)
    mode = _decide_execution_mode(signal.side, signal.entry, current_price)

    logger.event(
        "AUTONOMOUS_EXECUTION_DECIDED",
        msg_id=msg_id,
        side=signal.side,
        entry=signal.entry,
        current_price=current_price,
        mode=mode,
    )

    if mode == "SKIP":
        logger.event(
            "AUTONOMOUS_SIGNAL_SKIPPED",
            msg_id=msg_id,
            reason="HARD_DRIFT",
            entry=signal.entry,
            current_price=current_price,
        )
        return False

    if state.has_signal(msg_id):
        logger.event("AUTONOMOUS_SIGNAL_DUPLICATE", msg_id=msg_id)
        return False

    state.add_signal(signal)

    volume = float(CFG.VOLUME_PER_ORDER)
    executed_count = 0

    for i, tp in enumerate(signal.tps):
        if _is_tp_already_hit(signal.side, tp, tick.bid, tick.ask):
            logger.event("TP_ALREADY_HIT", msg_id=msg_id, tp_index=i, tp=tp)
            continue

        if mode == "MARKET":
            success = _execute_market_order(signal, tp, i, volume, mt5, msg_id)
        else:
            success = _execute_limit_order(signal, tp, i, volume, mt5, msg_id)

        if success:
            executed_count += 1

    logger.event(
        "AUTONOMOUS_SIGNAL_EXECUTED",
        msg_id=msg_id,
        side=signal.side,
        entry=signal.entry,
        executed_orders=executed_count,
        mode=mode,
    )

    return executed_count > 0


def _get_current_price(side: str, bid: float, ask: float) -> float:
    return float(ask) if side == "BUY" else float(bid)


def _decide_execution_mode(side: str, entry: float, current: float) -> str:
    drift_pips = abs(entry - current)
    hard_drift = float(getattr(CFG, "HARD_DRIFT_LIMIT", 15.0))
    soft_drift = float(getattr(CFG, "SOFT_DRIFT_LIMIT", 3.0))

    if drift_pips > hard_drift:
        return "SKIP"
    if drift_pips <= soft_drift:
        return "MARKET"
    return "LIMIT"


def _is_tp_already_hit(side: str, tp: float, bid: float, ask: float) -> bool:
    if side == "BUY":
        return bid >= tp
    return ask <= tp


def _execute_market_order(
    signal: Signal,
    tp: float,
    tp_index: int,
    volume: float,
    mt5: MT5Client,
    msg_id: int,
) -> bool:
    try:
        ticket = mt5.send_order(
            side=signal.side,
            volume=volume,
            sl=signal.sl,
            tp=tp,
            comment=f"AUTO_{signal.symbol}_{tp_index}",
        )
        if ticket and ticket > 0:
            logger.event(
                "ORDER_MARKET_SUCCESS",
                msg_id=msg_id,
                ticket=ticket,
                side=signal.side,
                volume=volume,
                tp=tp,
                sl=signal.sl,
            )
            return True
        logger.event("ORDER_MARKET_FAILED", msg_id=msg_id, side=signal.side)
        return False
    except Exception as ex:
        logger.error("ORDER_MARKET_ERROR", exc_info=True, msg_id=msg_id, error=str(ex))
        return False


def _execute_limit_order(
    signal: Signal,
    tp: float,
    tp_index: int,
    volume: float,
    mt5: MT5Client,
    msg_id: int,
) -> bool:
    try:
        ticket = mt5.send_pending_order(
            side=signal.side,
            volume=volume,
            entry=signal.entry,
            sl=signal.sl,
            tp=tp,
            comment=f"AUTO_LIMIT_{signal.symbol}_{tp_index}",
        )
        if ticket and ticket > 0:
            logger.event(
                "ORDER_LIMIT_SUCCESS",
                msg_id=msg_id,
                ticket=ticket,
                side=signal.side,
                entry=signal.entry,
                volume=volume,
                tp=tp,
                sl=signal.sl,
            )
            return True
        logger.event("ORDER_LIMIT_FAILED", msg_id=msg_id, side=signal.side)
        return False
    except Exception as ex:
        logger.error("ORDER_LIMIT_ERROR", exc_info=True, msg_id=msg_id, error=str(ex))
        return False