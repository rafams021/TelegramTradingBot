# core/services/edit_handler.py
"""
Manejador de ediciones de mensajes de Telegram.
Previene duplicados y valida cambios significativos.
"""
from typing import Optional, List, Tuple
from datetime import datetime, timezone

from core.state import BotState
from core.domain.models import Signal
from infrastructure.logging import get_logger

logger = get_logger()


class EditHandler:
    """
    Maneja la lógica de ediciones de mensajes de Telegram.
    """
    
    def __init__(self, state: BotState, edit_window_s: int = 180):
        """
        Args:
            state: Estado del bot
            edit_window_s: Ventana de reprocesamiento en segundos
        """
        self.state = state
        self.edit_window_s = edit_window_s
    
    def should_process_edit(
        self,
        msg_id: int,
        new_text: str,
        signal: Optional[Signal] = None
    ) -> Tuple[bool, str]:
        """
        Determina si una edición debe ser procesada.
        
        Reglas:
        1. Si no existe en cache → procesar (primera vez)
        2. Si fuera de ventana Y sin cambios significativos → ignorar
        3. Si tiene splits activos → ignorar (previene duplicados)
        4. Si cambio significativo (typo) → procesar aunque fuera de ventana
        
        Args:
            msg_id: ID del mensaje
            new_text: Nuevo texto
            signal: Señal parseada (opcional)
        
        Returns:
            Tuple de (should_process, reason)
        """
        cache = self.state.msg_cache.get(msg_id)
        
        # Primera vez que vemos el mensaje
        if cache is None:
            return True, "first_time"
        
        # Verificar si está dentro de la ventana de edición
        within_window = cache.within_window(self.edit_window_s)
        
        # Verificar si ya tiene splits activos
        has_active_splits = self._has_active_splits(msg_id)
        
        if has_active_splits:
            logger.warning(
                "Edit ignored: splits already active",
                msg_id=msg_id,
                splits_count=len(self.state.get_signal(msg_id).splits) if self.state.has_signal(msg_id) else 0
            )
            return False, "splits_already_active"
        
        # Si fuera de ventana, verificar si hay cambio significativo
        if not within_window:
            if signal:
                has_significant_change = self._has_significant_change(msg_id, signal)
                if has_significant_change:
                    logger.info(
                        "Edit outside window but has significant change",
                        msg_id=msg_id,
                        old_entry=self._get_old_entry(msg_id),
                        new_entry=signal.entry
                    )
                    return True, "significant_change_despite_window"
            
            return False, "outside_window"
        
        # Dentro de ventana, procesar
        return True, "within_window"
    
    def _has_active_splits(self, msg_id: int) -> bool:
        """
        Verifica si el mensaje tiene splits activos (PENDING u OPEN).
        
        Args:
            msg_id: ID del mensaje
        
        Returns:
            True si tiene splits activos
        """
        sig_state = self.state.get_signal(msg_id)
        
        if not sig_state or not sig_state.splits:
            return False
        
        # Contar splits activos
        active_statuses = {"PENDING", "OPEN"}
        active_count = sum(
            1 for split in sig_state.splits
            if split.status in active_statuses
        )
        
        return active_count > 0
    
    def _has_significant_change(self, msg_id: int, new_signal: Signal) -> bool:
        """
        Detecta si hay un cambio significativo que justifique reprocesar.
        
        Cambios significativos:
        - Entry cambió >5% (posible corrección de typo)
        - Número de TPs cambió
        - SL cambió >10%
        
        Args:
            msg_id: ID del mensaje
            new_signal: Nueva señal parseada
        
        Returns:
            True si hay cambio significativo
        """
        old_sig_state = self.state.get_signal(msg_id)
        
        if not old_sig_state:
            return True  # No hay señal anterior
        
        old_signal = old_sig_state.signal
        
        # Cambio en entry >5%
        entry_change_pct = abs(new_signal.entry - old_signal.entry) / old_signal.entry
        if entry_change_pct > 0.05:  # 5%
            logger.debug(
                "Significant entry change detected",
                msg_id=msg_id,
                old_entry=old_signal.entry,
                new_entry=new_signal.entry,
                change_pct=entry_change_pct
            )
            return True
        
        # Cambio en número de TPs
        if len(new_signal.tps) != len(old_signal.tps):
            logger.debug(
                "TP count changed",
                msg_id=msg_id,
                old_count=len(old_signal.tps),
                new_count=len(new_signal.tps)
            )
            return True
        
        # Cambio en SL >10%
        sl_change_pct = abs(new_signal.sl - old_signal.sl) / abs(old_signal.sl)
        if sl_change_pct > 0.10:  # 10%
            logger.debug(
                "Significant SL change detected",
                msg_id=msg_id,
                old_sl=old_signal.sl,
                new_sl=new_signal.sl,
                change_pct=sl_change_pct
            )
            return True
        
        return False
    
    def _get_old_entry(self, msg_id: int) -> Optional[float]:
        """Helper para obtener el entry anterior."""
        sig_state = self.state.get_signal(msg_id)
        if sig_state:
            return sig_state.signal.entry
        return None
    
    def get_new_splits_only(self, msg_id: int) -> List:
        """
        Retorna solo los splits NUEVOS que deben ser creados.
        
        Previene duplicados: si edit pero splits ya existen, retorna lista vacía.
        
        Args:
            msg_id: ID del mensaje
        
        Returns:
            Lista de splits nuevos (status == "NEW")
        """
        sig_state = self.state.get_signal(msg_id)
        
        if not sig_state or not sig_state.splits:
            return []
        
        # Filtrar solo splits NEW
        new_splits = [
            split for split in sig_state.splits
            if getattr(split, "status", None) == "NEW"
        ]
        
        return new_splits
    
    def should_extend_edit_window(
        self,
        msg_id: int,
        new_signal: Signal
    ) -> bool:
        """
        Determina si se debe extender la ventana de edición.
        
        Casos:
        - Typo obvio corregido (delta >100 puntos)
        - Primera corrección después de error de parse
        
        Args:
            msg_id: ID del mensaje
            new_signal: Nueva señal
        
        Returns:
            True si se debe extender la ventana
        """
        cache = self.state.msg_cache.get(msg_id)
        
        # Si hubo error de parse antes, extender ventana
        if cache and cache.parse_failed and cache.parse_attempts > 0:
            return True
        
        # Si hay cambio muy grande (typo), extender ventana
        if self._has_significant_change(msg_id, new_signal):
            return True
        
        return False