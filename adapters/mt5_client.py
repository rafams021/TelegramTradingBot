import time
import MetaTrader5 as mt5
import config as CFG


def init() -> bool:
    if not mt5.initialize():
        return False
    mt5.login(CFG.MT5_LOGIN, CFG.MT5_PASSWORD, CFG.MT5_SERVER) if hasattr(CFG, "LOGIN") else None
    return True


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
    return mt5.symbol_info_tick(CFG.SYMBOL)


def symbol_constraints():
    info = mt5.symbol_info(CFG.SYMBOL)
    if not info:
        return {"point": 0.01, "digits": 2, "stops_level_points": 0, "freeze_level_points": 0}
    return {
        "point": float(info.point),
        "digits": int(info.digits),
        "stops_level_points": int(getattr(info, "stops_level", 0) or 0),
        "freeze_level_points": int(getattr(info, "freeze_level", 0) or 0),
    }


def normalize_price(x: float) -> float:
    info = mt5.symbol_info(CFG.SYMBOL)
    digits = int(getattr(info, "digits", 2) or 2) if info else 2
    return round(float(x), digits)


def position_get(position_ticket: int):
    ps = mt5.positions_get(ticket=position_ticket)
    if not ps:
        return None
    return ps[0]


def orders_get():
    return mt5.orders_get(symbol=CFG.SYMBOL) or []


def open_market(side: str, volume: float, sl: float, tp: float):
    tick = symbol_tick()
    if not tick:
        return None, None
    side_u = (side or "").upper().strip()
    order_type = mt5.ORDER_TYPE_BUY if side_u == "BUY" else mt5.ORDER_TYPE_SELL
    price = float(tick.ask) if side_u == "BUY" else float(tick.bid)

    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": CFG.SYMBOL,
        "volume": float(volume),
        "type": order_type,
        "price": normalize_price(price),
        "sl": normalize_price(sl),
        "tp": normalize_price(tp) if tp is not None else 0.0,
        "deviation": int(CFG.DEVIATION),
        "magic": int(CFG.MAGIC),
        "comment": "TG_BOT",
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }
    if CFG.DRY_RUN:
        return req, None
    res = mt5.order_send(req)
    return req, res


def open_pending(side: str, mode: str, volume: float, price: float, sl: float, tp: float):
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
        "symbol": CFG.SYMBOL,
        "volume": float(volume),
        "type": order_type,
        "price": normalize_price(price),
        "sl": normalize_price(sl),
        "tp": normalize_price(tp) if tp is not None else 0.0,
        "deviation": int(CFG.DEVIATION),
        "magic": int(CFG.MAGIC),
        "comment": "TG_BOT_PENDING",
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }
    if CFG.DRY_RUN:
        return req, None
    res = mt5.order_send(req)
    return req, res


def cancel_order(order_ticket: int):
    req = {"action": mt5.TRADE_ACTION_REMOVE, "order": int(order_ticket)}
    if CFG.DRY_RUN:
        return req, None
    res = mt5.order_send(req)
    return req, res


def close_position(position_ticket: int, side: str, volume: float):
    tick = symbol_tick()
    if not tick:
        return None, None
    side_u = (side or "").upper().strip()
    # close: opposite order type
    order_type = mt5.ORDER_TYPE_SELL if side_u == "BUY" else mt5.ORDER_TYPE_BUY
    price = float(tick.bid) if side_u == "BUY" else float(tick.ask)

    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": CFG.SYMBOL,
        "position": int(position_ticket),
        "volume": float(volume),
        "type": order_type,
        "price": normalize_price(price),
        "deviation": int(CFG.DEVIATION),
        "magic": int(CFG.MAGIC),
        "comment": "TG_BOT_CLOSE",
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }
    if CFG.DRY_RUN:
        return req, None
    res = mt5.order_send(req)
    return req, res


def modify_sltp(position_ticket: int, new_sl: float, new_tp: float):
    """Modify SL/TP for an open position."""
    new_sl = normalize_price(new_sl)
    new_tp = normalize_price(new_tp) if new_tp is not None else 0.0
    req = {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": CFG.SYMBOL,
        "position": position_ticket,
        "sl": new_sl,
        "tp": new_tp,
        "magic": CFG.MAGIC,
        "comment": "TG_BOT_MODIFY",
    }
    if CFG.DRY_RUN:
        return req, None
    res = mt5.order_send(req)
    return req, res


def modify_sl(position_ticket: int, new_sl: float, fallback_tp: float | None = None):
    """Modify SL while preserving existing TP when possible.

    IMPORTANT: In MT5 a MODIFY with tp=0.0 removes the TP. So we must pass the current TP.
    """
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

    new_sl = normalize_price(new_sl)
    tp_use = normalize_price(tp_use) if tp_use else 0.0

    req = {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": CFG.SYMBOL,
        "position": position_ticket,
        "sl": new_sl,
        "tp": tp_use,
        "magic": CFG.MAGIC,
        "comment": "TG_BOT_BE",
    }
    if CFG.DRY_RUN:
        return req, None
    res = mt5.order_send(req)
    return req, res

