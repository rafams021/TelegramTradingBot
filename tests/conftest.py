# tests/conftest.py
"""
Configuración de pytest y fixtures compartidos.
"""
import pytest
from datetime import datetime, timezone

from core.state import BotState
from core.domain.models import Signal
from core.domain.enums import OrderSide


@pytest.fixture
def bot_state():
    """Estado limpio del bot para cada test."""
    return BotState()


@pytest.fixture
def sample_buy_signal():
    """Señal BUY de ejemplo."""
    return Signal(
        message_id=12345,
        symbol="XAUUSD",
        side=OrderSide.BUY,
        entry=4910.0,
        tps=[4912.0, 4915.0, 4920.0],
        sl=4900.0,
    )


@pytest.fixture
def sample_sell_signal():
    """Señal SELL de ejemplo."""
    return Signal(
        message_id=12346,
        symbol="XAUUSD",
        side=OrderSide.SELL,
        entry=4880.0,
        tps=[4875.0, 4870.0, 4865.0],
        sl=4890.0,
    )


@pytest.fixture
def sample_buy_text():
    """Texto de señal BUY para parsear."""
    return """
    XAUUSD BUY @ 4910
    TP1: 4912
    TP2: 4915
    TP3: 4920
    SL: 4900
    """


@pytest.fixture
def sample_sell_text():
    """Texto de señal SELL para parsear."""
    return """
    XAUUSD SELL @ 4880
    TP1: 4875
    TP2: 4870
    SL: 4890
    """


@pytest.fixture
def utc_now():
    """Timestamp UTC actual."""
    return datetime.now(timezone.utc)