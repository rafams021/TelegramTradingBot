from dataclasses import dataclass
from typing import Optional, List


@dataclass
class Signal:
    message_id: int
    side: str
    entry: float
    sl: Optional[float]
    tps: List[float]


@dataclass
class SplitState:
    signal_msg_id: int
    split_index: int

    # signal context
    side: str
    entry: float
    tp: float
    sl: float

    # lifecycle
    status: str  # NEW, OPEN, PENDING, CLOSED, CANCELED
    order_ticket: Optional[int] = None
    position_ticket: Optional[int] = None
    created_ts: float = 0.0

    # real fill info (when OPEN)
    open_price: Optional[float] = None  # price_open real (preferido para BE)

    # BE workflow
    be_armed: bool = False
    be_done: bool = False
    be_requested_ts: Optional[float] = None
    be_applied_ts: Optional[float] = None
    be_attempts: int = 0

    # CLOSE_AT workflow
    close_target: Optional[float] = None
    close_armed: bool = False
    close_done: bool = False
    close_requested_ts: Optional[float] = None
    close_applied_ts: Optional[float] = None
    close_attempts: int = 0
