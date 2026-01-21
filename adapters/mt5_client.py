import MetaTrader5 as mt5
from typing import Any, List
import config as CFG


def init():
    if not mt5.initialize():
        raise RuntimeError(mt5.last_error())

    info = mt5.symbol_info(CFG.SYMBOL)
    if info is None:
        raise RuntimeError("Symbol not found")

    if not info.visible:
        mt5.symbol_select(CFG.SYMBOL, True)


def account_info():
    return mt5.account_info()


def tick():
    t = mt5.symbol_info_tick(CFG.SYMBOL)
    if t is None:
        raise RuntimeError("No tick")
    return t


def symbol_info():
    info = mt5.symbol_info(CFG.SYMBOL)
    if info is None:
        raise RuntimeError("Symbol not found")
    return info


def stop_constraints() -> dict:
    """Stops/freeze/digits/point para validación y logs."""
    info = symbol_info()
    point = float(getattr(info, "point", 0.0) or 0.0)
    digits = int(getattr(info, "digits", 0) or 0)
    stops_level = int(getattr(info, "trade_stops_level", 0) or 0)
    freeze_level = int(getattr(info, "trade_freeze_level", 0) or 0)

    return {
        "point": point,
        "digits": digits,
        "stops_level_points": stops_level,
        "freeze_level_points": freeze_level,
    }


def normalize_price(price: float) -> float:
    info = symbol_info()
    digits = int(getattr(info, "digits", 0) or 0)
    return round(float(price), digits)


def send_market(side, volume, sl, tp):
    t = tick()
    price = t.ask if side == "BUY" else t.bid
    typ = mt5.ORDER_TYPE_BUY if side == "BUY" else mt5.ORDER_TYPE_SELL

    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": CFG.SYMBOL,
        "volume": volume,
        "type": typ,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": CFG.DEVIATION,
        "magic": CFG.MAGIC,
        "comment": "TG_BOT",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    if CFG.DRY_RUN:
        return req, None

    res = mt5.order_send(req)
    return req, res


def send_pending(side, kind, entry, volume, sl, tp):
    if kind == "LIMIT":
        typ = mt5.ORDER_TYPE_BUY_LIMIT if side == "BUY" else mt5.ORDER_TYPE_SELL_LIMIT
    else:
        typ = mt5.ORDER_TYPE_BUY_STOP if side == "BUY" else mt5.ORDER_TYPE_SELL_STOP

    req = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": CFG.SYMBOL,
        "volume": volume,
        "type": typ,
        "price": entry,
        "sl": sl,
        "tp": tp,
        "deviation": CFG.DEVIATION,
        "magic": CFG.MAGIC,
        "comment": "TG_BOT_PENDING",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }

    if CFG.DRY_RUN:
        return req, None

    res = mt5.order_send(req)
    return req, res


def cancel_order(ticket: int):
    req = {"action": mt5.TRADE_ACTION_REMOVE, "order": ticket}
    if CFG.DRY_RUN:
        return req, None
    res = mt5.order_send(req)
    return req, res


def modify_sl(position_ticket: int, new_sl: float):
    new_sl = normalize_price(new_sl)
    req = {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": CFG.SYMBOL,
        "position": position_ticket,
        "sl": new_sl,
        "tp": 0.0,
        "magic": CFG.MAGIC,
        "comment": "TG_BOT_BE",
    }
    if CFG.DRY_RUN:
        return req, None
    res = mt5.order_send(req)
    return req, res


def position_get(position_ticket: int):
    pos = mt5.positions_get(ticket=position_ticket)
    if not pos:
        return None
    return pos[0]


def orders_get(order_ticket: int):
    ords = mt5.orders_get(ticket=order_ticket)
    if not ords:
        return None
    return ords[0]


def positions_by_magic() -> List[Any]:
    poss = mt5.positions_get(symbol=CFG.SYMBOL)
    if not poss:
        return []
    out = []
    for p in poss:
        if getattr(p, "magic", None) == CFG.MAGIC:
            out.append(p)
    return out


def close_position(position_ticket: int, side: str, volume: float):
    """Cierra a mercado. side = lado original de la posición (BUY/SELL)."""
    t = tick()
    close_type = mt5.ORDER_TYPE_SELL if side == "BUY" else mt5.ORDER_TYPE_BUY
    price = t.bid if side == "BUY" else t.ask

    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": CFG.SYMBOL,
        "position": position_ticket,
        "volume": volume,
        "type": close_type,
        "price": price,
        "deviation": CFG.DEVIATION,
        "magic": CFG.MAGIC,
        "comment": "TG_BOT_CLOSE",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    if CFG.DRY_RUN:
        return req, None

    res = mt5.order_send(req)
    return req, res
