from typing import Literal
import config as CFG

ExecutionMode = Literal["MARKET", "LIMIT", "STOP", "SKIP"]


def decide_execution(side: str, entry: float, current_price: float) -> ExecutionMode:
    """
    Decide cómo ejecutar la entrada (MARKET vs pending LIMIT/STOP) en función de la distancia al entry.

    Definición:
      delta = current_price - entry
      - delta > 0  => precio actual ARRIBA del entry
      - delta < 0  => precio actual ABAJO del entry

    Política:
      1) Si abs(delta) > HARD_DRIFT => SKIP (no operar; demasiado lejos del entry).
      2) Si está dentro de tolerancia MARKET => MARKET.
      3) Si está fuera de tolerancia MARKET pero no demasiado lejos => pending.
         - BUY:  entry arriba del precio actual => BUY STOP (breakout)
                 entry abajo del precio actual => BUY LIMIT (pullback)
         - SELL: entry abajo del precio actual => SELL STOP (breakout)
                 entry arriba del precio actual => SELL LIMIT (pullback)
    """
    side_u = (side or "").upper().strip()
    delta = float(current_price) - float(entry)

    # Guardrail duro
    if abs(delta) > float(CFG.HARD_DRIFT):
        return "SKIP"

    if side_u == "BUY":
        # BUY: tolerancia asimétrica
        if delta > float(CFG.BUY_UP_TOL) or delta < -float(CFG.BUY_DOWN_TOL):
            # entry abajo del precio actual => LIMIT; entry arriba => STOP
            return "STOP" if float(entry) > float(current_price) else "LIMIT"
        return "MARKET"

    # SELL: tolerancia asimétrica
    if delta < -float(CFG.SELL_DOWN_TOL) or delta > float(CFG.SELL_UP_TOL):
        # entry abajo del precio actual => STOP; entry arriba => LIMIT
        return "STOP" if float(entry) < float(current_price) else "LIMIT"
    return "MARKET"


def tp_reached(side: str, tp: float, bid: float, ask: float) -> bool:
    if (side or "").upper().strip() == "BUY":
        return float(bid) >= float(tp)
    else:
        return float(ask) <= float(tp)


def min_stop_distance(constraints: dict, extra_buffer: float = 0.0) -> float:
    """Compute minimum stop distance in price units from symbol constraints + optional extra buffer."""
    point = float(constraints.get("point", 0.0) or 0.0)
    stops = int(constraints.get("stops_level_points", 0) or 0)
    freeze = int(constraints.get("freeze_level_points", 0) or 0)
    lvl = max(stops, freeze)
    return lvl * point + float(extra_buffer or 0.0)


def be_allowed(side: str, be_price: float, bid: float, ask: float, min_dist: float) -> bool:
    """Whether moving SL to be_price is allowed given current prices and min stop distance."""
    if (side or "").upper().strip() == "BUY":
        return (float(bid) - float(be_price)) >= float(min_dist)
    else:
        return (float(be_price) - float(ask)) >= float(min_dist)


def close_at_triggered(side: str, target: float, bid: float, ask: float, buffer: float = 0.0) -> bool:
    """Whether a CLOSE_AT target is triggered given current prices and optional buffer."""
    buf = float(buffer or 0.0)
    if (side or "").upper().strip() == "BUY":
        return float(bid) >= (float(target) + buf)
    else:
        return float(ask) <= (float(target) - buf)


