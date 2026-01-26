# tests/unit/test_management_service.py
"""
Tests unitarios para ManagementService.
"""
import pytest
from core.services import ManagementService
from core.state import BotState, SplitState
from core.parsers import ManagementParser
from core.domain.enums import ManagementType


class TestManagementService:
    """Tests para ManagementService."""
    
    def setup_method(self):
        """Setup antes de cada test."""
        self.state = BotState()
        self.service = ManagementService(self.state)
        self.parser = ManagementParser()
    
    def _create_test_signal_with_splits(self, msg_id: int, num_splits: int = 3):
        """Helper para crear señal con splits OPEN."""
        from core.domain.models import Signal
        from core.domain.enums import OrderSide
        
        signal = Signal(
            message_id=msg_id,
            symbol="XAUUSD",
            side=OrderSide.BUY,
            entry=4910.0,
            tps=[4912.0, 4915.0, 4920.0],
            sl=4900.0
        )
        
        self.state.add_signal(signal)
        
        # Crear splits manualmente
        sig_state = self.state.get_signal(msg_id)
        for i in range(num_splits):
            split = SplitState(
                split_index=i,
                side="BUY",
                entry=4910.0,
                sl=4900.0,
                tp=signal.tps[i]
            )
            split.status = "OPEN"
            split.position_ticket = 10000 + i
            sig_state.splits.append(split)
        
        return signal
    
    def test_apply_be_success(self):
        """Debe armar break even en posiciones OPEN."""
        # Setup
        signal = self._create_test_signal_with_splits(msg_id=100, num_splits=3)
        
        # Parse comando BE
        action = self.parser.parse("BE")
        
        # Apply
        result = self.service.apply(action, msg_id=200, reply_to=100)
        
        # Verificar
        assert result is True
        
        sig_state = self.state.get_signal(100)
        for split in sig_state.splits:
            assert split.be_armed is True
            assert split.be_done is False
    
    def test_apply_be_no_reply_to(self):
        """Debe fallar si no hay reply_to."""
        action = self.parser.parse("BE")
        
        result = self.service.apply(action, msg_id=200, reply_to=None)
        
        assert result is False
    
    def test_apply_be_signal_not_found(self):
        """Debe fallar si señal no existe."""
        action = self.parser.parse("BE")
        
        result = self.service.apply(action, msg_id=200, reply_to=999)
        
        assert result is False
    
    def test_apply_move_sl_success(self):
        """Debe armar movimiento de SL."""
        # Setup
        signal = self._create_test_signal_with_splits(msg_id=100, num_splits=2)
        
        # Parse comando
        action = self.parser.parse("MOVER EL SL A 4905")
        
        # Apply
        result = self.service.apply(action, msg_id=200, reply_to=100)
        
        # Verificar
        assert result is True
        
        sig_state = self.state.get_signal(100)
        for split in sig_state.splits:
            assert split.sl == 4905.0
            assert split.sl_move_armed is True
            assert split.sl_move_done is False
    
    def test_apply_move_sl_no_price(self):
        """Debe fallar si no hay precio."""
        signal = self._create_test_signal_with_splits(msg_id=100)
        
        # Acción sin precio
        from core.parsers.management_parser import ManagementAction
        action = ManagementAction(type=ManagementType.MOVE_SL, price=None)
        
        result = self.service.apply(action, msg_id=200, reply_to=100)
        
        assert result is False
    
    def test_apply_close_tp_success(self):
        """Debe armar cierre en TP específico."""
        # Setup
        signal = self._create_test_signal_with_splits(msg_id=100, num_splits=3)
        
        # Parse comando
        action = self.parser.parse("CERRAR TP1")
        
        # Apply
        result = self.service.apply(action, msg_id=200, reply_to=100)
        
        # Verificar
        assert result is True
        
        sig_state = self.state.get_signal(100)
        for split in sig_state.splits:
            assert split.close_armed is True
            assert split.close_done is False
            assert split.close_target == 4912.0  # TP1
    
    def test_apply_close_tp_invalid_index(self):
        """Debe fallar con índice inválido."""
        signal = self._create_test_signal_with_splits(msg_id=100)
        
        # Acción con índice 0 (inválido)
        from core.parsers.management_parser import ManagementAction
        action = ManagementAction(type=ManagementType.CLOSE_TP_AT, tp_index=0)
        
        result = self.service.apply(action, msg_id=200, reply_to=100)
        
        assert result is False
    
    def test_apply_close_tp_out_of_range(self):
        """Debe manejar índice fuera de rango."""
        signal = self._create_test_signal_with_splits(msg_id=100, num_splits=2)
        
        # Parse comando TP5 (no existe)
        action = self.parser.parse("CERRAR TP5")
        
        # Apply (no debería fallar, pero close_target será None)
        result = self.service.apply(action, msg_id=200, reply_to=100)
        
        assert result is True
        sig_state = self.state.get_signal(100)
        for split in sig_state.splits:
            assert split.close_armed is True
            # close_target puede ser None porque TP5 no existe
    
    def test_apply_close_all_success(self):
        """Debe armar cierre de todas las posiciones."""
        # Setup
        signal = self._create_test_signal_with_splits(msg_id=100, num_splits=3)
        
        # Parse comando
        action = self.parser.parse("CERRAR TODO")
        
        # Apply
        result = self.service.apply(action, msg_id=200, reply_to=100)
        
        # Verificar
        assert result is True
        
        sig_state = self.state.get_signal(100)
        for split in sig_state.splits:
            assert split.close_armed is True
            assert split.close_done is False
            assert split.close_target is None  # None = cerrar inmediatamente
    
    def test_apply_only_affects_open_positions(self):
        """Debe solo afectar posiciones OPEN."""
        # Setup
        signal = self._create_test_signal_with_splits(msg_id=100, num_splits=3)
        
        # Marcar una como CLOSED
        sig_state = self.state.get_signal(100)
        sig_state.splits[1].status = "CLOSED"
        
        # Parse y apply BE
        action = self.parser.parse("BE")
        result = self.service.apply(action, msg_id=200, reply_to=100)
        
        # Verificar
        assert result is True
        
        # Split 0 y 2 (OPEN) deben tener BE armado
        assert sig_state.splits[0].be_armed is True
        assert sig_state.splits[2].be_armed is True
        
        # Split 1 (CLOSED) NO debe tener BE armado
        assert sig_state.splits[1].be_armed is False
    
    def test_multiple_management_commands(self):
        """Debe permitir múltiples comandos de gestión."""
        # Setup
        signal = self._create_test_signal_with_splits(msg_id=100, num_splits=2)
        
        # Comando 1: BE
        action_be = self.parser.parse("BE")
        result1 = self.service.apply(action_be, msg_id=201, reply_to=100)
        assert result1 is True
        
        # Comando 2: MOVE_SL
        action_move = self.parser.parse("MOVER EL SL A 4905")
        result2 = self.service.apply(action_move, msg_id=202, reply_to=100)
        assert result2 is True
        
        # Comando 3: CLOSE
        action_close = self.parser.parse("CERRAR TODO")
        result3 = self.service.apply(action_close, msg_id=203, reply_to=100)
        assert result3 is True
        
        # Verificar que todos los flags están armados
        sig_state = self.state.get_signal(100)
        for split in sig_state.splits:
            assert split.be_armed is True
            assert split.sl_move_armed is True
            assert split.close_armed is True
            assert split.sl == 4905.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])