# adapters/mt5_client.py
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

import MetaTrader5 as mt5
import config as CFG

# Import logger safely (project layout can vary)
try:
    from core import logger
except Exception:
    try:
        import logger  # fallback if logger.py is at project root
    except Exception:
        logger = None


# -------------------------
# Compat types for imports
# -------------------------
@dataclass
class Tick:
    bid: float
    ask: float
    last: float = 0.0
    time_msc: int = 0


def _to_tick(native_tick: Any) -> Tick:
    if native_tick is None:
        return Tick(bid=0.0, ask=0.0, last=0.0, time_msc=0)
    return Tick(
        bid=float(getattr(native_tick, "bid", 0.0) or 0.0),
        ask=float(getattr(native_tick, "ask", 0.0) or 0.0),
        last=float(getattr(native_tick, "last", 0.0) or 0.0),
        time_msc=int(getattr(native_tick, "time_msc", 0) or 0),
    )


# -------------------------
# Internal state (no duplication)
# -------------------------
_MT5_READY = False
_SYMBOL_READY = False
_SYMBOL_READY_NAME = None


def _log(payload: dict) -> None:
    """Never crash if logger is unavailable."""
    if logger is None:
        return
    try:
        logger.log_event(payload)
    except Exception:
        pass


def _last_error() -> dict:
    """MT5 last_error() helper, never crash."""
    try:
        e = mt5.last_error()
        # MT5 returns tuple (code, description) in many builds
        if isinstance(e, tuple) and len(e) >= 2:
            return {"code": int(e[0]), "desc": str(e[1])}
        return {"code": None, "desc": str(e)}
    except Exception as ex:
        return {"code": None, "desc": f"last_error_exception: {ex}"}


def _ensure_mt5_ready() -> bool:
    """
    Ensure MT5 is initialized AND logged in.
    This is intentionally centralized to avoid duplicate logic.
    """
    global _MT5_READY

    if _MT5_READY:
        return True

    if not mt5.initialize():
        _log(
            {
                "event": "MT5_INIT_FAILED_INTERNAL",
                "server": getattr(CFG, "MT5_SERVER", None),
                "login": getattr(CFG, "MT5_LOGIN", None),
                "last_error": _last_error(),
            }
        )
        return False

    # Always attempt login (fixes previous bug: hasattr(CFG, "LOGIN") was wrong)
    login = getattr(CFG, "MT5_LOGIN", None)
    password = getattr(CFG, "MT5_PASSWORD", None)
    server = getattr(CFG, "MT5_SERVER", None)

    ok_login = False
    try:
        ok_login = bool(mt5.login(int(login), str(password), str(server)))
    except Exception as ex:
        _log(
            {
                "event": "MT5_LOGIN_EXCEPTION",
                "login": login,
                "server": server,
                "error": str(ex),
                "last_error": _last_error(),
            }
        )
        ok_login = False

    if not ok_login:
        _log(
            {
                "event": "MT5_LOGIN_FAILED",
                "login": login,
                "server": server,
                "last_error": _last_error(),
            }
        )
        return False

    # Confirm account_info is accessible after login
    try:
        info = mt5.account_info()
        _log(
            {
                "event": "MT5_LOGIN_OK",
                "login": getattr(info, "login", login) if info else login,
                "server": getattr(info, "server", server) if info else server,
            }
        )
    except Exception:
        # Not fatal, but log it
        _log({"event": "MT5_ACCOUNT_INFO_UNAVAILABLE", "last_error": _last_error()})

    _MT5_READY = True
    return True


