# core/domain/models.py
"""
Modelos de dominio unificados.
Combina y mejora Signal, SplitState de archivos anteriores.
"""
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime, timezone

from .enums import OrderSide, OrderStatus


def _utc_now() -> datetime:
    """Retorna timestamp UTC actual."""
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    """Retorna timestamp UTC actual en formato ISO."""
    return _utc_now().isoformat()


# =========================
# Value Objects
# =========================

@dataclass(frozen=True)
class Price:
    """Representa un precio normalizado."""
    value: float
    
    def __post_init__(self):
        if self.value < 0:
            raise ValueError(f"Price cannot be negative: {self.value}")
    
    def __float__(self) -> float:
        return self.value
    
    def __str__(self) -> str:
        return f"{self.value:.5f}"


@dataclass(frozen=True)
class Volume:
    """Representa un volumen de trading."""
    value: float
    
    def __post_init__(self):
        if self.value <= 0:
            raise ValueError(f"Volume must be positive: {self.value}")
    
    def __float__(self) -> float:
        return self.value


@dataclass(frozen=True)
class Ticket:
    """Representa un ticket de MT5 (order o position)."""
    value: int
    
    def __post_init__(self):
        if self.value <= 0:
            raise ValueError(f"Ticket must be positive: {self.value}")
    
    def __int__(self) -> int:
        return self.value


# =========================
# Domain Entities
# =========================

@dataclass
class Signal:
    """
    Señal de trading parseada desde Telegram.
    Representa la intención de trading del usuario.
    """
    message_id: int
    symbol: str
    side: OrderSide
    entry: float
    tps: List[float]
    sl: float
    
    # Metadata
    created_at: str = field(default_factory=_utc_now_iso)
    
    def __post_init__(self):
        """Validaciones básicas."""
        if not self.tps:
            raise ValueError("Signal must have at least one TP")
        
        if self.side == OrderSide.BUY:
            # BUY: TPs deben estar arriba del entry, SL abajo
            if not all(tp > self.entry for tp in self.tps):
                raise ValueError(f"BUY signal: all TPs must be > entry ({self.entry})")
            if self.sl >= self.entry:
                raise ValueError(f"BUY signal: SL ({self.sl}) must be < entry ({self.entry})")
        else:
            # SELL: TPs deben estar abajo del entry, SL arriba
            if not all(tp < self.entry for tp in self.tps):
                raise ValueError(f"SELL signal: all TPs must be < entry ({self.entry})")
            if self.sl <= self.entry:
                raise ValueError(f"SELL signal: SL ({self.sl}) must be > entry ({self.entry})")
    
    @property
    def num_tps(self) -> int:
        """Número de TPs en la señal."""
        return len(self.tps)


