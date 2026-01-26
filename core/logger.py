# core/logger.py
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from typing import Any, Optional

# Archivo por defecto (puedes cambiarlo con env var si quieres)
DEFAULT_EVENTS_PATH = os.environ.get("BOT_EVENTS_PATH", "bot_events.jsonl")

_lock = threading.Lock()


def _utc_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir(path: str) -> None:
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


def log_event(event: dict, path: str = DEFAULT_EVENTS_PATH) -> None:
    """
    Escribe un evento JSONL (una línea por evento).
    Mantiene compatibilidad con el resto del proyecto.
    """
    try:
        _ensure_dir(path)
        payload = dict(event or {})
        payload.setdefault("ts", _utc_ts())

        line = json.dumps(payload, ensure_ascii=False)
        with _lock:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception:
        # Evita romper el bot por fallas de logging
        pass


def log(message: str, **fields: Any) -> None:
    """
    Helper simple: logea un evento tipo LOG.
    """
    ev = {"event": "LOG", "message": str(message)}
    if fields:
        ev.update(fields)
    log_event(ev)


# ✅ Compatibilidad: algunos módulos hacen `from core.logger import logger`
# Si ya usabas `logger` en algún lado, lo mantenemos.
def logger(message: str, **fields: Any) -> None:
    log(message, **fields)


# ✅ Compatibilidad clave: algunos módulos hacen `from core.logger import Logger`
class Logger:
    """
    Wrapper para no romper imports antiguos:
      - Logger.log(...)
      - Logger.event({...})
    """

    @staticmethod
    def log(message: str, **fields: Any) -> None:
        log(message, **fields)

    @staticmethod
    def event(event: dict, path: str = DEFAULT_EVENTS_PATH) -> None:
        log_event(event, path=path)

    @staticmethod
    def info(message: str, **fields: Any) -> None:
        log(message, level="INFO", **fields)

    @staticmethod
    def warning(message: str, **fields: Any) -> None:
        log(message, level="WARNING", **fields)

    @staticmethod
    def error(message: str, **fields: Any) -> None:
        log(message, level="ERROR", **fields)

