# core/logger.py
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict

import config


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(payload: Dict[str, Any]) -> None:
    # Ensure timestamp
    if "ts" not in payload:
        payload["ts"] = iso_now()

    line = json.dumps(payload, ensure_ascii=False)

    # stdout (console)
    print(line, flush=True)

    # file (project root)
    try:
        root = os.path.dirname(os.path.dirname(__file__))
        path = os.path.join(root, config.LOG_FILE)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        # never crash due to logging
        pass


def log_event(payload: Dict[str, Any]) -> None:
    # Backward-compatible alias. No new logic here.
    log(payload)