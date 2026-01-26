# adapters/mt5/types.py
"""
Tipos y dataclasses para el cliente MT5.
"""
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class Tick:
    """Representa un tick de precio del mercado."""
    bid: float
    ask: float
    last: float = 0.0
    time_msc: int = 0


@dataclass
class SymbolInfo:
    """Información de un símbolo."""
    name: str
    digits: int
    point: float
    stops_level: int
    freeze_level: int
    trade_mode: int
    visible: bool


@dataclass
class MT5Error:
    """Error retornado por MT5."""
    code: Optional[int]
    description: str


def to_tick(native_tick: Any) -> Tick:
    """
    Convierte un tick nativo de MT5 a nuestro tipo Tick.
    
    Args:
        native_tick: Tick retornado por mt5.symbol_info_tick()
    
    Returns:
        Tick normalizado
    """
    if native_tick is None:
        return Tick(bid=0.0, ask=0.0, last=0.0, time_msc=0)
    
    return Tick(
        bid=float(getattr(native_tick, "bid", 0.0) or 0.0),
        ask=float(getattr(native_tick, "ask", 0.0) or 0.0),
        last=float(getattr(native_tick, "last", 0.0) or 0.0),
        time_msc=int(getattr(native_tick, "time_msc", 0) or 0),
    )


def to_symbol_info(native_info: Any) -> Optional[SymbolInfo]:
    """
    Convierte información nativa de símbolo a nuestro tipo.
    
    Args:
        native_info: Info retornada por mt5.symbol_info()
    
    Returns:
        SymbolInfo normalizado o None
    """
    if native_info is None:
        return None
    
    return SymbolInfo(
        name=str(getattr(native_info, "name", "")),
        digits=int(getattr(native_info, "digits", 2) or 2),
        point=float(getattr(native_info, "point", 0.01) or 0.01),
        stops_level=int(getattr(native_info, "stops_level", 0) or 0),
        freeze_level=int(getattr(native_info, "freeze_level", 0) or 0),
        trade_mode=int(getattr(native_info, "trade_mode", -1) or -1),
        visible=bool(getattr(native_info, "visible", False)),
    )


def get_mt5_error() -> MT5Error:
    """
    Obtiene el último error de MT5 de forma segura.
    
    Returns:
        MT5Error con código y descripción
    """
    import MetaTrader5 as mt5
    
    try:
        e = mt5.last_error()
        # MT5 returns tuple (code, description) in many builds
        if isinstance(e, tuple) and len(e) >= 2:
            return MT5Error(code=int(e[0]), description=str(e[1]))
        return MT5Error(code=None, description=str(e))
    except Exception as ex:
        return MT5Error(code=None, description=f"last_error_exception: {ex}")