import re
from typing import Optional, List
from core.models import Signal

# ---- Helpers regex ----

# "XAUUSD BUY 4832"
re_symbol_side_entry = re.compile(r"\bXAUUSD\b\s*(?:\|\s*)?(BUY|SELL)\b[^\d]*(\d+(?:\.\d+)?)", re.IGNORECASE)

# "BUY XAUUSD 4827"
re_side_symbol_entry = re.compile(r"\b(BUY|SELL)\b\s+XAUUSD\b[^\d]*(\d+(?:\.\d+)?)", re.IGNORECASE)

# "SELL @ 4832" / "SELL 4832" / "SELL AT 4832"
re_side_entry_line = re.compile(r"\b(BUY|SELL)\b\s*(?:@|AT)?\s*(\d+(?:\.\d+)?)\b", re.IGNORECASE)

# "ENTRY: 4832" / "ENTRY=4832"
re_open_entry = re.compile(r"\bENTRY\b\s*[:=]?\s*(\d+(?:\.\d+)?)\b", re.IGNORECASE)

# "SL: 4844" / "SL 4844" / "SL=4844"
re_sl = re.compile(r"\bSL\b\s*[:=]?\s*(\d+(?:\.\d+)?)\b", re.IGNORECASE)

# "TP1:4830" / "TP 4835" / "TP2 = 4825"
re_tp = re.compile(r"\bTP\d*\b\s*[:=]?\s*(\d+(?:\.\d+)?)\b", re.IGNORECASE)

# "TP3: open" / "TP open" (no numérico) -> se ignora por definición
re_tp_open = re.compile(r"\bTP\d*\b\s*[:=]?\s*open\b", re.IGNORECASE)

# Header para side sin entry: "XAUUSD | SELL NOW" / "XAUUSD SELL NOW"
re_header_side = re.compile(r"\bXAUUSD\b.*\b(BUY|SELL)\b", re.IGNORECASE)


def _dedup_preserve_order(values: List[float]) -> List[float]:
    seen = set()
    out: List[float] = []
    for v in values:
        if v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


def parse_signal(text: str, msg_id: int) -> Optional[Signal]:
    t = (text or "").strip()
    if not t:
        return None

    up = t.upper()
    # Seguridad: solo intentamos parsear señales de XAUUSD
    if "XAUUSD" not in up:
        return None

    side: Optional[str] = None
    entry: Optional[float] = None

    # 1) Extraer side (aunque sea del header)
    mh = re_header_side.search(t)
    if mh:
        side = mh.group(1).upper()

    # 2) Extraer side + entry con patrones más específicos primero
    m = re_symbol_side_entry.search(t)
    if m:
        side = (side or m.group(1)).upper()
        entry = float(m.group(2))

    if entry is None:
        m = re_side_symbol_entry.search(t)
        if m:
            side = (side or m.group(1)).upper()
            entry = float(m.group(2))

    # 3) ENTRY explícito (si viene)
    m2 = re_open_entry.search(t)
    if m2:
        entry = float(m2.group(1))

    # 4) Línea "BUY/SELL @ 4832" / "SELL AT 4832"
    if entry is None:
        m3 = re_side_entry_line.search(t)
        if m3:
            side = (side or m3.group(1)).upper()
            entry = float(m3.group(2))

    if not side or entry is None:
        return None

    # SL (opcional, el default SL se decide fuera)
    sl = None
    msl = re_sl.search(t)
    if msl:
        sl = float(msl.group(1))

    # Ignorar TP open (no numérico)
    # (No hace falta remover nada: re_tp solo toma numéricos)
    _ = re_tp_open.search(t)

    # TP numéricos
    tps = [float(x) for x in re_tp.findall(t)]
    tps = _dedup_preserve_order(tps)

    # Reglas del bot: si no hay TPs numéricos, no es señal válida
    if not tps:
        return None

    return Signal(message_id=msg_id, side=side, entry=entry, sl=sl, tps=tps)