def _ensure_symbol_ready(force: bool = False) -> bool:
    """
    Ensure the trading symbol exists and is selected in this MT5 Python session.
    Centralized to avoid duplicating select logic across tick/order functions.
    """
    global _SYMBOL_READY, _SYMBOL_READY_NAME

    sym = str(getattr(CFG, "SYMBOL", "") or "").strip()
    if not sym:
        _SYMBOL_READY = False
        _SYMBOL_READY_NAME = None
        _log({"event": "MT5_SYMBOL_EMPTY"})
        return False

    if not _ensure_mt5_ready():
        _SYMBOL_READY = False
        _SYMBOL_READY_NAME = None
        return False

    if _SYMBOL_READY and _SYMBOL_READY_NAME == sym and not force:
        return True

    # Check symbol info first
    info = None
    try:
        info = mt5.symbol_info(sym)
    except Exception:
        info = None

    if not info:
        _SYMBOL_READY = False
        _SYMBOL_READY_NAME = None
        _log(
            {
                "event": "MT5_SYMBOL_INFO_MISSING",
                "symbol": sym,
                "last_error": _last_error(),
            }
        )
        return False

    # Ensure it's selected for this session
    ok_select = False
    try:
        ok_select = bool(mt5.symbol_select(sym, True))
    except Exception as ex:
        _log(
            {
                "event": "MT5_SYMBOL_SELECT_EXCEPTION",
                "symbol": sym,
                "error": str(ex),
                "last_error": _last_error(),
            }
        )
        ok_select = False

    if not ok_select:
        _SYMBOL_READY = False
        _SYMBOL_READY_NAME = None
        _log(
            {
                "event": "MT5_SYMBOL_SELECT_FAILED",
                "symbol": sym,
                "visible": bool(getattr(info, "visible", False)),
                "trade_mode": int(getattr(info, "trade_mode", -1) or -1),
                "last_error": _last_error(),
            }
        )
        return False

    _SYMBOL_READY = True
    _SYMBOL_READY_NAME = sym

    _log(
        {
            "event": "MT5_SYMBOL_READY",
            "symbol": sym,
            "digits": int(getattr(info, "digits", 0) or 0),
            "point": float(getattr(info, "point", 0.0) or 0.0),
            "trade_mode": int(getattr(info, "trade_mode", -1) or -1),
            "visible": bool(getattr(info, "visible", False)),
        }
    )
    return True


# -------------------------
# Public API (used by executor/watcher)
# -------------------------
def init() -> bool:
    """
    Called by main.py.
    Ensures MT5 init + login + symbol selection.
    """
    if not _ensure_mt5_ready():
        return False

    # Selecting symbol here helps avoid tick missing later
    _ensure_symbol_ready(force=True)
    return True


def shutdown() -> None:
    """Optional helper if you ever need a clean shutdown."""
    global _MT5_READY, _SYMBOL_READY, _SYMBOL_READY_NAME
    try:
        mt5.shutdown()
    except Exception:
        pass
    _MT5_READY = False
    _SYMBOL_READY = False
    _SYMBOL_READY_NAME = None


def account_login():
    info = mt5.account_info()
    return info.login if info else None


def account_server():
    info = mt5.account_info()
    return info.server if info else None


def account_balance():
    info = mt5.account_info()
    return info.balance if info else None


def symbol_tick():
    """
    Return MT5 tick for CFG.SYMBOL.
    Adds robust selection + tiny retry to avoid transient None in REAL.
    """
    sym = str(getattr(CFG, "SYMBOL", "") or "").strip()

    if not _ensure_symbol_ready():
        _log(
            {
                "event": "MT5_TICK_MISSING_DIAG",
                "symbol": sym,
                "reason": "symbol_not_ready",
                "last_error": _last_error(),
            }
        )
        return None

    # Retry a bit: real feeds can return None momentarily even with selection OK
    retries = 3
    delay_s = 0.20
    last = None
    for _ in range(retries):
        try:
            last = mt5.symbol_info_tick(sym)
        except Exception:
            last = None

        if last is not None:
            return last
        time.sleep(delay_s)

    _log(
        {
            "event": "MT5_TICK_MISSING_DIAG",
            "symbol": sym,
            "reason": "tick_none_after_retries",
            "retries": retries,
            "last_error": _last_error(),
        }
    )
    return None


def symbol_tick_safe() -> Tick:
    """Convenience: returns Tick dataclass instead of native MT5 tick."""
    return _to_tick(symbol_tick())


def symbol_constraints():
    sym = str(getattr(CFG, "SYMBOL", "") or "").strip()
    info = mt5.symbol_info(sym) if _ensure_symbol_ready() else None
    if not info:
        return {"point": 0.01, "digits": 2, "stops_level_points": 0, "freeze_level_points": 0}
    return {
        "point": float(info.point),
        "digits": int(info.digits),
        "stops_level_points": int(getattr(info, "stops_level", 0) or 0),
        "freeze_level_points": int(getattr(info, "freeze_level", 0) or 0),
    }


