# tests/unit/test_management_parser.py
"""
Tests unitarios para ManagementParser.
"""
import pytest
from core.parsers import ManagementParser
from core.domain.enums import ManagementType
from tests.fixtures.sample_signals import (
    MANAGEMENT_BE,
    MANAGEMENT_MOVE_SL,
    MANAGEMENT_CLOSE_TP1,
    MANAGEMENT_CLOSE_ALL,
)


class TestManagementParser:
    """Tests para ManagementParser."""
    
    def setup_method(self):
        """Setup antes de cada test."""
        self.parser = ManagementParser()
    
    def test_parse_be_command(self):
        """Debe parsear comando BE."""
        action = self.parser.parse(MANAGEMENT_BE)
        
        assert action.type == ManagementType.BE
        assert action.price is None
        assert action.tp_index is None
    
    def test_parse_move_sl_command(self):
        """Debe parsear comando MOVE_SL."""
        action = self.parser.parse(MANAGEMENT_MOVE_SL)
        
        assert action.type == ManagementType.MOVE_SL
        assert action.price == 4905
        assert action.tp_index is None
    
    def test_parse_close_tp_command(self):
        """Debe parsear comando CLOSE_TP."""
        action = self.parser.parse(MANAGEMENT_CLOSE_TP1)
        
        assert action.type == ManagementType.CLOSE_TP_AT
        assert action.tp_index == 1
        assert action.price is None
    
    def test_parse_close_all_command(self):
        """Debe parsear comando CLOSE_ALL."""
        action = self.parser.parse(MANAGEMENT_CLOSE_ALL)
        
        assert action.type == ManagementType.CLOSE_ALL_AT
        assert action.price is None
        assert action.tp_index is None
    
    def test_parse_be_variations(self):
        """Debe parsear variaciones de BE."""
        variations = [
            "BE",
            "MOVER EL STOP LOSS A BE",
            "CERRAR A BE",
        ]
        
        for text in variations:
            action = self.parser.parse(text)
            assert action.type == ManagementType.BE, f"Failed for: {text}"
    
    def test_parse_move_sl_variations(self):
        """Debe parsear variaciones de MOVE_SL."""
        variations = [
            "MOVER EL SL A 4905",
            "MOVER EL STOP LOSS A 4905.5",
        ]
        
        for text in variations:
            action = self.parser.parse(text)
            assert action.type == ManagementType.MOVE_SL, f"Failed for: {text}"
            assert action.price is not None
    
    def test_parse_not_management(self):
        """Debe retornar NONE para texto no relacionado."""
        action = self.parser.parse("Hola, ¿cómo estás?")
        assert action.type == ManagementType.NONE
    
    def test_parse_empty_text(self):
        """Debe manejar texto vacío."""
        action = self.parser.parse("")
        assert action.type == ManagementType.NONE
    
    def test_is_management_command(self):
        """Debe identificar comandos de gestión."""
        assert self.parser.is_management_command("BE") is True
        assert self.parser.is_management_command("MOVER EL SL A 4905") is True
        assert self.parser.is_management_command("Hola") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])