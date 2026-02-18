# core/state.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

import config as CFG


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Signal:
    message_id: int
    symbol: str
    side: str
    entry: float
    tps: List[float]
    sl: float


@dataclass
class SplitState:
    split_index: int
    side: str
    entry: float
    sl: float
    tp: float

    status: str = "NEW"
    order_ticket: Optional[int] = None
    position_ticket: Optional[int] = None
    open_price: Optional[float] = None

    be_armed: bool = False
    be_done: bool = False
    be_attempts: int = 0
    be_applied_ts: Optional[str] = None

    close_armed: bool = False
    close_target: Optional[float] = None
    close_done: bool = False
    close_attempts: int = 0
    close_applied_ts: Optional[str] = None

    sl_move_armed: bool = False
    sl_move_done: bool = False
    sl_move_attempts: int = 0
    sl_move_applied_ts: Optional[float] = None


@dataclass
class SignalState:
    signal: Signal
    splits: List[SplitState] = field(default_factory=list)


class BotState:
    def __init__(self) -> None:
        self.signals: Dict[int, SignalState] = {}

    def has_signal(self, signal_msg_id: int) -> bool:
        return signal_msg_id in self.signals

    def add_signal(self, signal: Signal) -> None:
        if signal.message_id in self.signals:
            return
        self.signals[signal.message_id] = SignalState(signal=signal)

    def get_signal(self, signal_msg_id: int) -> Optional[SignalState]:
        return self.signals.get(signal_msg_id)

    def build_splits_for_signal(self, signal_msg_id: int) -> List[SplitState]:
        st = self.signals.get(signal_msg_id)
        if st is None:
            return []

        if st.splits:
            return st.splits

        sig = st.signal
        splits: List[SplitState] = []
        max_splits = int(getattr(CFG, "MAX_SPLITS", 0) or 0)

        for i, tp in enumerate(sig.tps):
            if max_splits > 0 and i >= max_splits:
                break
            splits.append(
                SplitState(
                    split_index=i,
                    side=sig.side,
                    entry=sig.entry,
                    sl=sig.sl,
                    tp=tp,
                )
            )

        st.splits = splits
        return splits


# Backward compatibility
State = BotState

BOT_STATE = BotState()