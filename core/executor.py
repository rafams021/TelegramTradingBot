# core/executor.py
"""
Ejecutor principal del bot - Orquesta el flujo de procesamiento de señales.

REFACTORIZADO EN FASE 2:
- Lógica de procesamiento de señales movida a SignalService
- Lógica de decisión de ejecución usa enums
- Código simplificado de 263 → ~150 líneas
"""
from __future__ import annotations

from typing import Optional

import config as CFG
from adapters import mt5_client as mt5c

from core import logger
from core.domain.enums import OrderSide, ExecutionMode
from core.management import classify_management, apply_management
from core.rules import decide_execution_legacy
from core.services import SignalService
from core.state import BOT_STATE, BotState


# Global service instance (lazy init)
_signal_service: Optional[SignalService] = None


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
    text = text or ""

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
    sig = signal_service.process_signal(
        msg_id=msg_id,
        text=text,
        date_iso=date_iso,
        is_edit=is_edit,
    )
    
    if sig is None:
        # Signal processing failed (ya loggeado por el service)
        return

    # ==========================================
    # 3. VERIFY MT5 READY
    # ==========================================
    if not mt5c.is_ready():
        logger.log_event({"event": "MT5_NOT_READY", "msg_id": msg_id})
        return

    tick = mt5c.symbol_tick()
    if not tick:
        logger.log_event({"event": "MT5_NO_TICK", "msg_id": msg_id})
        return

    # ==========================================
    # 4. DECIDE EXECUTION MODE
    # ==========================================
    current_price = _current_price_for_side(sig.side, tick.bid, tick.ask)
    mode = decide_execution_legacy(sig.side, sig.entry, current_price)

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

    # ==========================================
    # 5. CREATE SPLITS (usando SignalService)
    # ==========================================
    splits = signal_service.create_splits(sig)

    # En ediciones, solo enviamos splits NUEVOS
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

    # ==========================================
    # 6. SKIP IF TP ALREADY REACHED
    # ==========================================
    for sp in splits_to_send:
        if signal_service.should_skip_tp(sig.side, sp.tp, tick.bid, tick.ask):
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

    # ==========================================
    # 7. EXECUTE ORDERS
    # ==========================================
    vol = float(getattr(CFG, "DEFAULT_LOT", 0.01))
    
    for sp in splits_to_send:
        if sp.status != "NEW":
            continue

        if mode == "MARKET":
            _execute_market_order(sp, sig, vol, msg_id)
        else:
            _execute_pending_order(sp, sig, vol, mode, msg_id)


def _execute_market_order(split, signal, volume: float, msg_id: int) -> None:
    """
    Ejecuta una orden a mercado.
    
    Args:
        split: Split (SplitState) a ejecutar
        signal: Señal original
        volume: Volumen a operar
        msg_id: ID del mensaje de Telegram
    """
    req, res = mt5c.open_market(signal.side, vol=volume, sl=signal.sl, tp=split.tp)
    
    split.last_req = req
    split.last_res = str(res)
    
    if res and getattr(res, "retcode", None) == 10009:
        split.status = "OPEN"
        split.position_ticket = getattr(res, "order", None)
    else:
        split.status = "ERROR"

    logger.log_event(
        {
            "event": "MARKET_ORDER_SENT",
            "signal_msg_id": msg_id,
            "split": split.split_index,
            "side": signal.side,
            "vol": volume,
            "sl": signal.sl,
            "tp": split.tp,
            "result": str(res),
        }
    )


def _execute_pending_order(split, signal, volume: float, mode: str, msg_id: int) -> None:
    """
    Ejecuta una orden pendiente (LIMIT o STOP).
    
    Args:
        split: Split (SplitState) a ejecutar
        signal: Señal original
        volume: Volumen a operar
        mode: Tipo de orden ("LIMIT" o "STOP")
        msg_id: ID del mensaje de Telegram
    """
    req, res = mt5c.open_pending(
        signal.side,
        price=signal.entry,
        vol=volume,
        sl=signal.sl,
        tp=split.tp,
        mode=mode,
    )
    
    split.last_req = req
    split.last_res = str(res)
    
    if res and getattr(res, "retcode", None) == 10009:
        split.status = "PENDING"
        split.order_ticket = getattr(res, "order", None)
        split.pending_created_ts = mt5c.time_now()
    else:
        split.status = "ERROR"

    logger.log_event(
        {
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
        }
    )