def normalize_price(x: float) -> float:
    sym = str(getattr(CFG, "SYMBOL", "") or "").strip()
    info = mt5.symbol_info(sym) if _ensure_symbol_ready() else None
    digits = int(getattr(info, "digits", 2) or 2) if info else 2
    return round(float(x), digits)


def position_get(position_ticket: int):
    ps = mt5.positions_get(ticket=position_ticket)
    if not ps:
        return None
    return ps[0]


def orders_get():
    sym = str(getattr(CFG, "SYMBOL", "") or "").strip()
    if not _ensure_symbol_ready():
        return []
    return mt5.orders_get(symbol=sym) or []


def open_market(side: str, volume: float, sl: float, tp: float):
    # Ensure symbol is ready before trying to trade
    if not _ensure_symbol_ready():
        return None, None

    tick = symbol_tick()
    if not tick:
        return None, None

    sym = str(getattr(CFG, "SYMBOL", "") or "").strip()
    side_u = (side or "").upper().strip()
    order_type = mt5.ORDER_TYPE_BUY if side_u == "BUY" else mt5.ORDER_TYPE_SELL
    price = float(tick.ask) if side_u == "BUY" else float(tick.bid)

    # MARKET: first IOC, fallback RETURN
    base_req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": sym,
        "volume": float(volume),
        "type": order_type,
        "price": normalize_price(price),
        "sl": normalize_price(sl),
        "tp": normalize_price(tp) if tp is not None else 0.0,
        "deviation": int(getattr(CFG, "DEVIATION", 0)),
        "magic": int(getattr(CFG, "MAGIC", 0)),
        "comment": "TG_BOT",
    }

    filling_try = [mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_RETURN]
    last_req = None
    last_res = None

    for fill in filling_try:
        req = dict(base_req)
        req["type_filling"] = fill
        last_req = req

        if getattr(CFG, "DRY_RUN", False):
            return req, None

        res = mt5.order_send(req)
        last_res = res

        ret = int(getattr(res, "retcode", 0) or 0)
        if ret == 10009:
            return req, res
        if ret == 10030:
            continue
        break

    return last_req, last_res


def open_pending(side: str, mode: str, volume: float, price: float, sl: float, tp: float):
    if not _ensure_symbol_ready():
        return None, None

    sym = str(getattr(CFG, "SYMBOL", "") or "").strip()
    side_u = (side or "").upper().strip()
    mode_u = (mode or "").upper().strip()

    if side_u == "BUY" and mode_u == "LIMIT":
        order_type = mt5.ORDER_TYPE_BUY_LIMIT
    elif side_u == "BUY" and mode_u == "STOP":
        order_type = mt5.ORDER_TYPE_BUY_STOP
    elif side_u == "SELL" and mode_u == "LIMIT":
        order_type = mt5.ORDER_TYPE_SELL_LIMIT
    else:
        order_type = mt5.ORDER_TYPE_SELL_STOP

    req = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": sym,
        "volume": float(volume),
        "type": order_type,
        "price": normalize_price(price),
        "sl": normalize_price(sl),
        "tp": normalize_price(tp) if tp is not None else 0.0,
        "deviation": int(getattr(CFG, "DEVIATION", 0)),
        "magic": int(getattr(CFG, "MAGIC", 0)),
        "comment": "TG_BOT_PENDING",
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }
    if getattr(CFG, "DRY_RUN", False):
        return req, None
    res = mt5.order_send(req)
    return req, res


def cancel_order(order_ticket: int):
    req = {"action": mt5.TRADE_ACTION_REMOVE, "order": int(order_ticket)}
    if getattr(CFG, "DRY_RUN", False):
        return req, None
    res = mt5.order_send(req)
    return req, res


