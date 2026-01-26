# core/parser.py
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from core.models import Signal

# We keep this parser intentionally lightweight and tolerant. The bot should be able to
# parse both clean formatted signals and common variations seen in Telegram edits.

_SYMBOL_RE = re.compile(r"\bXAUUSD\b", re.IGNORECASE)

_BUY_RE = re.compile(r"\bBUY\b", re.IGNORECASE)
_SELL_RE = re.compile(r"\bSELL\b", re.IGNORECASE)

_ENTRY_AFTER_SIDE_RE = re.compile(
    r"\b(?:BUY|SELL)\b\s*@?\s*(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)

# Entry zones seen as: "(4982.5-4981.5)" (hyphen or en-dash)
_ENTRY_RANGE_RE = re.compile(
    r"\(\s*(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*\)",
    re.IGNORECASE,
)

_TP_RE = re.compile(r"\bTP\s*\d*\s*[:\s]+(\d+(?:\.\d+)?)", re.IGNORECASE)

# SL variants: "SL:", "SL 4900", "STOP LOSS:", "STOPLOSS:" etc.
_SL_RE = re.compile(
    r"\b(?:SL|S/L|STOP\s*LOSS|STOPLOSS)\b\s*[:\s]+(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


def parse_signal(text: str) -> Optional[Signal]:
    """Parse a Telegram message into a Signal.

    Expected (tolerant) formats include:
      - "XAUUSD | BUY\nBUY @ 4910\nTP1: 4912 ...\nSL: 4900"
      - "XAUUSD SELL 4880\nTP 4875 ...\nSTOP LOSS: 4887"
      - "XAUUSD BUY\nBUY @ (4982.5-4981.5)\nTP1: ...\nSL: ..."

    Returns None if we can't confidently parse a trade signal.
    """
    if not text:
        return None

    if not _SYMBOL_RE.search(text):
        return None

    side = _extract_side(text)
    if side is None:
        return None

    tps = _extract_tps(text)
    sl = _extract_sl(text)

    entry = _extract_entry(text, side=side)

    # Require at minimum entry and SL, and at least one TP.
    if entry is None or sl is None or not tps:
        return None

    return Signal(symbol="XAUUSD", side=side, entry=entry, tps=tps, sl=sl)


def _extract_side(text: str) -> Optional[str]:
    # Prefer explicit BUY/SELL tokens.
    if _BUY_RE.search(text):
        return "BUY"
    if _SELL_RE.search(text):
        return "SELL"
    return None


def _extract_entry(text: str, side: str) -> Optional[float]:
    # First handle entry zones like (a-b)
    rng = _ENTRY_RANGE_RE.search(text)
    if rng:
        a = float(rng.group(1))
        b = float(rng.group(2))
        lo, hi = (a, b) if a <= b else (b, a)
        # For BUY we prefer the better (lower) price; for SELL the higher.
        return lo if side.upper() == "BUY" else hi

    m = _ENTRY_AFTER_SIDE_RE.search(text)
    if not m:
        return None
    return float(m.group(1))


def _extract_tps(text: str) -> List[float]:
    return [float(x) for x in _TP_RE.findall(text)]


def _extract_sl(text: str) -> Optional[float]:
    m = _SL_RE.search(text)
    return float(m.group(1)) if m else None
