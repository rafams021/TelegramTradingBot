# core/parser.py
from __future__ import annotations

import re
from typing import List, Optional

from core.models import Signal

_SYMBOL_RE = re.compile(r"\bXAUUSD\b", re.I)
_BUY_RE = re.compile(r"\bBUY\b", re.I)
_SELL_RE = re.compile(r"\bSELL\b", re.I)

_NUM_RE = re.compile(r"(\d+(?:\.\d+)?)")
_TP_RE = re.compile(r"\bTP\s*\d*\s*[:\s]+(\d+(?:\.\d+)?)", re.I)
_SL_RE = re.compile(r"\bSL\s*[:\s]+(\d+(?:\.\d+)?)", re.I)


def _extract_entry(text: str) -> Optional[float]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for line in lines:
        # If side word is typo (BIU), we still have symbol line with number
        if _BUY_RE.search(line) or _SELL_RE.search(line) or _SYMBOL_RE.search(line):
            nums = _NUM_RE.findall(line)
            if nums:
                return float(nums[-1])
    m = _NUM_RE.search(text)
    return float(m.group(1)) if m else None


def _infer_side(entry: float, sl: float, tps: List[float]) -> Optional[str]:
    """
    Heurística para casos tipo "BIU":
      BUY  -> TP promedio > entry y SL < entry
      SELL -> TP promedio < entry y SL > entry
    """
    if not tps:
        return None
    tp_avg = sum(tps) / float(len(tps))

    if tp_avg > entry and sl < entry:
        return "BUY"
    if tp_avg < entry and sl > entry:
        return "SELL"
    return None


def parse_signal(msg_id: int, text: str) -> Optional[Signal]:
    t = text.strip()
    if not _SYMBOL_RE.search(t):
        return None

    sl_m = _SL_RE.search(t)
    if not sl_m:
        return None
    sl = float(sl_m.group(1))

    tps = [float(x) for x in _TP_RE.findall(t)]
    if not tps:
        return None

    entry = _extract_entry(t)
    if entry is None:
        return None

    side: Optional[str] = None
    if _BUY_RE.search(t):
        side = "BUY"
    elif _SELL_RE.search(t):
        side = "SELL"
    else:
        side = _infer_side(entry=entry, sl=sl, tps=tps)

    if side not in ("BUY", "SELL"):
        return None

    return Signal(message_id=msg_id, side=side, entry=entry, sl=sl, tps=tps)
