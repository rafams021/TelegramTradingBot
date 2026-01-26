# core/domain/enums.py
"""
Enumeraciones para tipos, estados y acciones del sistema.
Centraliza valores que antes eran strings mágicos.
"""
from enum import Enum, auto


class OrderSide(str, Enum):
    """Lado de la orden (BUY/SELL)."""
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, Enum):
    """Estado de una orden o posición."""
    NEW = "NEW"              # Recién creado, no enviado a MT5
    PENDING = "PENDING"      # Orden pendiente en MT5
    OPEN = "OPEN"           # Posición abierta
    CLOSED = "CLOSED"       # Posición cerrada
    CANCELED = "CANCELED"   # Orden cancelada
    ERROR = "ERROR"         # Error en ejecución


class ExecutionMode(str, Enum):
    """Modo de ejecución de la orden."""
    MARKET = "MARKET"   # Ejecución inmediata a mercado
    LIMIT = "LIMIT"     # Orden límite pendiente
    STOP = "STOP"       # Orden stop pendiente
    SKIP = "SKIP"       # No ejecutar (fuera de rango)


class ManagementType(str, Enum):
    """Tipo de comando de gestión."""
    NONE = "NONE"                 # No es comando de gestión
    BE = "BE"                     # Break Even
    MOVE_SL = "MOVE_SL"           # Mover Stop Loss
    CLOSE_TP_AT = "CLOSE_TP_AT"   # Cerrar en TP específico
    CLOSE_ALL_AT = "CLOSE_ALL_AT" # Cerrar todas las posiciones


class MessageProcessStatus(str, Enum):
    """Estado del procesamiento de mensaje."""
    PROCESSED = "PROCESSED"
    IGNORED = "IGNORED"
    FAILED = "FAILED"
    PENDING = "PENDING"


class WatcherEventType(str, Enum):
    """Tipos de eventos del watcher."""
    PENDING_FILLED = "PENDING_FILLED"
    PENDING_CANCELED_TP = "PENDING_CANCELED_TP"
    PENDING_CANCELED_TIMEOUT = "PENDING_CANCELED_TIMEOUT"
    BE_ARMED = "BE_ARMED"
    BE_APPLIED = "BE_APPLIED"
    BE_FAILED = "BE_FAILED"
    MOVE_SL_ARMED = "MOVE_SL_ARMED"
    MOVE_SL_APPLIED = "MOVE_SL_APPLIED"
    MOVE_SL_FAILED = "MOVE_SL_FAILED"
    CLOSE_ARMED = "CLOSE_ARMED"
    CLOSE_APPLIED = "CLOSE_APPLIED"
    CLOSE_FAILED = "CLOSE_FAILED"