# tests/unit/test_message_classifier.py
"""
Tests para MessageClassifier - reducción de ruido en logs.
"""
import pytest
from core.services.message_classifier import MessageClassifier


class TestMessageClassifier:
    """Tests de clasificación de mensajes."""
    
    def setup_method(self):
        """Setup antes de cada test."""
        self.classifier = MessageClassifier()
    
    def test_valid_signal_classified_as_candidate(self):
        """Señal válida debe clasificarse como SIGNAL_CANDIDATE."""
        text = "XAUUSD BUY 5090\nTP 5093\nSL: 5085"
        
        category, reason = self.classifier.classify(text)
        
        assert category == "SIGNAL_CANDIDATE"
        assert "signal_indicators" in reason
    
    def test_sl_emoji_classified_as_non_signal(self):
        """Reproducir msg_id 4593: 'SL❌' debe ser NON_SIGNAL."""
        text = "SL❌"
        
        category, reason = self.classifier.classify(text)
        
        assert category == "NON_SIGNAL"
        assert "non_signal_pattern" in reason
    
    def test_tp_pips_classified_as_non_signal(self):
        """Reproducir msg_id 4595: 'TP, +40 PIPS✅' debe ser NON_SIGNAL."""
        text = "TP, +40 PIPS✅"
        
        category, reason = self.classifier.classify(text)
        
        assert category == "NON_SIGNAL"
        assert "non_signal_pattern" in reason
    
    def test_marketing_message_classified_as_non_signal(self):
        """Reproducir msg_id 4598: mensaje largo de marketing."""
        text = """👉🏻CHICOS, ESTAMOS TERMINANDO DE PREPARAR LOS ÚLTIMOS DETALLES, 
        PERO MUY PRONTO OS DAREMOS UNA NOTICIA TOP SOBRE EL PROYECTO QUE HEMOS PREPARADO."""
        
        category, reason = self.classifier.classify(text)
        
        assert category == "NON_SIGNAL"
        assert "non_signal_pattern" in reason
    
    def test_be_command_classified_as_management(self):
        """Comando BE debe clasificarse como MANAGEMENT."""
        text = "MOVER EL STOP LOSS A BE"
        
        category, reason = self.classifier.classify(text)
        
        assert category == "MANAGEMENT"
        assert "management_command" in reason
    
    def test_close_command_classified_as_management(self):
        """Reproducir msg_id 4629: 'CERRAR AHORA' debe ser MANAGEMENT."""
        text = "CERRAR AHORA A 5070, +30 PIPS✅"
        
        category, reason = self.classifier.classify(text)
        
        assert category == "MANAGEMENT"
        assert "management_command" in reason
    
    def test_should_parse_valid_signal(self):
        """Señal válida debe intentar parsearse."""
        text = "XAUUSD SELL 4948\nTP 4946\nTP 4944\nSL: 4958"
        
        should_parse, reason = self.classifier.should_attempt_parse(text)
        
        assert should_parse is True
        assert "SIGNAL_CANDIDATE" in reason
    
    def test_should_not_parse_tp_confirmation(self):
        """Confirmación de TP NO debe parsearse."""
        text = "Take profit 1 +30PIPS✅"
        
        should_parse, reason = self.classifier.should_attempt_parse(text)
        
        assert should_parse is False
        assert "NON_SIGNAL" in reason
    
    def test_should_not_parse_empty_text(self):
        """Texto vacío NO debe parsearse."""
        text = ""
        
        should_parse, reason = self.classifier.should_attempt_parse(text)
        
        assert should_parse is False
        assert "empty_text" in reason
    
    def test_incomplete_signal_still_candidate(self):
        """Señal incompleta con XAUUSD debe ser candidato."""
        text = "XAUUSD BUY (5083.5-5082.5)"
        
        category, reason = self.classifier.classify(text)
        
        # Tiene XAUUSD + BUY, debe ser candidato
        assert category == "SIGNAL_CANDIDATE"
    
    def test_cancelar_message_classified_as_non_signal(self):
        """Reproducir msg_id 4617: 'CANCELAR' debe ser NON_SIGNAL."""
        text = "CANCELAR, LA OPERACIÓN YA ESTABA A TP"
        
        category, reason = self.classifier.classify(text)
        
        assert category == "NON_SIGNAL"
        assert "non_signal_pattern" in reason
    
    def test_modificar_tp_classified_as_non_signal(self):
        """Reproducir msg_id 4620: 'Modificar el Take profit'."""
        text = "Modificar el Take profit"
        
        category, reason = self.classifier.classify(text)
        
        assert category == "NON_SIGNAL"
        assert "non_signal_pattern" in reason
    
    def test_classification_stats(self):
        """Test de estadísticas de clasificación."""
        messages = [
            "XAUUSD BUY 5090\nTP 5093\nSL: 5085",  # SIGNAL
            "SL❌",  # NON_SIGNAL
            "MOVER EL SL A BE",  # MANAGEMENT
            "TP +30 PIPS✅",  # NON_SIGNAL
            "XAUUSD SELL 5070",  # SIGNAL
        ]
        
        stats = self.classifier.get_classification_stats(messages)
        
        assert stats["total"] == 5
        assert stats["signal_candidates"] == 2
        assert stats["non_signals"] == 2
        assert stats["management"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])