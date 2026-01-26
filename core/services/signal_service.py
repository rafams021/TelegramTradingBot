# core/services/signal_service.py
"""
Servicio de procesamiento de señales.
Extrae y centraliza la lógica de negocio relacionada con señales de trading.
"""
from __future__ import annotations

from typing import List, Optional

import config as CFG
from infrastructure.logging import get_logger
from core.domain.enums import OrderSide
from core.domain.models import Signal
from core.parser import parse_signal
from core.state import BotState, SplitState


class SignalService:
    """
    Servicio para procesamiento de señales de trading.
    
    Responsabilidades:
    - Validar señales parseadas
    - Gestionar cache de mensajes
    - Crear splits (posiciones) a partir de señales
    - Verificar si TPs ya fueron alcanzados
    """
    
    def __init__(self, state: BotState):
        """
        Args:
            state: Estado global del bot
        """
        self.state = state
        self.logger = get_logger()
    
    def process_signal(
        self,
        msg_id: int,
        text: str,
        date_iso: Optional[str] = None,
        is_edit: bool = False,
    ) -> Optional[Signal]:
        """
        Procesa un mensaje de Telegram y retorna una señal válida.
        
        Gestiona:
        - Cache de mensajes para edits
        - Validación de duplicados
        - Ventana de reprocesamiento para edits
        - Parseo de señal
        
        Args:
            msg_id: ID del mensaje de Telegram
            text: Contenido del mensaje
            date_iso: Fecha del mensaje en formato ISO
            is_edit: Si es una edición de mensaje
        
        Returns:
            Signal válida o None si no se puede procesar
        """
        # 1. Gestionar cache de mensajes
        cache = self.state.upsert_msg_cache(msg_id=msg_id, text=text)
        
        # 2. Validar duplicados (solo para mensajes nuevos)
        if self.state.has_signal(msg_id) and not is_edit:
            self.logger.event(
                "SIGNAL_DUPLICATE_IGNORED",
                msg_id=msg_id,
                date=date_iso,
            )
            return None
        
        # 3. Validar ventana de reprocesamiento para edits
        if is_edit:
            if not self._is_edit_within_window(cache, msg_id, date_iso):
                return None
            
            if not self._is_edit_within_max_attempts(cache, msg_id, date_iso):
                return None
        
        # 4. Parsear señal
        sig = parse_signal(text)
        self.state.mark_parse_attempt(msg_id=msg_id, parse_failed=(sig is None))
        
        if sig is None:
            self.logger.event(
                "SIGNAL_PARSE_FAILED",
                msg_id=msg_id,
                date=date_iso,
                is_edit=is_edit,
                text=text[:200],  # Solo muestra primeros 200 chars
                attempts=cache.parse_attempts,
            )
            return None
        
        # 5. Agregar msg_id a la señal y guardarla
        sig.message_id = msg_id
        
        self.logger.event(
            "SIGNAL_PARSED",
            msg_id=msg_id,
            date=date_iso,
            side=sig.side,
            entry=sig.entry,
            tps=sig.tps,
            sl=sig.sl,
        )
        
        # 6. Guardar señal en estado
        self.state.add_signal(sig)
        
        return sig
    
    def create_splits(self, signal: Signal) -> List[SplitState]:
        """
        Crea splits (posiciones individuales) para cada TP de la señal.
        
        Args:
            signal: Señal de trading válida
        
        Returns:
            Lista de SplitState, uno por cada TP
        """
        splits = self.state.build_splits_for_signal(signal.message_id)
        
        self.logger.info(
            "Splits creados",
            signal_msg_id=signal.message_id,
            num_splits=len(splits),
            tps=[s.tp for s in splits],
        )
        
        return splits
    
    def should_skip_tp(
        self,
        side: str,
        tp: float,
        bid: float,
        ask: float
    ) -> bool:
        """
        Verifica si un TP ya fue alcanzado al momento de procesar.
        
        Si el TP ya se tocó, no tiene sentido abrir la posición.
        
        Args:
            side: "BUY" o "SELL"
            tp: Precio del take profit
            bid: Precio bid actual
            ask: Precio ask actual
        
        Returns:
            True si el TP ya fue alcanzado (skip la posición)
        """
        side_u = (side or "").upper().strip()
        
        if side_u == "BUY":
            # BUY: TP se alcanza cuando bid >= tp
            reached = float(bid) >= float(tp)
        else:
            # SELL: TP se alcanza cuando ask <= tp
            reached = float(ask) <= float(tp)
        
        if reached:
            self.logger.warning(
                "TP ya alcanzado, skip split",
                side=side,
                tp=tp,
                bid=bid,
                ask=ask,
            )
        
        return reached
    
    # ==========================================
    # Métodos privados
    # ==========================================
    
    def _is_edit_within_window(
        self,
        cache,
        msg_id: int,
        date_iso: Optional[str]
    ) -> bool:
        """Verifica si un edit está dentro de la ventana de reprocesamiento."""
        window_s = int(getattr(CFG, "TG_EDIT_REPROCESS_WINDOW_S", 180))
        
        if not cache.within_edit_window(window_s):
            self.logger.event(
                "EDIT_IGNORED_OUTSIDE_WINDOW",
                msg_id=msg_id,
                date=date_iso,
                first_seen_ts=cache.first_seen_ts,
                last_seen_ts=cache.last_seen_ts,
                window_s=window_s,
            )
            return False
        
        return True
    
    def _is_edit_within_max_attempts(
        self,
        cache,
        msg_id: int,
        date_iso: Optional[str]
    ) -> bool:
        """Verifica si un edit no ha excedido el máximo de intentos."""
        max_attempts = int(getattr(CFG, "TG_EDIT_REPROCESS_MAX_ATTEMPTS", 3))
        
        if cache.parse_attempts >= max_attempts:
            self.logger.event(
                "EDIT_IGNORED_MAX_ATTEMPTS",
                msg_id=msg_id,
                date=date_iso,
                attempts=cache.parse_attempts,
                max=max_attempts,
            )
            return False
        
        return True