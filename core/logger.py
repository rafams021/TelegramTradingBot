import json
import os
import traceback
from datetime import datetime, timezone
from typing import Dict, Any
from config import LOG_FILE


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_log_dir() -> None:
    p = os.path.abspath(LOG_FILE)
    d = os.path.dirname(p)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


def log(ev: Dict[str, Any]) -> None:
    _ensure_log_dir()
    e = dict(ev)
    e["ts"] = e.get("ts") or now_iso()
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")
        f.flush()


def log_exception(where: str, exc: BaseException) -> None:
    tb = traceback.format_exc()
    log(
        {
            "event": "CRASH",
            "where": where,
            "error": repr(exc),
            "traceback": tb,
        }
    )

