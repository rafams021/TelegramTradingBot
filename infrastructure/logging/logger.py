# infrastructure/logging/logger.py
import json
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class BotLogger:
    """
    Logger centralizado que escribe eventos en formato JSONL.
    Thread-safe y con manejo de errores robusto.
    """

    def __init__(self, log_path: str = "bot_events.jsonl"):
        self.log_path = log_path
        self._lock = threading.Lock()
        self._ensure_log_dir()

    def _ensure_log_dir(self) -> None:
        log_dir = os.path.dirname(os.path.abspath(self.log_path))
        if log_dir and not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir, exist_ok=True)
            except Exception:
                self.log_path = os.path.basename(self.log_path)

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _write_event(self, event: Dict[str, Any]) -> None:
        try:
            if "ts" not in event:
                event["ts"] = self._utc_now()
            line = json.dumps(event, ensure_ascii=False, default=str)
            with self._lock:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
        except Exception as e:
            import sys
            print(f"[LOGGER ERROR] {e}: {event}", file=sys.stderr)

    def event(self, event_type: str, **data: Any) -> None:
        e = {"event": event_type}
        e.update(data)
        self._write_event(e)

    def info(self, message: str, **context: Any) -> None:
        e = {"event": "INFO", "level": "INFO", "message": message}
        e.update(context)
        self._write_event(e)

    def warning(self, message: str, **context: Any) -> None:
        e = {"event": "WARNING", "level": "WARNING", "message": message}
        e.update(context)
        self._write_event(e)

    def error(self, message: str, exc_info: bool = False, **context: Any) -> None:
        e = {"event": "ERROR", "level": "ERROR", "message": message}
        if exc_info:
            import traceback
            e["traceback"] = traceback.format_exc()
        e.update(context)
        self._write_event(e)

    def debug(self, message: str, **context: Any) -> None:
        e = {"event": "DEBUG", "level": "DEBUG", "message": message}
        e.update(context)
        self._write_event(e)


_logger: Optional[BotLogger] = None


def get_logger(log_path: Optional[str] = None) -> BotLogger:
    global _logger
    if _logger is None:
        from config.constants import DEFAULT_EVENTS_PATH
        path = log_path or DEFAULT_EVENTS_PATH
        _logger = BotLogger(path)
    elif log_path is not None and _logger.log_path != log_path:
        _logger = BotLogger(log_path)
    return _logger


def set_logger(logger: BotLogger) -> None:
    global _logger
    _logger = logger


def event(event_type: str, **data: Any) -> None:
    get_logger().event(event_type, **data)


def info(message: str, **context: Any) -> None:
    get_logger().info(message, **context)


def warning(message: str, **context: Any) -> None:
    get_logger().warning(message, **context)


def error(message: str, exc_info: bool = False, **context: Any) -> None:
    get_logger().error(message, exc_info=exc_info, **context)


def debug(message: str, **context: Any) -> None:
    get_logger().debug(message, **context)