@dataclass
class Position:
    """
    Representa una posición individual (split de una señal).
    Incluye todo el ciclo de vida: NEW -> PENDING -> OPEN -> CLOSED/CANCELED.
    """
    # Identificación
    split_id: str
    split_index: int
    signal_message_id: int
    
    # Datos de trading
    symbol: str
    side: OrderSide
    entry: float
    tp: float
    sl: float
    volume: float
    
    # Estado
    status: OrderStatus = OrderStatus.NEW
    
    # MT5 references
    order_ticket: Optional[int] = None
    position_ticket: Optional[int] = None
    
    # Timestamps
    created_at: str = field(default_factory=_utc_now_iso)
    pending_created_ts: Optional[float] = None
    open_ts: Optional[float] = None
    closed_ts: Optional[float] = None
    
    # Execution details
    open_price: Optional[float] = None
    close_price: Optional[float] = None
    
    # Last MT5 interaction
    last_request: Optional[dict] = None
    last_response: Optional[str] = None
    
    # Management flags - Break Even
    be_armed: bool = False
    be_done: bool = False
    be_attempts: int = 0
    be_applied_ts: Optional[float] = None
    
    # Management flags - Move SL
    sl_move_armed: bool = False
    sl_move_done: bool = False
    sl_move_attempts: int = 0
    sl_move_applied_ts: Optional[float] = None
    
    # Management flags - Close At
    close_armed: bool = False
    close_done: bool = False
    close_target: Optional[float] = None
    close_attempts: int = 0
    close_applied_ts: Optional[float] = None
    
    def __post_init__(self):
        """Genera split_id si no existe."""
        if not self.split_id:
            object.__setattr__(
                self,
                'split_id',
                f"{self.signal_message_id}_split_{self.split_index}"
            )
    
    @property
    def is_pending(self) -> bool:
        """True si la orden está pendiente."""
        return self.status == OrderStatus.PENDING
    
    @property
    def is_open(self) -> bool:
        """True si la posición está abierta."""
        return self.status == OrderStatus.OPEN
    
    @property
    def is_closed(self) -> bool:
        """True si la posición está cerrada."""
        return self.status == OrderStatus.CLOSED
    
    @property
    def is_active(self) -> bool:
        """True si está pendiente o abierta (necesita monitoreo)."""
        return self.status in (OrderStatus.PENDING, OrderStatus.OPEN)
    
    @property
    def can_apply_be(self) -> bool:
        """True si puede aplicar break even."""
        return (
            self.is_open
            and self.be_armed
            and not self.be_done
            and self.position_ticket is not None
        )
    
    @property
    def can_move_sl(self) -> bool:
        """True si puede mover stop loss."""
        return (
            self.is_open
            and self.sl_move_armed
            and not self.sl_move_done
            and self.position_ticket is not None
        )
    
    @property
    def can_close_at(self) -> bool:
        """True si puede cerrar en target."""
        return (
            self.is_open
            and self.close_armed
            and not self.close_done
            and self.position_ticket is not None
        )
    
    def mark_pending(self, order_ticket: int, timestamp: Optional[float] = None) -> None:
        """Marca la posición como orden pendiente."""
        self.status = OrderStatus.PENDING
        self.order_ticket = order_ticket
        self.pending_created_ts = timestamp
    
    def mark_open(
        self,
        position_ticket: int,
        open_price: float,
        timestamp: Optional[float] = None
    ) -> None:
        """Marca la posición como abierta."""
        self.status = OrderStatus.OPEN
        self.position_ticket = position_ticket
        self.open_price = open_price
        self.open_ts = timestamp
    
    def mark_closed(self, close_price: Optional[float] = None, timestamp: Optional[float] = None) -> None:
        """Marca la posición como cerrada."""
        self.status = OrderStatus.CLOSED
        self.close_price = close_price
        self.closed_ts = timestamp
    
    def mark_canceled(self, timestamp: Optional[float] = None) -> None:
        """Marca la orden como cancelada."""
        self.status = OrderStatus.CANCELED
        self.closed_ts = timestamp
    
    def arm_be(self) -> None:
        """Arma el break even."""
        self.be_armed = True
        self.be_done = False
    
    def apply_be(self, timestamp: Optional[float] = None) -> None:
        """Marca el BE como aplicado."""
        self.be_done = True
        self.be_armed = False
        self.be_applied_ts = timestamp
    
    def arm_sl_move(self, new_sl: float) -> None:
        """Arma el movimiento de SL."""
        self.sl = new_sl
        self.sl_move_armed = True
        self.sl_move_done = False
    
    def apply_sl_move(self, timestamp: Optional[float] = None) -> None:
        """Marca el MOVE_SL como aplicado."""
        self.sl_move_done = True
        self.sl_move_armed = False
        self.sl_move_applied_ts = timestamp
    
    def arm_close(self, target: Optional[float] = None) -> None:
        """Arma el cierre en target."""
        self.close_armed = True
        self.close_done = False
        self.close_target = target
    
    def apply_close(self, timestamp: Optional[float] = None) -> None:
        """Marca el CLOSE como aplicado."""
        self.close_done = True
        self.close_armed = False
        self.close_applied_ts = timestamp


@dataclass
class MessageCache:
    """
    Cache de mensajes de Telegram para manejo de edits.
    """
    msg_id: int
    first_seen_ts: str = field(default_factory=_utc_now_iso)
    last_seen_ts: str = field(default_factory=_utc_now_iso)
    text_last: str = ""
    parse_failed: bool = False
    parse_attempts: int = 0
    
    def update(self, text: str) -> None:
        """Actualiza el cache con nuevo texto."""
        self.last_seen_ts = _utc_now_iso()
        self.text_last = text
    
    def mark_parse_attempt(self, failed: bool) -> None:
        """Registra un intento de parseo."""
        self.parse_attempts += 1
        self.parse_failed = failed
        self.last_seen_ts = _utc_now_iso()
    
    def within_window(self, window_seconds: int) -> bool:
        """Verifica si está dentro de la ventana de reprocesamiento."""
        try:
            first = datetime.fromisoformat(self.first_seen_ts)
            last = datetime.fromisoformat(self.last_seen_ts)
            delta = (last - first).total_seconds()
            return delta <= float(window_seconds)
        except (ValueError, TypeError):
            # Si hay error parseando timestamps, ser permisivo
            return True