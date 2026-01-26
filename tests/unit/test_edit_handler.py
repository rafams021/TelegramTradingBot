# tests/unit/test_edit_handler.py
"""
Tests para EditHandler - prevención de duplicados.
"""
import pytest
from core.services.edit_handler import EditHandler
from core.state import BotState
from core.domain.models import Signal
from core.domain.enums import OrderSide


class TestEditHandler:
    """Tests de manejo de ediciones."""
    
    def setup_method(self):
        """Setup antes de cada test."""
        self.state = BotState()
        self.handler = EditHandler(self.state, edit_window_s=180)
    
    def test_first_time_message_processed(self):
        """Primera vez que vemos el mensaje → debe procesarse."""
        should_process, reason = self.handler.should_process_edit(
            msg_id=100,
            new_text="XAUUSD BUY 5090"
        )
        assert should_process is True
        assert reason == "first_time"
    
    def test_edit_within_window_processed(self):
        """Edit dentro de ventana → debe procesarse."""
        # Crear cache
        self.state.upsert_msg_cache(msg_id=100, text="original")
        
        should_process, reason = self.handler.should_process_edit(
            msg_id=100,
            new_text="edited"
        )
        assert should_process is True
        assert reason == "within_window"
    
    def test_edit_outside_window_ignored(self):
        """Edit fuera de ventana → debe ignorarse."""
        # Reproducir msg_id 4603 del log
        import time
        from datetime import datetime, timezone, timedelta
        
        # Crear cache con timestamp antiguo
        cache = self.state.upsert_msg_cache(msg_id=100, text="old")
        # Hackear timestamp para estar fuera de ventana
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=250)).isoformat()
        cache.first_seen_ts = old_time
        
        should_process, reason = self.handler.should_process_edit(
            msg_id=100,
            new_text="new"
        )
        assert should_process is False
        assert reason == "outside_window"
    
    def test_edit_with_active_splits_ignored(self):
        """Edit cuando ya hay splits activos → debe ignorarse."""
        # Reproducir msg_id 4594 del log
        # 1. Crear señal con splits PENDING
        signal = Signal(
            message_id=100,
            symbol="XAUUSD",
            side=OrderSide.BUY,
            entry=4979.0,
            tps=[4983.0],
            sl=4960.0
        )
        self.state.add_signal(signal)

        # 2. Crear cache del mensaje (IMPORTANTE: antes de crear splits)
        self.state.upsert_msg_cache(msg_id=100, text="original text")

        # 3. Crear splits PENDING
        splits = self.state.build_splits_for_signal(100)
        
        # Verificar que splits se crearon
        assert len(splits) > 0, "No se crearon splits"
        
        splits[0].status = "PENDING"
        splits[0].order_ticket = 154575709

        # 4. Intentar procesar edit
        should_process, reason = self.handler.should_process_edit(
            msg_id=100,
            new_text="edited text",
            signal=signal
        )

        assert should_process is False
        assert reason == "splits_already_active"
    
    def test_significant_change_extends_window(self):
        """Cambio significativo debe procesarse aunque fuera de ventana."""
        # Reproducir msg_id 4601: typo 4091 → 5091
        import time
        from datetime import datetime, timezone, timedelta
        
        # Crear señal original con typo
        original_signal = Signal(
            message_id=100,
            symbol="XAUUSD",
            side=OrderSide.BUY,
            entry=4091.0,  # Typo
            tps=[4094.0],
            sl=4070.0
        )
        self.state.add_signal(original_signal)
        
        # Crear cache fuera de ventana
        cache = self.state.upsert_msg_cache(msg_id=100, text="old")
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=900)).isoformat()
        cache.first_seen_ts = old_time
        
        # Nueva señal con corrección
        corrected_signal = Signal(
            message_id=100,
            symbol="XAUUSD",
            side=OrderSide.BUY,
            entry=5091.0,  # Corregido
            tps=[5094.0],
            sl=5070.0
        )
        
        # Debe procesarse por cambio significativo
        should_process, reason = self.handler.should_process_edit(
            msg_id=100,
            new_text="corrected",
            signal=corrected_signal
        )
        
        assert should_process is True
        assert reason == "significant_change_despite_window"
    
    def test_get_new_splits_only_filters_correctly(self):
        """get_new_splits_only debe retornar solo splits NEW."""
        signal = Signal(
            message_id=100,
            symbol="XAUUSD",
            side=OrderSide.BUY,
            entry=5090.0,
            tps=[5093.0, 5095.0],
            sl=5080.0
        )
        self.state.add_signal(signal)
        
        splits = self.state.build_splits_for_signal(100)
        
        # Marcar primer split como PENDING
        splits[0].status = "PENDING"
        # Segundo split sigue NEW
        splits[1].status = "NEW"
        
        new_only = self.handler.get_new_splits_only(100)
        
        assert len(new_only) == 1
        assert new_only[0].split_index == 1
    
    def test_has_significant_change_entry_5_percent(self):
        """Cambio >5% en entry es significativo."""
        original = Signal(
            message_id=100,
            symbol="XAUUSD",
            side=OrderSide.BUY,
            entry=5000.0,
            tps=[5010.0],
            sl=4990.0
        )
        self.state.add_signal(original)
        
        # Nuevo con entry +6%
        new = Signal(
            message_id=100,
            symbol="XAUUSD",
            side=OrderSide.BUY,
            entry=5300.0,  # +6%
            tps=[5310.0],
            sl=5290.0
        )
        
        has_change = self.handler._has_significant_change(100, new)
        assert has_change is True
    
    def test_has_significant_change_tp_count(self):
        """Cambio en número de TPs es significativo."""
        original = Signal(
            message_id=100,
            symbol="XAUUSD",
            side=OrderSide.BUY,
            entry=5000.0,
            tps=[5010.0],
            sl=4990.0
        )
        self.state.add_signal(original)
        
        # Nuevo con 2 TPs
        new = Signal(
            message_id=100,
            symbol="XAUUSD",
            side=OrderSide.BUY,
            entry=5000.0,
            tps=[5010.0, 5015.0],  # Añadió TP
            sl=4990.0
        )
        
        has_change = self.handler._has_significant_change(100, new)
        assert has_change is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])