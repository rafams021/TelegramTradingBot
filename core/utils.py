from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple


def safe_text_sample(text: str, limit: int = 300) -> str:
    """Return a bounded-length sample for logging."""
    t = (text or "").strip()
    if len(t) <= limit:
        return t
    return t[:limit] + "…"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_dt(date_iso: Optional[str]) -> Optional[datetime]:
    if not date_iso:
        return None
    try:
        dt = datetime.fromisoformat(date_iso)
        # Ensure timezone-aware; Telethon dates are usually aware, but be safe.
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def set_tg_startup_cutoff(state) -> str:
    """Record the moment we started receiving Telegram updates."""
    ts = utc_now_iso()
    setattr(state, "tg_startup_cutoff_iso", ts)
    return ts


def should_process_tg_message(
    *,
    state,
    msg_id: int,
    msg_date_iso: Optional[str],
    is_edit: bool,
    tolerance_s: int = 5,
) -> Tuple[bool, str, Optional[str], Optional[float]]:
    """Decide if a Telegram message should be processed.

    Goal: prevent "catch-up" / backlog updates from being executed after bot restart.

    Rules:
      - If this is an edit for a message we already saw in this runtime, allow.
      - Otherwise, if msg.date is older than startup cutoff - tolerance, ignore.

    Returns: (ok, reason, cutoff_iso, age_seconds)
    """

    cutoff_iso = getattr(state, "tg_startup_cutoff_iso", None)
    cutoff_dt = _parse_dt(cutoff_iso)
    msg_dt = _parse_dt(msg_date_iso)

    # If we don't have a cutoff, be permissive.
    if cutoff_dt is None or msg_dt is None:
        return True, "no_cutoff_or_no_msg_date", cutoff_iso, None

    # Allow edits for messages we already handled in this runtime (avoid breaking edit flow).
    if is_edit:
        try:
            if hasattr(state, "msg_cache") and msg_id in state.msg_cache:
                return True, "edit_for_seen_message", cutoff_iso, (cutoff_dt - msg_dt).total_seconds()
        except Exception:
            # If msg_cache access fails, continue to staleness check.
            pass

    # Staleness check
    tol = timedelta(seconds=int(tolerance_s))
    if msg_dt < (cutoff_dt - tol):
        age_s = (cutoff_dt - msg_dt).total_seconds()
        return False, "stale_before_startup", cutoff_iso, age_s

    return True, "fresh", cutoff_iso, (cutoff_dt - msg_dt).total_seconds()
