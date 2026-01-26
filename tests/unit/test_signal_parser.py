# tests/unit/test_signal_parser.py
"""
Tests unitarios para SignalParser.
"""
import pytest
from core.parsers import SignalParser
from core.domain.enums import OrderSide
from tests.fixtures.sample_signals import (
    VALID_BUY_SIGNAL,
    VALID_SELL_SIGNAL,
    SIGNAL_WITH_RANGE,
    SIGNAL_ALTERNATE_FORMAT,
    INVALID_NO_TP,
    INVALID_NO_SL,
    INVALID_TP_DIRECTION,
    NOT_A_SIGNAL,
)


class TestSignalParser:
    """Tests para SignalParser."""
    
    def setup_method(self):
        """Setup antes de cada test."""
        self.parser = SignalParser()
    
    def test_parse_valid_buy_signal(self):
        """Debe parsear señal BUY válida."""
        signal = self.parser.parse(VALID_BUY_SIGNAL, msg_id=123)
        
        assert signal is not None
        assert signal.message_id == 123
        assert signal.symbol == "XAUUSD"
        assert signal.side == OrderSide.BUY
        assert signal.entry == 4910
        assert signal.sl == 4900
        assert len(signal.tps) == 3
        assert signal.tps == [4912, 4915, 4920]
    
    def test_parse_valid_sell_signal(self):
        """Debe parsear señal SELL válida."""
        signal = self.parser.parse(VALID_SELL_SIGNAL, msg_id=124)
        
        assert signal is not None
        assert signal.side == OrderSide.SELL
        assert signal.entry == 4880
        assert signal.sl == 4890
        assert signal.tps == [4875, 4870, 4865]
    
    def test_parse_signal_with_range(self):
        """Debe parsear señal con rango de entrada."""
        signal = self.parser.parse(SIGNAL_WITH_RANGE)
        
        assert signal is not None
        assert signal.side == OrderSide.BUY
        # Para BUY, debe elegir el precio más bajo del rango
        assert signal.entry == 4981.5
        assert signal.tps == [4985, 4990]
    
    def test_parse_alternate_format(self):
        """Debe parsear formatos alternativos."""
        signal = self.parser.parse(SIGNAL_ALTERNATE_FORMAT)
        
        assert signal is not None
        assert signal.side == OrderSide.SELL
        assert signal.entry == 4880
        assert signal.sl == 4887
        assert len(signal.tps) == 2
    
    def test_parse_invalid_no_tp(self):
        """Debe rechazar señal sin TP."""
        signal = self.parser.parse(INVALID_NO_TP)
        assert signal is None
    
    def test_parse_invalid_no_sl(self):
        """Debe rechazar señal sin SL."""
        signal = self.parser.parse(INVALID_NO_SL)
        assert signal is None
    
    def test_parse_invalid_tp_direction(self):
        """Debe rechazar señal con TPs en dirección incorrecta."""
        signal = self.parser.parse(INVALID_TP_DIRECTION)
        # El parser parsea, pero Signal.__post_init__ valida
        assert signal is None
    
    def test_parse_not_a_signal(self):
        """Debe rechazar texto que no es señal."""
        signal = self.parser.parse(NOT_A_SIGNAL)
        assert signal is None
    
    def test_parse_empty_text(self):
        """Debe manejar texto vacío."""
        signal = self.parser.parse("")
        assert signal is None
    
    def test_parse_none_text(self):
        """Debe manejar None."""
        signal = self.parser.parse(None)
        assert signal is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])