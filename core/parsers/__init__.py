# core/parsers/__init__.py
"""
Parsers del bot - Extracción de datos de texto.

Parsers:
    - SignalParser: Parsea señales de trading de Telegram
    - ManagementParser: Parsea comandos de gestión (BE, CLOSE, MOVE_SL)
"""

from .signal_parser import SignalParser, parse_signal
from .management_parser import ManagementParser, ManagementAction

__all__ = [
    "SignalParser",
    "parse_signal",
    "ManagementParser",
    "ManagementAction",
]