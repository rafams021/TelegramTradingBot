# utils/validators.py
"""
Validadores de datos para el bot.
"""
from typing import Optional


def validate_price(price: float, min_price: float = 0.0) -> bool:
    """
    Valida un precio.
    
    Args:
        price: Precio a validar
        min_price: Precio mínimo permitido
    
    Returns:
        True si es válido
    
    Raises:
        ValueError: Si el precio es inválido
    """
    if not isinstance(price, (int, float)):
        raise ValueError(f"Price must be numeric, got {type(price)}")
    
    if price < min_price:
        raise ValueError(f"Price {price} must be >= {min_price}")
    
    return True


def validate_volume(volume: float, min_volume: float = 0.01, max_volume: float = 100.0) -> bool:
    """
    Valida un volumen (lotes).
    
    Args:
        volume: Volumen a validar
        min_volume: Volumen mínimo
        max_volume: Volumen máximo
    
    Returns:
        True si es válido
    
    Raises:
        ValueError: Si el volumen es inválido
    """
    if not isinstance(volume, (int, float)):
        raise ValueError(f"Volume must be numeric, got {type(volume)}")
    
    if volume < min_volume:
        raise ValueError(f"Volume {volume} must be >= {min_volume}")
    
    if volume > max_volume:
        raise ValueError(f"Volume {volume} must be <= {max_volume}")
    
    return True


def validate_symbol(symbol: str, allowed_symbols: Optional[list] = None) -> bool:
    """
    Valida un símbolo de trading.
    
    Args:
        symbol: Símbolo a validar (ej: "XAUUSD")
        allowed_symbols: Lista de símbolos permitidos (opcional)
    
    Returns:
        True si es válido
    
    Raises:
        ValueError: Si el símbolo es inválido
    """
    if not isinstance(symbol, str):
        raise ValueError(f"Symbol must be string, got {type(symbol)}")
    
    if not symbol or not symbol.strip():
        raise ValueError("Symbol cannot be empty")
    
    symbol = symbol.strip().upper()
    
    if allowed_symbols and symbol not in allowed_symbols:
        raise ValueError(f"Symbol {symbol} not in allowed list: {allowed_symbols}")
    
    return True


def validate_tp_sl_relationship(side: str, entry: float, tp: float, sl: float) -> bool:
    """
    Valida la relación entre entry, TP y SL según el lado.
    
    Args:
        side: "BUY" o "SELL"
        entry: Precio de entrada
        tp: Take Profit
        sl: Stop Loss
    
    Returns:
        True si es válido
    
    Raises:
        ValueError: Si la relación es inválida
    """
    side = side.upper().strip()
    
    if side == "BUY":
        # BUY: TP > entry, SL < entry
        if tp <= entry:
            raise ValueError(f"BUY: TP ({tp}) must be > entry ({entry})")
        if sl >= entry:
            raise ValueError(f"BUY: SL ({sl}) must be < entry ({entry})")
    
    elif side == "SELL":
        # SELL: TP < entry, SL > entry
        if tp >= entry:
            raise ValueError(f"SELL: TP ({tp}) must be < entry ({entry})")
        if sl <= entry:
            raise ValueError(f"SELL: SL ({sl}) must be > entry ({entry})")
    
    else:
        raise ValueError(f"Invalid side: {side}. Must be BUY or SELL")
    
    return True


def validate_ticket(ticket: int) -> bool:
    """
    Valida un ticket de MT5.
    
    Args:
        ticket: Ticket a validar
    
    Returns:
        True si es válido
    
    Raises:
        ValueError: Si el ticket es inválido
    """
    if not isinstance(ticket, int):
        raise ValueError(f"Ticket must be integer, got {type(ticket)}")
    
    if ticket <= 0:
        raise ValueError(f"Ticket {ticket} must be > 0")
    
    return True


def validate_message_id(msg_id: int) -> bool:
    """
    Valida un ID de mensaje de Telegram.
    
    Args:
        msg_id: ID a validar
    
    Returns:
        True si es válido
    
    Raises:
        ValueError: Si el ID es inválido
    """
    if not isinstance(msg_id, int):
        raise ValueError(f"Message ID must be integer, got {type(msg_id)}")
    
    if msg_id <= 0:
        raise ValueError(f"Message ID {msg_id} must be > 0")
    
    return True


def validate_tps_list(tps: list, side: str, entry: float) -> bool:
    """
    Valida una lista de TPs.
    
    Args:
        tps: Lista de Take Profits
        side: "BUY" o "SELL"
        entry: Precio de entrada
    
    Returns:
        True si es válida
    
    Raises:
        ValueError: Si la lista es inválida
    """
    if not isinstance(tps, list):
        raise ValueError(f"TPs must be list, got {type(tps)}")
    
    if not tps:
        raise ValueError("TPs list cannot be empty")
    
    side = side.upper().strip()
    
    for i, tp in enumerate(tps):
        if not isinstance(tp, (int, float)):
            raise ValueError(f"TP[{i}] must be numeric, got {type(tp)}")
        
        if side == "BUY" and tp <= entry:
            raise ValueError(f"BUY: TP[{i}] ({tp}) must be > entry ({entry})")
        
        if side == "SELL" and tp >= entry:
            raise ValueError(f"SELL: TP[{i}] ({tp}) must be < entry ({entry})")
    
    return True