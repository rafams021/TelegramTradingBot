# utils/order_validator.py
"""
Validador de órdenes antes de enviar a MT5.
Previene errores como "Invalid price" (retcode 10015).
"""
from typing import Tuple, Optional
from core.domain.enums import OrderSide, ExecutionMode


class OrderValidationError(Exception):
    """Error de validación de orden."""
    pass


def validate_limit_order(
    side: OrderSide,
    entry: float,
    current_price: float,
    tolerance: float = 0.01
) -> Tuple[bool, Optional[str]]:
    """
    Valida que una orden LIMIT sea válida según las reglas de MT5.
    
    Reglas:
    - BUY LIMIT: entry debe estar ABAJO del current_price (pullback)
    - SELL LIMIT: entry debe estar ARRIBA del current_price (pullback)
    
    Args:
        side: Lado de la orden
        entry: Precio de entrada deseado
        current_price: Precio actual del mercado
        tolerance: Tolerancia en puntos para errores de redondeo
    
    Returns:
        Tuple de (is_valid, error_message)
        - (True, None) si es válida
        - (False, "reason") si no es válida
    
    Example:
        >>> validate_limit_order(OrderSide.BUY, 4900, 4910)
        (True, None)  # OK: entry abajo del precio
        
        >>> validate_limit_order(OrderSide.BUY, 4920, 4910)
        (False, "BUY LIMIT invalid: entry (4920) must be below current (4910)")
    """
    if side == OrderSide.BUY:
        # BUY LIMIT: entry debe estar abajo del current_price
        if entry >= (current_price - tolerance):
            return False, (
                f"BUY LIMIT invalid: entry ({entry}) must be below "
                f"current price ({current_price})"
            )
    
    elif side == OrderSide.SELL:
        # SELL LIMIT: entry debe estar arriba del current_price
        if entry <= (current_price + tolerance):
            return False, (
                f"SELL LIMIT invalid: entry ({entry}) must be above "
                f"current price ({current_price})"
            )
    
    return True, None


def validate_stop_order(
    side: OrderSide,
    entry: float,
    current_price: float,
    tolerance: float = 0.01
) -> Tuple[bool, Optional[str]]:
    """
    Valida que una orden STOP sea válida según las reglas de MT5.
    
    Reglas:
    - BUY STOP: entry debe estar ARRIBA del current_price (breakout)
    - SELL STOP: entry debe estar ABAJO del current_price (breakout)
    
    Args:
        side: Lado de la orden
        entry: Precio de entrada deseado
        current_price: Precio actual del mercado
        tolerance: Tolerancia en puntos
    
    Returns:
        Tuple de (is_valid, error_message)
    """
    if side == OrderSide.BUY:
        # BUY STOP: entry debe estar arriba del current_price
        if entry <= (current_price + tolerance):
            return False, (
                f"BUY STOP invalid: entry ({entry}) must be above "
                f"current price ({current_price})"
            )
    
    elif side == OrderSide.SELL:
        # SELL STOP: entry debe estar abajo del current_price
        if entry >= (current_price - tolerance):
            return False, (
                f"SELL STOP invalid: entry ({entry}) must be below "
                f"current price ({current_price})"
            )
    
    return True, None


def fix_invalid_limit_order(
    side: OrderSide,
    entry: float,
    current_price: float,
    mode: ExecutionMode
) -> ExecutionMode:
    """
    Intenta corregir una orden LIMIT inválida.
    
    Estrategia:
    1. Si LIMIT pero entry ya fue cruzado → cambiar a MARKET
    2. Si entry está muy lejos → cambiar a SKIP
    
    Args:
        side: Lado de la orden
        entry: Precio de entrada
        current_price: Precio actual
        mode: Modo actual (LIMIT)
    
    Returns:
        Modo corregido (MARKET o SKIP)
    
    Example:
        >>> fix_invalid_limit_order(OrderSide.SELL, 4948, 4954, ExecutionMode.LIMIT)
        ExecutionMode.MARKET  # Precio ya cruzó, ejecutar ya
    """
    if mode != ExecutionMode.LIMIT:
        return mode
    
    # Verificar si es inválido
    is_valid, _ = validate_limit_order(side, entry, current_price)
    
    if is_valid:
        return mode  # No necesita corrección
    
    # Precio ya cruzó el entry
    # Decidir entre MARKET (delta pequeño) o SKIP (delta grande)
    
    delta = abs(current_price - entry)
    
    # Si delta es pequeño (<2 puntos), ejecutar a mercado
    if delta < 2.0:
        return ExecutionMode.MARKET
    
    # Si delta es grande (>=2 puntos), mejor skip
    return ExecutionMode.SKIP


def validate_pending_order(
    side: OrderSide,
    mode: ExecutionMode,
    entry: float,
    current_price: float,
    sl: float,
    tp: float
) -> Tuple[bool, Optional[str]]:
    """
    Validación completa de orden pendiente antes de enviar.
    
    Args:
        side: Lado
        mode: Modo de ejecución
        entry: Precio de entrada
        current_price: Precio actual
        sl: Stop Loss
        tp: Take Profit
    
    Returns:
        Tuple de (is_valid, error_message)
    """
    # Validar según tipo de orden
    if mode == ExecutionMode.LIMIT:
        is_valid, error = validate_limit_order(side, entry, current_price)
        if not is_valid:
            return False, error
    
    elif mode == ExecutionMode.STOP:
        is_valid, error = validate_stop_order(side, entry, current_price)
        if not is_valid:
            return False, error
    
    # Validar relación TP/SL
    if side == OrderSide.BUY:
        if tp <= entry:
            return False, f"BUY: TP ({tp}) must be > entry ({entry})"
        if sl >= entry:
            return False, f"BUY: SL ({sl}) must be < entry ({entry})"
    else:
        if tp >= entry:
            return False, f"SELL: TP ({tp}) must be < entry ({entry})"
        if sl <= entry:
            return False, f"SELL: SL ({sl}) must be > entry ({entry})"
    
    return True, None


def should_retry_as_market(
    retcode: int,
    mode: ExecutionMode,
    side: OrderSide,
    entry: float,
    current_price: float
) -> bool:
    """
    Determina si después de un error 10015 (Invalid price)
    se debe reintentar como orden a MARKET.
    
    Args:
        retcode: Código de retorno de MT5
        mode: Modo que falló
        side: Lado de la orden
        entry: Precio de entrada
        current_price: Precio actual
    
    Returns:
        True si debe reintentar como MARKET
    
    Example:
        >>> should_retry_as_market(10015, ExecutionMode.LIMIT, OrderSide.BUY, 4900, 4905)
        True  # Entry ya fue alcanzado, ejecutar a mercado
    """
    # Solo para error 10015 (Invalid price)
    if retcode != 10015:
        return False
    
    # Solo para órdenes pendientes
    if mode not in (ExecutionMode.LIMIT, ExecutionMode.STOP):
        return False
    
    # Verificar si el precio ya cruzó el entry
    delta = abs(current_price - entry)
    
    # Si está muy cerca (< 1 punto), vale la pena ejecutar a mercado
    if delta < 1.0:
        return True
    
    return False