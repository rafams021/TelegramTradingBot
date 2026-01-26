# core/domain/__init__.py
"""
Módulo de dominio - Modelos de negocio y enums.

Exports:
    - Enums: OrderSide, OrderStatus, ExecutionMode, ManagementType
    - Models: Signal, Position, MessageCache
    - Value Objects: Price, Volume, Ticket
"""

from .enums import (
    OrderSide,
    OrderStatus,
    ExecutionMode,
    ManagementType,
    MessageProcessStatus,
    WatcherEventType,
)

from .models import (
    Signal,
    Position,
    MessageCache,
    Price,
    Volume,
    Ticket,
)

__all__ = [
    # Enums
    "OrderSide",
    "OrderStatus",
    "ExecutionMode",
    "ManagementType",
    "MessageProcessStatus",
    "WatcherEventType",
    # Models
    "Signal",
    "Position",
    "MessageCache",
    # Value Objects
    "Price",
    "Volume",
    "Ticket",
]






