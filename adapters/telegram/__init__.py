# adapters/telegram/__init__.py
"""
Cliente Telegram refactorizado.

Exports:
    - TelegramBotClient: Wrapper del cliente de Telegram
"""

from .client import TelegramBotClient

__all__ = [
    "TelegramBotClient",
]