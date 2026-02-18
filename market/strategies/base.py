# market/strategies/base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import pandas as pd

import config as CFG
from core.state import Signal


class BaseStrategy(ABC):

    def __init__(self, symbol: str, magic: int):
        self.symbol = symbol
        self.magic = magic

    @abstractmethod
    def scan(
        self,
        df: pd.DataFrame,
        current_price: float,
    ) -> Optional[Signal]:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    def _is_valid_session(self, ts: pd.Timestamp) -> bool:
        """Filtro de sesion desde config. Compartido por todas las estrategias."""
        session_filter = getattr(CFG, "SESSION_FILTER", "24h")

        if session_filter == "24h":
            return True

        hour_utc = ts.hour

        if session_filter == "eu_ny":
            return 8 <= hour_utc < 22

        if session_filter == "ny_only":
            return 13 <= hour_utc < 22

        return True

    def _make_signal(
        self,
        side: str,
        entry: float,
        sl: float,
        tps: list,
        msg_id: int,
    ) -> Optional[Signal]:
        try:
            side_u = side.upper()

            if side_u == "BUY":
                if sl >= entry:
                    return None
                if not all(tp > entry for tp in tps):
                    return None
            else:
                if sl <= entry:
                    return None
                if not all(tp < entry for tp in tps):
                    return None

            return Signal(
                message_id=msg_id,
                symbol=self.symbol,
                side=side_u,
                entry=entry,
                tps=tps,
                sl=sl,
            )

        except Exception:
            return None