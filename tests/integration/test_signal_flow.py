# tests/integration/test_signal_flow.py
"""
Tests de integración para el flujo completo de procesamiento de señales.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch

from core.state import BotState
from core.services import SignalService
from core.parsers import SignalParser, ManagementParser
from core.domain.enums import OrderSide, OrderStatus


class TestSignalFlow:
    """Tests del flujo completo: Telegram → Parser → Service → State."""
    
    def setup_method(self):
        """Setup antes de cada test."""
        self.state = BotState()
        self.signal_service = SignalService(self.state)
        self.signal_parser = SignalParser()
    
    def test_full_signal_flow_buy(self):
        """
        Test del flujo completo de una señal BUY:
        1. Texto → Parser
        2. Parser → Signal
        3. Signal → Service
        4. Service → State
        5. State → Splits
        """
        # 1. Texto de entrada
        text = """
        XAUUSD BUY @ 4910
        TP1: 4912
        TP2: 4915
        TP3: 4920
        SL: 4900
        """
        msg_id = 100
        
        # 2. Parsear señal
        signal = self.signal_parser.parse(text, msg_id)
        
        assert signal is not None
        assert signal.message_id == msg_id
        assert signal.side == OrderSide.BUY
        assert signal.entry == 4910
        assert len(signal.tps) == 3
        
        # 3. Procesar con service
        self.state.add_signal(signal)
        
        # 4. Verificar en state
        assert self.state.has_signal(msg_id)
        sig_state = self.state.get_signal(msg_id)
        assert sig_state is not None
        assert sig_state.signal.message_id == msg_id
        
        # 5. Crear splits
        splits = self.signal_service.create_splits(msg_id)
        
        assert len(splits) == 3
        assert splits[0].tp == 4912
        assert splits[1].tp == 4915
        assert splits[2].tp == 4920
        assert all(s.sl == 4900 for s in splits)
        assert all(s.entry == 4910 for s in splits)
        assert all(s.status == "NEW" for s in splits)
    
    def test_full_signal_flow_sell(self):
        """Test del flujo completo de una señal SELL."""
        text = """
        XAUUSD SELL @ 4880
        TP1: 4875
        TP2: 4870
        SL: 4890
        """
        msg_id = 200
        
        # Parse
        signal = self.signal_parser.parse(text, msg_id)
        assert signal is not None
        assert signal.side == OrderSide.SELL
        
        # Add to state
        self.state.add_signal(signal)
        
        # Create splits
        splits = self.signal_service.create_splits(msg_id)
        
        assert len(splits) == 2
        assert splits[0].tp == 4875
        assert splits[1].tp == 4870
    
    def test_signal_with_edit(self):
        """
        Test de flujo con edición:
        1. Mensaje inicial (parse falla)
        2. Edit con texto correcto
        3. Signal procesada correctamente
        """
        msg_id = 300
        
        # 1. Primer intento (texto incorrecto)
        signal1 = self.signal_service.process_signal(
            msg_id=msg_id,
            text="Texto inválido sin señal",
            is_edit=False
        )
        assert signal1 is None
        
        # 2. Edit con texto correcto
        text_correcto = """
        XAUUSD BUY @ 4910
        TP1: 4912
        SL: 4900
        """
        
        signal2 = self.signal_service.process_signal(
            msg_id=msg_id,
            text=text_correcto,
            is_edit=True
        )
        
        assert signal2 is not None
        assert signal2.message_id == msg_id
        
        # 3. Verificar en state
        assert self.state.has_signal(msg_id)
    
    def test_duplicate_signal_rejected(self):
        """Test que duplicados son rechazados."""
        text = """
        XAUUSD BUY @ 4910
        TP1: 4912
        SL: 4900
        """
        msg_id = 400
        
        # Primera vez
        signal1 = self.signal_service.process_signal(
            msg_id=msg_id,
            text=text,
            is_edit=False
        )
        assert signal1 is not None
        
        # Segunda vez (duplicado)
        signal2 = self.signal_service.process_signal(
            msg_id=msg_id,
            text=text,
            is_edit=False
        )
        assert signal2 is None  # Rechazado
    
    def test_management_command_flow(self):
        """
        Test del flujo de comando de gestión:
        1. Crear señal original
        2. Parsear comando BE
        3. Aplicar a splits
        """
        # 1. Señal original
        text = """
        XAUUSD BUY @ 4910
        TP1: 4912
        SL: 4900
        """
        msg_id = 500
        
        signal = self.signal_service.process_signal(
            msg_id=msg_id,
            text=text,
            is_edit=False
        )
        
        splits = self.signal_service.create_splits(msg_id)
        
        # Simular que están OPEN
        for split in splits:
            split.status = "OPEN"
        
        # 2. Comando de gestión
        mgmt_parser = ManagementParser()
        action = mgmt_parser.parse("BE")
        
        assert action.type.value == "BE"
        
        # 3. Aplicar (simular)
        from core.services import ManagementService
        mgmt_service = ManagementService(self.state)
        
        result = mgmt_service.apply(
            action=action,
            msg_id=600,
            reply_to=msg_id
        )
        
        assert result is True
        
        # Verificar que BE está armado
        sig_state = self.state.get_signal(msg_id)
        for split in sig_state.splits:
            if split.status == "OPEN":
                assert split.be_armed is True
    
    def test_skip_tp_already_reached(self):
        """Test que splits se skipean si TP ya alcanzado."""
        text = """
        XAUUSD BUY @ 4910
        TP1: 4912
        SL: 4900
        """
        msg_id = 700
        
        signal = self.signal_service.process_signal(
            msg_id=msg_id,
            text=text,
            is_edit=False
        )
        
        splits = self.signal_service.create_splits(msg_id)
        
        # Simular que TP1 ya fue alcanzado
        should_skip = self.signal_service.should_skip_tp(
            tp=4912,
            side=signal.side,
            bid=4913,  # bid > TP para BUY
            ask=4914
        )
        
        assert should_skip is True
    
    def test_multiple_signals_in_state(self):
        """Test de múltiples señales en state simultáneamente."""
        # Señal 1
        signal1 = self.signal_service.process_signal(
            msg_id=801,
            text="XAUUSD BUY @ 4910\nTP1: 4912\nSL: 4900",
            is_edit=False
        )
        
        # Señal 2
        signal2 = self.signal_service.process_signal(
            msg_id=802,
            text="XAUUSD SELL @ 4880\nTP1: 4875\nSL: 4890",
            is_edit=False
        )
        
        assert signal1 is not None
        assert signal2 is not None
        
        # Verificar ambas en state
        assert self.state.has_signal(801)
        assert self.state.has_signal(802)
        
        # Verificar que son diferentes
        assert signal1.side == OrderSide.BUY
        assert signal2.side == OrderSide.SELL


class TestIntegrationWithMocks:
    """Tests de integración con mocks de MT5."""
    
    def setup_method(self):
        """Setup con mocks."""
        self.state = BotState()
        self.signal_service = SignalService(self.state)
    
    @patch('adapters.mt5_client.symbol_tick')
    @patch('adapters.mt5_client.open_market')
    def test_market_execution_flow(self, mock_open_market, mock_tick):
        """Test de ejecución a mercado (con mocks)."""
        # Mock tick
        mock_tick.return_value = MagicMock(bid=4910.2, ask=4910.3)
        
        # Mock resultado exitoso
        mock_result = MagicMock()
        mock_result.retcode = 10009
        mock_result.order = 12345
        mock_open_market.return_value = ({}, mock_result)
        
        # Procesar señal
        signal = self.signal_service.process_signal(
            msg_id=900,
            text="XAUUSD BUY @ 4910\nTP1: 4912\nSL: 4900",
            is_edit=False
        )
        
        assert signal is not None
        
        # En un flujo real, executor llamaría a MT5
        # Aquí solo verificamos que el mock funcionaría
        splits = self.signal_service.create_splits(900)
        
        assert len(splits) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])