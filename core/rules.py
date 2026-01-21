from typing import Literal
import config as CFG

def decide_execution(side: str, entry: float, current_price: float) -> Literal["MARKET","LIMIT","STOP","SKIP"]:

    if side == "BUY":
        delta = current_price - entry

        if delta > CFG.MAX_UP_DRIFT:
            return "LIMIT"   # esperar retroceso
        if delta < -CFG.MAX_DOWN_DRIFT:
            return "STOP"    # esperar confirmación
        return "MARKET"

    else:  # SELL
        delta = entry - current_price

        if delta > CFG.MAX_UP_DRIFT:
            return "LIMIT"
        if delta < -CFG.MAX_DOWN_DRIFT:
            return "STOP"
        return "MARKET"

def tp_reached(side: str, tp: float, bid: float, ask: float) -> bool:
    if side == "BUY":
        return bid >= tp
    else:
        return ask <= tp
