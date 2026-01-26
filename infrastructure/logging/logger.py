# infrastructure/logging/logger.py
"""
Logger unificado para el TelegramTradingBot.
Simplifica y centraliza todo el logging en JSONL.
"""
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
        """Crea el directorio de logs si no existe."""
        log_dir = os.path.dirname(os.path.abspath(self.log_path))
        if log_dir and not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir, exist_ok=True)
            except Exception:
                # Si falla, usar directorio actual
                self.log_path = os.path.basename(self.log_path)
    
    @staticmethod
    def _utc_now() -> str:
        """Retorna timestamp UTC en formato ISO."""
        return datetime.now(timezone.utc).isoformat()
    
    def _write_event(self, event: Dict[str, Any]) -> None:
        """Escribe un evento en el archivo JSONL."""
        try:
            # Asegurar que tenga timestamp
            if "ts" not in event:
                event["ts"] = self._utc_now()
            
            line = json.dumps(event, ensure_ascii=False, default=str)
            
            with self._lock:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
        except Exception as e:
            # Fallback: imprimir a stderr sin romper la app
            import sys
            print(f"[LOGGER ERROR] {e}: {event}", file=sys.stderr)
    
    def event(self, event_type: str, **data: Any) -> None:
        """
        Registra un evento estructurado.
        
        Args:
            event_type: Tipo de evento (ej: "SIGNAL_PARSED", "ORDER_SENT")
            **data: Datos adicionales del evento
        
        Example:
            logger.event("SIGNAL_PARSED", msg_id=123, side="BUY", entry=4910.5)
        """
        event = {"event": event_type}
        event.update(data)
        self._write_event(event)
    
    def info(self, message: str, **context: Any) -> None:
        """
        Log de información.
        
        Args:
            message: Mensaje descriptivo
            **context: Contexto adicional
        """
        event = {
            "event": "INFO",
            "level": "INFO",
            "message": message,
        }
        event.update(context)
        self._write_event(event)
    
    def warning(self, message: str, **context: Any) -> None:
        """
        Log de advertencia.
        
        Args:
            message: Mensaje descriptivo
            **context: Contexto adicional
        """
        event = {
            "event": "WARNING",
            "level": "WARNING",
            "message": message,
        }
        event.update(context)
        self._write_event(event)
    
    def error(self, message: str, exc_info: bool = False, **context: Any) -> None:
        """
        Log de error.
        
        Args:
            message: Mensaje descriptivo
            exc_info: Si True, incluye traceback de la excepción actual
            **context: Contexto adicional
        """
        event = {
            "event": "ERROR",
            "level": "ERROR",
            "message": message,
        }
        
        if exc_info:
            import traceback
            event["traceback"] = traceback.format_exc()
        
        event.update(context)
        self._write_event(event)
    
    def debug(self, message: str, **context: Any) -> None:
        """
        Log de debug (solo en modo verbose).
        
        Args:
            message: Mensaje descriptivo
            **context: Contexto adicional
        """
        # Por ahora siempre logea, pero se puede agregar flag de DEBUG
        event = {
            "event": "DEBUG",
            "level": "DEBUG",
            "message": message,
        }
        event.update(context)
        self._write_event(event)


# =========================
# Global logger instance
# =========================

_logger: Optional[BotLogger] = None


def get_logger(log_path: Optional[str] = None) -> BotLogger:
    """
    Obtiene o crea la instancia global del logger.
    
    Args:
        log_path: Path del archivo de log. Si es None, usa el existente o default.
    
    Returns:
        BotLogger instance
    """
    global _logger
    
    if _logger is None:
        from config.constants import DEFAULT_EVENTS_PATH
        path = log_path or DEFAULT_EVENTS_PATH
        _logger = BotLogger(path)
    elif log_path is not None and _logger.log_path != log_path:
        # Si se pide un path diferente, crear nueva instancia
        _logger = BotLogger(log_path)
    
    return _logger


def set_logger(logger: BotLogger) -> None:
    """Establece una instancia custom del logger."""
    global _logger
    _logger = logger


# =========================
# Convenience functions
# =========================

def event(event_type: str, **data: Any) -> None:
    """Shortcut para get_logger().event()"""
    get_logger().event(event_type, **data)


def info(message: str, **context: Any) -> None:
    """Shortcut para get_logger().info()"""
    get_logger().info(message, **context)


def warning(message: str, **context: Any) -> None:
    """Shortcut para get_logger().warning()"""
    get_logger().warning(message, **context)


def error(message: str, exc_info: bool = False, **context: Any) -> None:
    """Shortcut para get_logger().error()"""
    get_logger().error(message, exc_info=exc_info, **context)


def debug(message: str, **context: Any) -> None:
    """Shortcut para get_logger().debug()"""
    get_logger().debug(message, **context)


# =========================
# Backward compatibility
# =========================

def log_event(event_dict: Dict[str, Any]) -> None:
    """
    Backward compatibility con código antiguo que usa log_event(dict).
    
    Args:
        event_dict: Diccionario con el evento, debe tener key "event"
    """
    logger = get_logger()
    event_type = event_dict.pop("event", "UNKNOWN")
    logger.event(event_type, **event_dict)


def iso_now() -> str:
    """Backward compatibility para obtener timestamp ISO."""
    return datetime.now(timezone.utc).isoformat()


# Clase de compatibilidad para código que hace `from core.logger import Logger`
class Logger:
    """Clase de compatibilidad para imports antiguos."""
    
    @staticmethod
    def log(message: str, **fields: Any) -> None:
        info(message, **fields)
    
    @staticmethod
    def event(event_dict: Dict[str, Any]) -> None:
        log_event(event_dict)
    
    @staticmethod
    def info(message: str, **fields: Any) -> None:
        info(message, **fields)
    
    @staticmethod
    def warning(message: str, **fields: Any) -> None:
        warning(message, **fields)
    
    @staticmethod
    def error(message: str, **fields: Any) -> None:
        error(message, exc_info=True, **fields)