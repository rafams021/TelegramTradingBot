from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

import config as CFG
from core.models import Signal


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SplitState:
    split_index: int
    side: str
    entry: float
    sl: float
    tp: float

    status: str = "PENDING"  # PENDING / OPEN / CLOSED / CANCELED
    order_ticket: Optional[int] = None
    position_ticket: Optional[int] = None
    open_price: Optional[float] = None

    # BE
    be_armed: bool = False
    be_done: bool = False
    be_attempts: int = 0
    be_applied_ts: Optional[str] = None

    # Close-at-price (optional management)
    close_armed: bool = False
    close_target: Optional[float] = None
    close_done: bool = False
    close_attempts: int = 0
    close_applied_ts: Optional[str] = None


@dataclass
class SignalState:
    signal: Signal
    splits: List[SplitState] = field(default_factory=list)


@dataclass
class MsgCacheEntry:
    msg_id: int
    first_seen_ts: str = field(default_factory=_utc_now_iso)
    last_seen_ts: str = field(default_factory=_utc_now_iso)
    text_last: str = ""
    parse_failed: bool = False
    parse_attempts: int = 0

    def within_edit_window(self, window_s: int) -> bool:
        try:
            first = datetime.fromisoformat(self.first_seen_ts)
            last = datetime.fromisoformat(self.last_seen_ts)
            return (last - first).total_seconds() <= float(window_s)
        except Exception:
            # if parsing timestamps fails, be permissive
            return True


class BotState:
    def __init__(self) -> None:
        self.signals: Dict[int, SignalState] = {}
        self.msg_cache: Dict[int, MsgCacheEntry] = {}

        # Telegram safety: ignore backlog/catch-up messages after restart.
        # Set once at TG_READY by main.py via utils.set_tg_startup_cutoff(...)
        self.tg_startup_cutoff_iso: Optional[str] = None

    def upsert_msg_cache(self, msg_id: int, text: str) -> MsgCacheEntry:
        e = self.msg_cache.get(msg_id)
        if e is None:
            e = MsgCacheEntry(msg_id=msg_id, text_last=text)
            self.msg_cache[msg_id] = e
        e.last_seen_ts = _utc_now_iso()
        e.text_last = text
        return e

    def mark_parse_attempt(self, msg_id: int, parse_failed: bool) -> None:
        e = self.msg_cache.get(msg_id)
        if e is None:
            e = MsgCacheEntry(msg_id=msg_id)
            self.msg_cache[msg_id] = e
        e.parse_attempts += 1
        e.parse_failed = parse_failed
        e.last_seen_ts = _utc_now_iso()

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

        # Do not rebuild splits if they already exist
        if st.splits:
            return st.splits

        sig = st.signal
        splits: List[SplitState] = []

        max_splits = int(getattr(CFG, "MAX_SPLITS", 0) or 0)

        for i, tp in enumerate(sig.tps):
            # MAX_SPLITS: 0 or missing means "no cap"
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


BOT_STATE = BotState()
