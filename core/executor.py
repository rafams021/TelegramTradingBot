# core/executor.py
"""
Ejecutor principal del bot - Orquesta el flujo de procesamiento de señales.

REFACTORIZADO EN FASE 2:
- Lógica de procesamiento de señales movida a SignalService
- Lógica de decisión de ejecución usa enums
- Código simplificado de 263 → ~150 líneas

FIX: Usa MT5Client instance en vez del módulo mt5_client

ANALYTICS INTEGRADO:
- Tracking de métricas de señales
- Clasificación automática de estrategias
- Medición de latency y slippage
- Tracking de posiciones abiertas

FASE C - LIMPIEZA:
- Guard de MAX_OPEN_POSITIONS antes de ejecutar órdenes
- Consulta MT5 directamente (no BotState) para evitar desincronización
"""
from __future__ import annotations

from typing import Optional
from datetime import datetime, timezone

import config as CFG
from adapters.mt5 import MT5Client

from core import logger
from core.domain.enums import OrderSide, ExecutionMode
from core.management import classify_management, apply_management
from core.rules import decide_execution_legacy
from core.services import SignalService
from core.state import BOT_STATE, BotState
from analytics.metrics_tracker import get_metrics_tracker
from analytics.strategy_classifier import StrategyClassifier
import time


# Global instances (lazy init)
_signal_service: Optional[SignalService] = None
_mt5_client: Optional[MT5Client] = None


def set_mt5_client(client: MT5Client) -> None:
    """Establece el cliente MT5 global."""
    global _mt5_client
    _mt5_client = client


def _get_mt5_client() -> Optional[MT5Client]:
    """Obtiene el cliente MT5."""
    return _mt5_client


def _get_signal_service(state: BotState) -> SignalService:
    """Obtiene o crea la instancia del servicio de señales."""
    global _signal_service
    if _signal_service is None:
        _signal_service = SignalService(state)
    return _signal_service


def _current_price_for_side(side: str, bid: float, ask: float) -> float:
    """Retorna el precio actual relevante según el lado de la operación."""
    side_u = (side or "").upper().strip()
    return float(ask) if side_u == "BUY" else float(bid)