def close_position(position_ticket: int, side: str, volume: float):
    if not _ensure_symbol_ready():
        return None, None

    tick = symbol_tick()
    if not tick:
        return None, None

    sym = str(getattr(CFG, "SYMBOL", "") or "").strip()
    side_u = (side or "").upper().strip()
    order_type = mt5.ORDER_TYPE_SELL if side_u == "BUY" else mt5.ORDER_TYPE_BUY
    price = float(tick.bid) if side_u == "BUY" else float(tick.ask)

    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": sym,
        "position": int(position_ticket),
        "volume": float(volume),
        "type": order_type,
        "price": normalize_price(price),
        "deviation": int(getattr(CFG, "DEVIATION", 0)),
        "magic": int(getattr(CFG, "MAGIC", 0)),
        "comment": "TG_BOT_CLOSE",
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }
    if getattr(CFG, "DRY_RUN", False):
        return req, None
    res = mt5.order_send(req)
    return req, res


def modify_sltp(position_ticket: int, new_sl: float, new_tp: float):
    """Modify SL/TP for an open position."""
    if not _ensure_symbol_ready():
        return None, None

    sym = str(getattr(CFG, "SYMBOL", "") or "").strip()
    new_sl = normalize_price(new_sl)
    new_tp = normalize_price(new_tp) if new_tp is not None else 0.0
    req = {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": sym,
        "position": position_ticket,
        "sl": new_sl,
        "tp": new_tp,
        "magic": getattr(CFG, "MAGIC", 0),
        "comment": "TG_BOT_MODIFY",
    }
    if getattr(CFG, "DRY_RUN", False):
        return req, None
    res = mt5.order_send(req)
    return req, res


def modify_sl(position_ticket: int, new_sl: float, fallback_tp: float | None = None):
    """Modify SL while preserving existing TP when possible.

    IMPORTANT: In MT5 a MODIFY with tp=0.0 removes the TP. So we must pass the current TP.
    """
    if not _ensure_symbol_ready():
        return None, None

    pos = position_get(position_ticket)
    tp_cur = None
    if pos is not None:
        try:
            tp_cur = float(getattr(pos, "tp", 0.0) or 0.0)
        except Exception:
            tp_cur = None

    if tp_cur is None or tp_cur <= 0.0:
        tp_use = float(fallback_tp) if fallback_tp is not None else 0.0
    else:
        tp_use = tp_cur

    sym = str(getattr(CFG, "SYMBOL", "") or "").strip()
    new_sl = normalize_price(new_sl)
    tp_use = normalize_price(tp_use) if tp_use else 0.0

    req = {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": sym,
        "position": position_ticket,
        "sl": new_sl,
        "tp": tp_use,
        "magic": getattr(CFG, "MAGIC", 0),
        "comment": "TG_BOT_BE",
    }
    if getattr(CFG, "DRY_RUN", False):
        return req, None
    res = mt5.order_send(req)
    return req, res


# -------------------------
# Wrapper class (compat for watcher imports)
# -------------------------
class MT5Client:
    """
    Compat wrapper:
        from adapters.mt5_client import MT5Client, Tick

    Internamente usa las funciones del módulo (sin duplicar lógica).
    """

    def __init__(self, login: int | None = None, password: str | None = None, server: str | None = None):
        # En tu proyecto real, las credenciales vienen de CFG; guardamos por compatibilidad.
        self.login = login
        self.password = password
        self.server = server

    def init(self) -> bool:
        return init()

    def shutdown(self) -> None:
        return shutdown()

    def symbol_tick(self) -> Any:
        return symbol_tick()

    def symbol_tick_safe(self) -> Tick:
        return symbol_tick_safe()

    def open_market(self, side: str, volume: float, sl: float, tp: float):
        return open_market(side, volume, sl, tp)

    def open_pending(self, side: str, mode: str, volume: float, price: float, sl: float, tp: float):
        return open_pending(side, mode, volume, price, sl, tp)

    def modify_sl(self, position_ticket: int, new_sl: float, fallback_tp: float | None = None):
        return modify_sl(position_ticket, new_sl, fallback_tp)

    def modify_sltp(self, position_ticket: int, new_sl: float, new_tp: float):
        return modify_sltp(position_ticket, new_sl, new_tp)

    def close_position(self, position_ticket: int, side: str, volume: float):
        return close_position(position_ticket, side, volume)

    def cancel_order(self, order_ticket: int):
        return cancel_order(order_ticket)


