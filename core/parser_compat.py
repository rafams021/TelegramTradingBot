# core/parser.py
"""
DEPRECADO: Este archivo redirige al nuevo parser en core/parsers/.

Los archivos antiguos que usan:
    from core.parser import parse_signal

Siguen funcionando gracias a esta redirección.

NUEVO CÓDIGO DEBERÍA USAR:
    from core.parsers import SignalParser, parse_signal
"""

# Importar todo desde el nuevo location
from core.parsers.signal_parser import (
    SignalParser,
    parse_signal,
)

__all__ = [
    "SignalParser",
    "parse_signal",
]