def _check_max_positions(mt5: MT5Client, msg_id: int) -> bool:
    """
    Verifica si se puede abrir una nueva posición.

    Consulta MT5 directamente para obtener el conteo real,
    evitando depender del BotState que puede estar desincronizado.

    Args:
        mt5: Cliente MT5
        msg_id: ID del mensaje (para logging)

    Returns:
        True si se puede abrir posición (bajo el límite)
        False si se alcanzó MAX_OPEN_POSITIONS
    """
    max_positions = int(getattr(CFG, "MAX_OPEN_POSITIONS", 0) or 0)

    # Si MAX_OPEN_POSITIONS es 0 o no está definido → sin límite
    if max_positions <= 0:
        return True

    open_positions = mt5.get_all_positions()
    current_count = len(open_positions)

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
    """
    Handler principal de mensajes de Telegram.

    Procesa:
    1. Comandos de gestión (BE, CLOSE, MOVE_SL)
    2. Señales de trading (BUY/SELL con TPs y SL)

    Args:
        msg_id: ID del mensaje de Telegram
        text: Contenido del mensaje
        reply_to: ID del mensaje al que responde (para management)
        date_iso: Fecha del mensaje en formato ISO
        is_edit: Si es una edición de mensaje
        state: Estado global del bot

    Note:
        Esta función ES async porque main.py la await-ea,
        pero internamente todo lo que hace es sync.
    """

    # ==========================================
    # METRICS: Iniciar tracking
    # ==========================================
    start_time = time.time()
    metrics = get_metrics_tracker()

    text = text or ""
    mt5 = _get_mt5_client()

    # ==========================================
    # 1. MANAGEMENT COMMANDS (BE / CLOSE / MOVE_SL)
    # ==========================================
    mg = classify_management(text)
    if mg.kind != "NONE":
        apply_management(state=state, msg_id=msg_id, reply_to=reply_to, mg=mg)
        return

    # ==========================================
    # 2. PROCESS SIGNAL (usando SignalService)
    # ==========================================
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

    # ==========================================
    # 3. VERIFY MT5 READY
    # ==========================================
    if not mt5 or not mt5.is_ready():
        metrics.track_signal_failed(msg_id, "MT5_NOT_READY")
        logger.log_event({"event": "MT5_NOT_READY", "msg_id": msg_id})
        return

    tick = mt5.get_tick()
    if not tick:
        metrics.track_signal_failed(msg_id, "MT5_NO_TICK")
        logger.log_event({"event": "MT5_NO_TICK", "msg_id": msg_id})
        return

    # ==========================================
    # 4. DECIDE EXECUTION MODE
    # ==========================================
    current_price = _current_price_for_side(sig.side, tick.bid, tick.ask)
    mode = decide_execution_legacy(sig.side, sig.entry, current_price)

    metrics.track_execution_decided(
        msg_id=msg_id,
        mode=mode,
        current_price=current_price,
    )

    timestamp = date_iso or datetime.now(timezone.utc).isoformat()
    classification = StrategyClassifier.classify_signal(
        entry=sig.entry,
        tps=sig.tps,
        sl=sig.sl,
        current_price=current_price,
        timestamp=timestamp,
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
            "bid": tick.bid,
            "ask": tick.ask,
            "current_price": current_price,
        })
        return

    # ==========================================
    # 4.5 GUARD: MAX_OPEN_POSITIONS (Fase C)
    # Se verifica DESPUÉS de decidir el modo pero
    # ANTES de crear splits y ejecutar órdenes.
    # Consulta MT5 directamente para evitar
    # depender del BotState desincronizado.
    # ==========================================
    if not _check_max_positions(mt5, msg_id):
        metrics.track_signal_skipped(msg_id, "MAX_POSITIONS_REACHED")
        return

    # ==========================================
    # 5. CREATE SPLITS (usando SignalService)
    # ==========================================
    splits = signal_service.create_splits(sig)

    splits_to_send = [sp for sp in splits if getattr(sp, "status", None) == "NEW"]
    if not splits_to_send:
        logger.log_event({
            "event": "SIGNAL_NO_NEW_SPLITS",
            "msg_id": msg_id,
            "is_edit": is_edit,
            "date": date_iso,
        })
        return

    # ==========================================
    # 6. SKIP IF TP ALREADY REACHED
    # ==========================================
    for sp in splits_to_send:
        if signal_service.should_skip_tp(sig.side, sp.tp, tick.bid, tick.ask):
            sp.status = "CANCELED"
            logger.log_event({
                "event": "SPLIT_SKIPPED_TP_ALREADY_REACHED",
                "signal_msg_id": msg_id,
                "split": sp.split_index,
                "tp": sp.tp,
                "bid": tick.bid,
                "ask": tick.ask,
            })

    # ==========================================
    # 7. EXECUTE ORDERS
    # ==========================================
    vol = float(getattr(CFG, "DEFAULT_LOT", 0.01))
    executed_count = 0

    for sp in splits_to_send:
        if sp.status != "NEW":
            continue

        if mode == "MARKET":
            success = _execute_market_order(sp, sig, vol, msg_id, mt5, metrics)
            if success:
                executed_count += 1
        else:
            success = _execute_pending_order(sp, sig, vol, mode, msg_id, mt5, metrics)
            if success:
                executed_count += 1

    # ==========================================
    # METRICS: Track signal executed
    # ==========================================
    if executed_count > 0:
        execution_time_ms = (time.time() - start_time) * 1000
        metrics.track_signal_executed(
            msg_id=msg_id,
            num_executed=executed_count,
            execution_time_ms=execution_time_ms,
        )


def _execute_market_order(
    split,
    signal,
    volume: float,
    msg_id: int,
    mt5: MT5Client,
    metrics,
) -> bool:
    """
    Ejecuta una orden a mercado.

    Returns:
        True si la orden fue exitosa
    """
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
    split,
    signal,
    volume: float,
    mode: str,
    msg_id: int,
    mt5: MT5Client,
    metrics,
) -> bool:
    """
    Ejecuta una orden pendiente (LIMIT o STOP).

    Returns:
        True si la orden fue exitosa
    """
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