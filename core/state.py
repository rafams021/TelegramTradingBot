from typing import Dict, List, Optional
from core.models import SplitState


class BotState:
    """
    Estado en memoria. No contiene lógica de trading.
    Solo almacena y devuelve splits por signal_msg_id.
    """

    def __init__(self) -> None:
        self.signals: Dict[int, List[SplitState]] = {}

    def get_splits(self, signal_msg_id: int) -> List[SplitState]:
        return self.signals.get(signal_msg_id, [])

    def set_splits(self, signal_msg_id: int, splits: List[SplitState]) -> None:
        self.signals[signal_msg_id] = splits

    def items(self):
        return list(self.signals.items())
