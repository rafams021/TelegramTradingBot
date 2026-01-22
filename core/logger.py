# core/logger.py
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict

import config


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_print(line: str) -> None:
    """
    Windows console can be cp1252 and crash on emojis/special chars.
    Never let logging crash the bot.
    """
    try:
        print(line, flush=True)
        return
    except UnicodeEncodeError:
        # Fallback: write bytes with replacement
        try:
            enc = (sys.stdout.encoding or "utf-8")
            data = (line + "\n").encode(enc, errors="backslashreplace")
            sys.stdout.buffer.write(data)
            sys.stdout.flush()
        except Exception:
            # last resort: ignore stdout completely
            pass
    except Exception:
        pass


def log(payload: Dict[str, Any]) -> None:
    # Ensure timestamp
    if "ts" not in payload:
        payload["ts"] = iso_now()

    line = json.dumps(payload, ensure_ascii=False)

    # stdout (never crash)
    _safe_print(line)

    # file (project root) - UTF-8, safe
    try:
        root = os.path.dirname(os.path.dirname(__file__))
        path = os.path.join(root, config.LOG_FILE)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        # never crash due to logging
        pass


def log_event(payload: Dict[str, Any]) -> None:
    # Backward-compatible alias
    log(payload)
