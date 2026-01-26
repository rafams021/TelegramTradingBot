from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Signal:
    message_id: int
    symbol: str
    side: str  # BUY / SELL
    entry: float
    tps: List[float]
    sl: float


@dataclass
class SplitState:
    split_id: str
    split_index: int
    side: str
    symbol: str

    entry: float
    tp: float
    sl: float

    vol: float
    status: str  # NEW / PENDING / OPEN / CLOSED / CANCELED / ERROR

    # MT5 link
    order_ticket: Optional[int] = None
    position_ticket: Optional[int] = None

    pending_created_ts: Optional[float] = None
    open_ts: Optional[float] = None
    open_price: Optional[float] = None

    # Raw MT5 last
    last_req: Optional[dict] = None
    last_res: Optional[str] = None

    # Management flags
    be_armed: bool = False
    be_done: bool = False
    be_attempts: int = 0
    be_applied_ts: Optional[float] = None

    close_armed: bool = False
    close_done: bool = False
    close_target: Optional[float] = None
    close_attempts: int = 0
    close_applied_ts: Optional[float] = None

    # Manual SL move support (e.g. "MOVER EL SL A 4890")
    sl_move_armed: bool = False
    sl_move_done: bool = False
    sl_move_attempts: int = 0
    sl_move_applied_ts: Optional[float] = None
