# adapters/mt5_client_compat.py
"""
Wrapper de compatibilidad para mantener la API antigua de mt5_client.py funcionando.

Este archivo permite que el código existente (monitoring, executor) siga funcionando
sin cambios mientras internamente usa el nuevo MT5Client refactorizado.

FASE A - LIMPIEZA: Se agrega set_client() para que main.py registre
la instancia única de MT5Client, evitando dos conexiones paralelas.

FASE B - LIMPIEZA: Se agrega positions_get_all() para que PositionWatcher
pueda consultar todas las posiciones abiertas del bot por MAGIC number.

BACKWARD COMPATIBILITY: 100%
"""
from __future__ import annotations

from typing import Any, List, Optional, Tuple

import config as CFG
from .mt5 import MT5Client, Tick

# Cliente global (se puede setear desde main.py o crear lazy)
_client: Optional[MT5Client] = None


def set_client(client: MT5Client) -> None:
    """
    Registra la instancia de MT5Client creada en main.py.

    Debe llamarse en main.py justo después de crear MT5Client
    y antes de iniciar los watchers. Esto garantiza que toda
    la app use una única conexión MT5.

    Args:
        client: Instancia ya conectada de MT5Client
    """
    global _client
    _client = client


def _get_client() -> MT5Client:
    """
    Obtiene el cliente registrado.
    Si no fue registrado via set_client(), crea uno lazy como fallback.
    """
    global _client
    if _client is None:
        # Fallback: crear instancia propia (compatibilidad con tests/scripts)
        _client = MT5Client(
            login=CFG.MT5_LOGIN,
            password=CFG.MT5_PASSWORD,
            server=CFG.MT5_SERVER,
            symbol=CFG.SYMBOL,
            deviation=getattr(CFG, "DEVIATION", 50),
            magic=getattr(CFG, "MAGIC", 0),
            dry_run=getattr(CFG, "DRY_RUN", False),
        )
    return _client


# ==========================================
# API Pública (backward compatible)
# ==========================================

def init() -> bool:
    """Inicializa MT5 (wrapper de compatibilidad)."""
    return _get_client().connect()


def shutdown() -> None:
    """Desconecta MT5 (wrapper de compatibilidad)."""
    if _client:
        _client.disconnect()


def is_ready() -> bool:
    """Verifica si MT5 está listo."""
    return _get_client().is_ready()


def symbol_tick() -> Any:
    """Obtiene tick del símbolo."""
    return _get_client().get_tick()


def symbol_tick_safe() -> Tick:
    """Obtiene tick del símbolo (versión Tick dataclass)."""
    tick = _get_client().get_tick()
    return tick if tick else Tick(0.0, 0.0)


def get_tick() -> Optional[Tick]:
    """Alias de symbol_tick_safe()."""
    return _get_client().get_tick()


def normalize_price(price: float) -> float:
    """Normaliza un precio."""
    return _get_client().normalize_price(price)


def symbol_constraints() -> dict:
    """Obtiene restricciones del símbolo."""
    return _get_client().get_symbol_constraints()


def position_get(ticket: int) -> Any:
    """Obtiene una posición por ticket."""
    return _get_client().get_position(ticket)


def positions_get_all() -> List[Any]:
    """
    Obtiene todas las posiciones abiertas del símbolo.
    Usado por PositionWatcher para detectar cierres externos.
    Retorna lista vacía si falla, nunca None.
    """
    return _get_client().get_all_positions()


def orders_get() -> List[Any]:
    """Obtiene órdenes pendientes."""
    return _get_client().get_orders()


def open_market(side: str, vol: float, sl: float, tp: float) -> Tuple[Optional[dict], Any]:
    """Abre orden a mercado."""
    return _get_client().open_market(side, vol, sl, tp)


def open_pending(side: str, price: float, vol: float, sl: float, tp: float, mode: str) -> Tuple[Optional[dict], Any]:
    """Abre orden pendiente."""
    return _get_client().open_pending(side, mode, vol, price, sl, tp)


def cancel_order(ticket: int) -> Tuple[dict, Any]:
    """Cancela orden pendiente."""
    return _get_client().cancel_order(ticket)


def close_position(ticket: int, side: str, vol: float) -> Tuple[Optional[dict], Any]:
    """Cierra posición."""
    return _get_client().close_position(ticket, side, vol)


def modify_sl(ticket: int, sl: float, fallback_tp: Optional[float] = None) -> Tuple[Optional[dict], Any]:
    """Modifica SL preservando TP."""
    return _get_client().modify_sl(ticket, sl, fallback_tp)


def modify_sltp(ticket: int, new_sl: float, new_tp: float) -> Tuple[Optional[dict], Any]:
    """Modifica SL y TP."""
    return _get_client().modify_sltp(ticket, new_sl, new_tp)


def time_now() -> float:
    """Timestamp actual."""
    import time
    return time.time()


def account_login():
    """Login de la cuenta."""
    info = _get_client().connection.get_account_info()
    return info.get("login")


def account_server():
    """Servidor de la cuenta."""
    info = _get_client().connection.get_account_info()
    return info.get("server")


def account_balance():
    """Balance de la cuenta."""
    info = _get_client().connection.get_account_info()
    return info.get("balance")