# core/services/message_classifier.py
"""
Clasificador de mensajes de Telegram.
Reduce ruido en logs al filtrar mensajes que obviamente NO son señales.
"""
import re
from typing import Tuple
from infrastructure.logging import get_logger

logger = get_logger()


class MessageClassifier:
    """
    Clasifica mensajes para determinar si vale la pena intentar parsearlos.
    """
    
    # Patrones que indican posible señal de trading
    SIGNAL_INDICATORS = [
        r'\bXAUUSD\b',           # Símbolo
        r'\b(BUY|SELL)\b',       # Lado
        r'\bTP\b',               # Take Profit
        r'\b(SL|STOP\s*LOSS)\b', # Stop Loss
    ]
    
    # Patrones que indican definitivamente NO es señal
    NON_SIGNAL_PATTERNS = [
        r'^(SL|TP)\s*[❌✅]',                    # "SL❌", "TP✅"
        r'^\+\d+\s*PIPS?\s*[✅❌]',              # "+40 PIPS✅"
        r'\bCHICOS\b',                           # Mensajes a la comunidad
        r'\bFALTA\s+POCO\b',                     # Anuncios
        r'\bGRATUITAMENTE\b',                    # Marketing
        r'\bACCESO\b.*\bOPORTUNIDAD\b',          # Marketing
        r'^CANCELAR',                            # Comandos
        r'^CERRAR\s+(AHORA|TODO)',               # Comandos de gestión
        r'Modificar\s+el\s+Take\s+profit',       # Notas
        r'Take\s+profit\s+\d+.*[✅❌]',          # Confirmaciones de TP
    ]
    
    def __init__(self):
        # Compilar regexes para performance
        self.signal_regexes = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.SIGNAL_INDICATORS
        ]
        
        self.non_signal_regexes = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.NON_SIGNAL_PATTERNS
        ]
    
    def classify(self, text: str) -> Tuple[str, str]:
        """
        Clasifica un mensaje.
        
        Args:
            text: Texto del mensaje
        
        Returns:
            Tuple de (category, reason)
            - category: "SIGNAL_CANDIDATE", "NON_SIGNAL", "MANAGEMENT", "UNKNOWN"
            - reason: Razón de la clasificación
        
        Example:
            >>> classifier.classify("SL❌")
            ("NON_SIGNAL", "matches_non_signal_pattern")
            
            >>> classifier.classify("XAUUSD BUY 5090")
            ("SIGNAL_CANDIDATE", "has_signal_indicators")
        """
        if not text or not text.strip():
            return "NON_SIGNAL", "empty_text"
        
        text = text.strip()
        
        # Primero verificar patrones de NO-señal
        for regex in self.non_signal_regexes:
            if regex.search(text):
                return "NON_SIGNAL", f"matches_non_signal_pattern: {regex.pattern}"
        
        # Verificar si parece comando de gestión
        if self._is_management_command(text):
            return "MANAGEMENT", "management_command_detected"
        
        # Contar cuántos indicadores de señal tiene
        indicator_count = sum(
            1 for regex in self.signal_regexes
            if regex.search(text)
        )
        
        # Si tiene al menos 2 indicadores, es candidato a señal
        if indicator_count >= 2:
            return "SIGNAL_CANDIDATE", f"has_{indicator_count}_signal_indicators"
        
        # Si tiene XAUUSD pero nada más, podría ser señal incompleta
        if any(regex.pattern == r'\bXAUUSD\b' for regex in self.signal_regexes if regex.search(text)):
            return "SIGNAL_CANDIDATE", "has_symbol_might_be_incomplete"
        
        # No parece señal
        return "UNKNOWN", "insufficient_signal_indicators"
    
    def should_attempt_parse(self, text: str) -> Tuple[bool, str]:
        """
        Determina si se debe intentar parsear el mensaje.
        
        Args:
            text: Texto del mensaje
        
        Returns:
            Tuple de (should_parse, reason)
        
        Example:
            >>> classifier.should_attempt_parse("CHICOS, ESTAMOS...")
            (False, "NON_SIGNAL: matches_non_signal_pattern")
            
            >>> classifier.should_attempt_parse("XAUUSD BUY 5090")
            (True, "SIGNAL_CANDIDATE: has_3_signal_indicators")
        """
        category, reason = self.classify(text)
        
        if category == "SIGNAL_CANDIDATE":
            return True, f"{category}: {reason}"
        
        return False, f"{category}: {reason}"
    
    def _is_management_command(self, text: str) -> bool:
        """
        Detecta si es un comando de gestión (BE, CLOSE, MOVE_SL).
        """
        management_patterns = [
            r'\bBE\b',
            r'MOVER.*SL',
            r'CERRAR.*TP',
            r'CERRAR.*TODO',
            r'CLOSE.*ALL',
        ]
        
        text_upper = text.upper()
        
        for pattern in management_patterns:
            if re.search(pattern, text_upper):
                return True
        
        return False
    
    def get_classification_stats(self, messages: list) -> dict:
        """
        Obtiene estadísticas de clasificación para un conjunto de mensajes.
        
        Útil para análisis de logs.
        
        Args:
            messages: Lista de textos de mensajes
        
        Returns:
            Dict con estadísticas
        """
        stats = {
            "total": len(messages),
            "signal_candidates": 0,
            "non_signals": 0,
            "management": 0,
            "unknown": 0,
        }
        
        for msg in messages:
            category, _ = self.classify(msg)
            
            if category == "SIGNAL_CANDIDATE":
                stats["signal_candidates"] += 1
            elif category == "NON_SIGNAL":
                stats["non_signals"] += 1
            elif category == "MANAGEMENT":
                stats["management"] += 1
            else:
                stats["unknown"] += 1
        
        return stats


# Instancia global para uso fácil
_classifier = MessageClassifier()


def should_attempt_parse(text: str) -> Tuple[bool, str]:
    """
    Función de conveniencia para clasificar mensajes.
    
    Example:
        >>> from core.services.message_classifier import should_attempt_parse
        >>> should_parse, reason = should_attempt_parse("SL❌")
        >>> print(should_parse)
        False
    """
    return _classifier.should_attempt_parse(text)