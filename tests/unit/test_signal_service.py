# tests/unit/test_signal_service.py
"""
Tests unitarios para SignalService.
"""
import pytest
from core.services import SignalService
from core.state import BotState


class TestSignalService:
    """Tests para SignalService."""
    
    def setup_method(self):
        """Setup antes de cada test."""
        self.state = BotState()
        self.service = SignalService(self.state)
    
    def test_process_signal_valid(self, sample_buy_text):
        """Debe procesar señal válida correctamente."""
        signal = self.service.process_signal(
            msg_id=100,
            text=sample_buy_text,
            is_edit=False,
        )
        
        assert signal is not None
        assert signal.message_id == 100
        assert signal.side.value == "BUY"
        assert signal.entry == 4910
    
    def test_process_signal_duplicate(self, sample_buy_text):
        """No debe procesar señal duplicada."""
        # Primera vez
        signal1 = self.service.process_signal(
            msg_id=100,
            text=sample_buy_text,
            is_edit=False,
        )
        
        # Segunda vez (duplicado)
        signal2 = self.service.process_signal(
            msg_id=100,
            text=sample_buy_text,
            is_edit=False,
        )
        
        assert signal1 is not None
        assert signal2 is None  # Duplicado
    
    def test_process_signal_edit_within_window(self, sample_buy_text):
        """Debe reprocesar edits dentro de ventana."""
        # Primera vez (falla de parseo)
        signal1 = self.service.process_signal(
            msg_id=100,
            text="Texto inválido",
            is_edit=False,
        )
        assert signal1 is None
        
        # Edit con texto correcto
        signal2 = self.service.process_signal(
            msg_id=100,
            text=sample_buy_text,
            is_edit=True,
        )
        assert signal2 is not None
    
    def test_create_splits(self, sample_buy_signal):
        """Debe crear splits correctamente."""
        self.state.add_signal(sample_buy_signal)
        
        splits = self.service.create_splits(sample_buy_signal.message_id)
        
        assert len(splits) == 3  # 3 TPs = 3 splits
        assert splits[0].tp == 4912
        assert splits[1].tp == 4915
        assert splits[2].tp == 4920
        assert all(s.sl == 4900 for s in splits)
    
    def test_should_skip_tp_buy_reached(self, sample_buy_signal):
        """Debe detectar cuando TP ya fue alcanzado (BUY)."""
        # TP1 = 4912, bid = 4913 => alcanzado
        should_skip = self.service.should_skip_tp(
            tp=4912,
            side=sample_buy_signal.side,
            bid=4913,
            ask=4914,
        )
        assert should_skip is True
    
    def test_should_skip_tp_buy_not_reached(self, sample_buy_signal):
        """No debe skipear si TP no alcanzado (BUY)."""
        # TP1 = 4912, bid = 4911 => NO alcanzado
        should_skip = self.service.should_skip_tp(
            tp=4912,
            side=sample_buy_signal.side,
            bid=4911,
            ask=4912,
        )
        assert should_skip is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])