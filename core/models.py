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
    entry: float
    tp: float
    sl: float
    status: str          # NEW, OPEN, PENDING, CLOSED, CANCELED
    order_ticket: Optional[int] = None
    position_ticket: Optional[int] = None
    created_ts: float = 0.0
