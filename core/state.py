import time
from dataclasses import dataclass
from typing import Dict, Optional, List

import config as CFG
from core.models import Signal, SplitState


@dataclass
class SignalMemory:
    signal: Signal
    splits: List[SplitState]


class BotState:
    """
    Estado en memoria. Guarda señales y splits.
    La lógica de trading/MT5 vive en executor/watcher.
    """

    def __init__(self) -> None:
        self.signals: Dict[int, SignalMemory] = {}

    def get_signal(self, signal_msg_id: int) -> Optional[SignalMemory]:
        return self.signals.get(signal_msg_id)

    def add_signal(self, msg_id: int, sig: Signal) -> None:
        if msg_id not in self.signals:
            self.signals[msg_id] = SignalMemory(signal=sig, splits=[])

    def build_splits_for_signal(self, msg_id: int) -> List[SplitState]:
        mem = self.signals.get(msg_id)
        if mem is None:
            return []

        sig = mem.signal
        # SL default si no viene
        sl = float(sig.sl) if sig.sl is not None else (
            float(sig.entry) - float(CFG.DEFAULT_SL_DISTANCE)
            if sig.side.upper() == "BUY"
            else float(sig.entry) + float(CFG.DEFAULT_SL_DISTANCE)
        )

        tps = list(sig.tps)[: int(CFG.MAX_SPLITS)]
        now = time.time()

        splits: List[SplitState] = []
        for i, tp in enumerate(tps):
            splits.append(
                SplitState(
                    signal_msg_id=msg_id,
                    split_index=i,
                    side=sig.side.upper(),
                    entry=float(sig.entry),
                    tp=float(tp),
                    sl=float(sl),
                    status="NEW",
                    created_ts=now,
                )
            )

        mem.splits = splits
        return splits
