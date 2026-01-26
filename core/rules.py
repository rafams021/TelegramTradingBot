# core/rules.py
"""
Reglas de negocio para decisiones de trading.

Funciones principales:
- decide_execution: Decide cómo ejecutar una señal (MARKET/LIMIT/STOP/SKIP)
- tp_reached: Verifica si un TP fue alcanzado
- be_allowed: Verifica si break even es permitido
- close_at_triggered: Verifica si cierre en target es permitido
"""
from __future__ import annotations

import config as CFG
from core.domain.enums import OrderSide, ExecutionMode


def decide_execution(
    side: OrderSide,
    entry: float,
    current_price: float
) -> ExecutionMode:
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
    
    Args:
        side: Lado de la operación (OrderSide.BUY o OrderSide.SELL)
        entry: Precio de entrada de la señal
        current_price: Precio actual del mercado
    
    Returns:
        ExecutionMode apropiado (MARKET, LIMIT, STOP, o SKIP)
    """
    delta = float(current_price) - float(entry)

    # Guardrail duro: si está demasiado lejos, no operar
    if abs(delta) > float(CFG.HARD_DRIFT):
        return ExecutionMode.SKIP

    if side == OrderSide.BUY:
        # BUY: tolerancia asimétrica
        if delta > float(CFG.BUY_UP_TOL) or delta < -float(CFG.BUY_DOWN_TOL):
            # entry abajo del precio actual => LIMIT; entry arriba => STOP
            return ExecutionMode.STOP if float(entry) > float(current_price) else ExecutionMode.LIMIT
        return ExecutionMode.MARKET

    # SELL: tolerancia asimétrica
    if delta < -float(CFG.SELL_DOWN_TOL) or delta > float(CFG.SELL_UP_TOL):
        # entry abajo del precio actual => STOP; entry arriba => LIMIT
        return ExecutionMode.STOP if float(entry) < float(current_price) else ExecutionMode.LIMIT
    return ExecutionMode.MARKET


def decide_execution_legacy(side: str, entry: float, current_price: float) -> str:
    """
    Versión legacy que acepta strings.
    
    DEPRECADO: Usar decide_execution() con OrderSide enum.
    Mantenido para backward compatibility.
    
    Args:
        side: "BUY" o "SELL"
        entry: Precio de entrada
        current_price: Precio actual
    
    Returns:
        "MARKET", "LIMIT", "STOP", o "SKIP"
    """
    side_u = (side or "").upper().strip()
    
    if side_u == "BUY":
        order_side = OrderSide.BUY
    elif side_u == "SELL":
        order_side = OrderSide.SELL
    else:
        return "SKIP"
    
    result = decide_execution(order_side, entry, current_price)
    return result.value


def tp_reached(side: str, tp: float, bid: float, ask: float) -> bool:
    """
    Verifica si un Take Profit fue alcanzado.
    
    BUY: TP se alcanza cuando bid >= tp (vendemos al bid)
    SELL: TP se alcanza cuando ask <= tp (compramos al ask)
    
    Args:
        side: "BUY" o "SELL"
        tp: Precio del take profit
        bid: Precio bid actual
        ask: Precio ask actual
    
    Returns:
        True si el TP fue alcanzado
    """
    if (side or "").upper().strip() == "BUY":
        return float(bid) >= float(tp)
    else:
        return float(ask) <= float(tp)


def min_stop_distance(constraints: dict, extra_buffer: float = 0.0) -> float:
    """
    Calcula la distancia mínima de stop según las restricciones del símbolo.
    
    MT5 tiene restricciones de "stops_level" y "freeze_level" que determinan
    qué tan cerca del precio actual puedes colocar SL/TP.
    
    Args:
        constraints: Dict con point, stops_level_points, freeze_level_points
        extra_buffer: Buffer adicional opcional en unidades de precio
    
    Returns:
        Distancia mínima en unidades de precio
    """
    point = float(constraints.get("point", 0.0) or 0.0)
    stops = int(constraints.get("stops_level_points", 0) or 0)
    freeze = int(constraints.get("freeze_level_points", 0) or 0)
    lvl = max(stops, freeze)
    return lvl * point + float(extra_buffer or 0.0)


def be_allowed(side: str, be_price: float, bid: float, ask: float, min_dist: float) -> bool:
    """
    Verifica si mover el SL a break even es permitido.
    
    El SL debe estar a una distancia mínima del precio actual según
    las restricciones del broker.
    
    BUY: Verificamos que (bid - be_price) >= min_dist
    SELL: Verificamos que (be_price - ask) >= min_dist
    
    Args:
        side: "BUY" o "SELL"
        be_price: Precio al que queremos mover el SL (break even)
        bid: Precio bid actual
        ask: Precio ask actual
        min_dist: Distancia mínima requerida
    
    Returns:
        True si es permitido mover el SL al precio de break even
    """
    if (side or "").upper().strip() == "BUY":
        return (float(bid) - float(be_price)) >= float(min_dist)
    else:
        return (float(be_price) - float(ask)) >= float(min_dist)


def close_at_triggered(side: str, target: float, bid: float, ask: float, buffer: float = 0.0) -> bool:
    """
    Verifica si se debe cerrar en un target específico.
    
    Permite un buffer opcional para dar margen antes de cerrar.
    
    BUY: Cerramos cuando bid >= (target + buffer)
    SELL: Cerramos cuando ask <= (target - buffer)
    
    Args:
        side: "BUY" o "SELL"
        target: Precio objetivo para cerrar
        bid: Precio bid actual
        ask: Precio ask actual
        buffer: Buffer opcional en unidades de precio
    
    Returns:
        True si se debe cerrar la posición
    """
    buf = float(buffer or 0.0)
    if (side or "").upper().strip() == "BUY":
        return float(bid) >= (float(target) + buf)
    else:
        return float(ask) <= (float(target) - buf)
