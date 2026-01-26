# tests/unit/test_management_finder.py
"""
Tests para ManagementSignalFinder - encontrar señales sin reply_to.
"""
import pytest
from core.services.management_finder import ManagementSignalFinder
from core.state import BotState, SplitState
from core.domain.models import Signal
from core.domain.enums import OrderSide


class TestManagementSignalFinder:
    """Tests de búsqueda de señales para comandos de gestión."""
    
    def setup_method(self):
        """Setup antes de cada test."""
        self.state = BotState()
        self.finder = ManagementSignalFinder(self.state)
    
    def _create_signal_with_open_split(self, msg_id: int) -> None:
        """Helper para crear señal con split OPEN."""
        signal = Signal(
            message_id=msg_id,
            symbol="XAUUSD",
            side=OrderSide.BUY,
            entry=5090.0,
            tps=[5093.0],
            sl=5085.0
        )
        self.state.add_signal(signal)
        
        splits = self.state.build_splits_for_signal(msg_id)
        splits[0].status = "OPEN"
        splits[0].position_ticket = 10000 + msg_id
    
    def test_no_open_signals_returns_none(self):
        """Sin señales abiertas → retorna None."""
        target = self.finder.find_target_signal(management_msg_id=100)
        
        assert target is None
    
    def test_single_open_signal_found(self):
        """Reproducir msg_id 4629: una sola señal OPEN debe encontrarse."""
        # Crear una señal OPEN
        self._create_signal_with_open_split(msg_id=4628)
        
        # Buscar target
        target = self.finder.find_target_signal(management_msg_id=4629)
        
        assert target == 4628
    
    def test_multiple_open_signals_returns_most_recent(self):
        """Múltiples señales OPEN → retorna la más reciente."""
        # Crear 3 señales OPEN
        self._create_signal_with_open_split(msg_id=100)
        self._create_signal_with_open_split(msg_id=200)
        self._create_signal_with_open_split(msg_id=300)
        
        # Debe retornar 300 (más reciente)
        target = self.finder.find_target_signal(management_msg_id=400)
        
        assert target == 300
    
    def test_ignores_closed_signals(self):
        """Señales CLOSED deben ignorarse."""
        # Señal CLOSED
        signal1 = Signal(
            message_id=100,
            symbol="XAUUSD",
            side=OrderSide.BUY,
            entry=5090.0,
            tps=[5093.0],
            sl=5085.0
        )
        self.state.add_signal(signal1)
        splits1 = self.state.build_splits_for_signal(100)
        splits1[0].status = "CLOSED"
        
        # Señal OPEN
        self._create_signal_with_open_split(msg_id=200)
        
        # Debe retornar solo la OPEN
        target = self.finder.find_target_signal(management_msg_id=300)
        
        assert target == 200
    
    def test_pending_signals_also_found(self):
        """Señales PENDING también deben encontrarse."""
        signal = Signal(
            message_id=100,
            symbol="XAUUSD",
            side=OrderSide.BUY,
            entry=5090.0,
            tps=[5093.0],
            sl=5085.0
        )
        self.state.add_signal(signal)
        
        splits = self.state.build_splits_for_signal(100)
        splits[0].status = "PENDING"
        splits[0].order_ticket = 12345
        
        target = self.finder.find_target_signal(management_msg_id=200)
        
        assert target == 100
    
    def test_validate_target_with_active_splits(self):
        """Validar target con splits activos."""
        self._create_signal_with_open_split(msg_id=100)
        
        is_valid = self.finder.validate_target(target_msg_id=100)
        
        assert is_valid is True
    
    def test_validate_target_without_active_splits(self):
        """Validar target sin splits activos."""
        signal = Signal(
            message_id=100,
            symbol="XAUUSD",
            side=OrderSide.BUY,
            entry=5090.0,
            tps=[5093.0],
            sl=5085.0
        )
        self.state.add_signal(signal)
        
        splits = self.state.build_splits_for_signal(100)
        splits[0].status = "CLOSED"
        
        is_valid = self.finder.validate_target(target_msg_id=100)
        
        assert is_valid is False
    
    def test_get_signal_info_for_prompt(self):
        """Obtener info de señales activas."""
        # Crear 2 señales OPEN
        self._create_signal_with_open_split(msg_id=100)
        self._create_signal_with_open_split(msg_id=200)
        
        info = self.finder.get_signal_info_for_prompt()
        
        assert len(info) == 2
        assert info[0]["msg_id"] == 100
        assert info[1]["msg_id"] == 200
        assert info[0]["open_count"] == 1
    
    def test_should_prompt_user_single_signal(self):
        """Con 1 sola señal NO debe pedir prompt."""
        self._create_signal_with_open_split(msg_id=100)
        
        should_prompt = self.finder.should_prompt_user(management_msg_id=200)
        
        assert should_prompt is False
    
    def test_should_prompt_user_no_signals(self):
        """Sin señales NO debe pedir prompt."""
        should_prompt = self.finder.should_prompt_user(management_msg_id=100)
        
        assert should_prompt is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])