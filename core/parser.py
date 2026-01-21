import re
from typing import Optional, List
from core.models import Signal

re_open_simple = re.compile(r"\bXAUUSD\s+(BUY|SELL)\s+(\d+(?:\.\d+)?)\b", re.IGNORECASE)
re_open_entry  = re.compile(r"\bENTRY\s*[:=]\s*(\d+(?:\.\d+)?)\b", re.IGNORECASE)
re_sl          = re.compile(r"\bSL\s*[:=]\s*(\d+(?:\.\d+)?)\b", re.IGNORECASE)
re_tp          = re.compile(r"\bTP\d*\s*[:=]?\s*(\d+(?:\.\d+)?)\b", re.IGNORECASE)
re_tp_open     = re.compile(r"\bTP\s+open\b", re.IGNORECASE)

def parse_signal(text: str, msg_id: int) -> Optional[Signal]:
    t = text.strip()

    side = None
    entry = None

    m = re_open_simple.search(t)
    if m:
        side = m.group(1).upper()
        entry = float(m.group(2))

    m2 = re_open_entry.search(t)
    if m2:
        entry = float(m2.group(1))

    if not side or entry is None:
        return None

    sl = None
    msl = re_sl.search(t)
    if msl:
        sl = float(msl.group(1))

    if re_tp_open.search(t):
        # ignoramos TP open
        pass

    tps = [float(x) for x in re_tp.findall(t)]

    return Signal(message_id=msg_id, side=side, entry=entry, sl=sl, tps=tps)
