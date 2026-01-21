import MetaTrader5 as mt5
from typing import Optional, Tuple
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

def send_market(side, volume, sl, tp):
    t = tick()
    price = t.ask if side=="BUY" else t.bid
    typ = mt5.ORDER_TYPE_BUY if side=="BUY" else mt5.ORDER_TYPE_SELL

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
    if kind=="LIMIT":
        typ = mt5.ORDER_TYPE_BUY_LIMIT if side=="BUY" else mt5.ORDER_TYPE_SELL_LIMIT
    else:
        typ = mt5.ORDER_TYPE_BUY_STOP if side=="BUY" else mt5.ORDER_TYPE_SELL_STOP

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
