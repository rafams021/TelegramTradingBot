# core/logger.py
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict

import config


def log(payload: Dict[str, Any]) -> None:
    # Ensure timestamp
    if "ts" not in payload:
        payload["ts"] = datetime.now(timezone.utc).isoformat()

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

