# adapters/mt5/client.py
"""
Cliente principal de MetaTrader 5.

Este es un wrapper simplificado que mantiene backward compatibility
con el mt5_client.py original mientras separa responsabilidades.

FASE B - LIMPIEZA: Se agrega get_all_positions() para que PositionWatcher
pueda detectar cierres externos filtrando por MAGIC number.
"""
from __future__ import annotations

import time
from typing import Any, List, Optional, Tuple

import MetaTrader5 as mt5

from .connection import MT5Connection
from .types import Tick, SymbolInfo, to_tick, to_symbol_info, get_mt5_error
from infrastructure.logging import get_logger


class MT5Client:
    """
    Cliente principal para interactuar con MetaTrader 5.

    Combina:
    - Conexión (MT5Connection)
    - Operaciones de símbolos
    - Operaciones de órdenes
    - Operaciones de posiciones
    """

    def __init__(self, login: int, password: str, server: str, symbol: str,
                 deviation: int = 50, magic: int = 0, dry_run: bool = False):
        self.symbol = symbol
        self.deviation = deviation
        self.magic = magic
        self.dry_run = dry_run
        self.logger = get_logger()

        self.connection = MT5Connection(login, password, server)
        self._symbol_selected = False

    def connect(self) -> bool:
        if not self.connection.connect():
            return False
        return self._ensure_symbol_selected()

    def disconnect(self) -> None:
        self.connection.disconnect()

    def is_ready(self) -> bool:
        return self.connection.is_connected() and self._symbol_selected

    # ==========================================
    # Symbol Operations
    # ==========================================

    def get_tick(self) -> Optional[Tick]:
        if not self._ensure_symbol_selected():
            return None

        for _ in range(3):
            try:
                native_tick = mt5.symbol_info_tick(self.symbol)
                if native_tick:
                    return to_tick(native_tick)
            except Exception as ex:
                self.logger.warning("Error obteniendo tick", error=str(ex))
            time.sleep(0.2)

        self.logger.error("No se pudo obtener tick", symbol=self.symbol)
        return None

    def get_symbol_info(self) -> Optional[SymbolInfo]:
        try:
            native_info = mt5.symbol_info(self.symbol)
            return to_symbol_info(native_info)
        except Exception as ex:
            self.logger.error("Error obteniendo symbol_info", error=str(ex))
            return None

    def normalize_price(self, price: float) -> float:
        info = self.get_symbol_info()
        if not info:
            return round(price, 2)
        return round(price, info.digits)

    def get_symbol_constraints(self) -> dict:
        info = self.get_symbol_info()
        if not info:
            return {
                "point": 0.01,
                "digits": 2,
                "stops_level_points": 0,
                "freeze_level_points": 0,
            }
        return {
            "point": info.point,
            "digits": info.digits,
            "stops_level_points": info.stops_level,
            "freeze_level_points": info.freeze_level,
        }

    # ==========================================
    # Order Operations
    # ==========================================

    def open_market(self, side: str, volume: float, sl: float, tp: float) -> Tuple[Optional[dict], Any]:
        if not self.is_ready():
            return None, None

        tick = self.get_tick()
        if not tick:
            return None, None

        side_u = side.upper().strip()
        order_type = mt5.ORDER_TYPE_BUY if side_u == "BUY" else mt5.ORDER_TYPE_SELL
        price = tick.ask if side_u == "BUY" else tick.bid

        base_req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": float(volume),
            "type": order_type,
            "price": self.normalize_price(price),
            "sl": self.normalize_price(sl),
            "tp": self.normalize_price(tp) if tp else 0.0,
            "deviation": self.deviation,
            "magic": self.magic,
            "comment": "TG_BOT",
        }

        for fill in [mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_RETURN]:
            req = dict(base_req)
            req["type_filling"] = fill

            if self.dry_run:
                self.logger.info("DRY_RUN: Market order", req=req)
                return req, None

            res = mt5.order_send(req)
            ret = int(getattr(res, "retcode", 0) or 0)

            if ret == 10009:
                return req, res
            if ret != 10030:
                break

        return req, res

    def open_pending(self, side: str, mode: str, volume: float, price: float,
                     sl: float, tp: float) -> Tuple[Optional[dict], Any]:
        if not self.is_ready():
            return None, None

        side_u = side.upper().strip()
        mode_u = mode.upper().strip()

        if side_u == "BUY" and mode_u == "LIMIT":
            order_type = mt5.ORDER_TYPE_BUY_LIMIT
        elif side_u == "BUY" and mode_u == "STOP":
            order_type = mt5.ORDER_TYPE_BUY_STOP
        elif side_u == "SELL" and mode_u == "LIMIT":
            order_type = mt5.ORDER_TYPE_SELL_LIMIT
        else:
            order_type = mt5.ORDER_TYPE_SELL_STOP

        req = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": self.symbol,
            "volume": float(volume),
            "type": order_type,
            "price": self.normalize_price(price),
            "sl": self.normalize_price(sl),
            "tp": self.normalize_price(tp) if tp else 0.0,
            "deviation": self.deviation,
            "magic": self.magic,
            "comment": "TG_BOT_PENDING",
            "type_filling": mt5.ORDER_FILLING_RETURN,
        }

        if self.dry_run:
            self.logger.info("DRY_RUN: Pending order", req=req)
            return req, None

        res = mt5.order_send(req)
        return req, res

    def cancel_order(self, order_ticket: int) -> Tuple[dict, Any]:
        req = {
            "action": mt5.TRADE_ACTION_REMOVE,
            "order": int(order_ticket),
        }

        if self.dry_run:
            self.logger.info("DRY_RUN: Cancel order", req=req)
            return req, None

        res = mt5.order_send(req)
        return req, res

    # ==========================================
    # Position Operations
    # ==========================================

    def get_position(self, ticket: int) -> Any:
        try:
            positions = mt5.positions_get(ticket=ticket)
            return positions[0] if positions else None
        except Exception as ex:
            self.logger.error("Error obteniendo posición", ticket=ticket, error=str(ex))
            return None

    def get_all_positions(self) -> List[Any]:
        """
        Obtiene todas las posiciones abiertas del símbolo con el MAGIC del bot.

        Filtra por symbol Y magic para asegurarse de retornar solo
        posiciones abiertas por este bot, ignorando posiciones manuales
        u otros bots en la misma cuenta.

        Returns:
            Lista de posiciones (puede ser vacía, nunca None)
        """
        try:
            all_positions = mt5.positions_get(symbol=self.symbol) or []
            # Filtrar solo las del bot por MAGIC number
            return [
                p for p in all_positions
                if int(getattr(p, "magic", 0) or 0) == self.magic
            ]
        except Exception as ex:
            self.logger.error("Error obteniendo todas las posiciones", error=str(ex))
            return []

    def close_position(self, ticket: int, side: str, volume: float) -> Tuple[Optional[dict], Any]:
        if not self.is_ready():
            return None, None

        tick = self.get_tick()
        if not tick:
            return None, None

        side_u = side.upper().strip()
        order_type = mt5.ORDER_TYPE_SELL if side_u == "BUY" else mt5.ORDER_TYPE_BUY
        price = tick.bid if side_u == "BUY" else tick.ask

        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "position": int(ticket),
            "volume": float(volume),
            "type": order_type,
            "price": self.normalize_price(price),
            "deviation": self.deviation,
            "magic": self.magic,
            "comment": "TG_BOT_CLOSE",
            "type_filling": mt5.ORDER_FILLING_RETURN,
        }

        if self.dry_run:
            self.logger.info("DRY_RUN: Close position", req=req)
            return req, None

        res = mt5.order_send(req)
        return req, res

    def modify_sl(self, ticket: int, new_sl: float, fallback_tp: Optional[float] = None) -> Tuple[Optional[dict], Any]:
        pos = self.get_position(ticket)
        if pos:
            tp_current = float(getattr(pos, "tp", 0.0) or 0.0)
        else:
            tp_current = 0.0

        tp_use = tp_current if tp_current > 0 else (fallback_tp or 0.0)
        return self.modify_sltp(ticket, new_sl, tp_use)

    def modify_sltp(self, ticket: int, new_sl: float, new_tp: float) -> Tuple[Optional[dict], Any]:
        req = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": self.symbol,
            "position": int(ticket),
            "sl": self.normalize_price(new_sl),
            "tp": self.normalize_price(new_tp) if new_tp else 0.0,
            "magic": self.magic,
            "comment": "TG_BOT_MODIFY",
        }

        if self.dry_run:
            self.logger.info("DRY_RUN: Modify SL/TP", req=req)
            return req, None

        res = mt5.order_send(req)
        return req, res

    def get_orders(self) -> List[Any]:
        """Obtiene todas las órdenes pendientes del símbolo."""
        try:
            return mt5.orders_get(symbol=self.symbol) or []
        except Exception:
            return []

    # ==========================================
    # Helpers Privados
    # ==========================================

    def _ensure_symbol_selected(self) -> bool:
        if self._symbol_selected:
            return True

        try:
            info = mt5.symbol_info(self.symbol)
            if not info:
                self.logger.error("Símbolo no existe", symbol=self.symbol)
                return False

            if not mt5.symbol_select(self.symbol, True):
                self.logger.error("No se pudo seleccionar símbolo", symbol=self.symbol)
                return False

            self._symbol_selected = True
            self.logger.info("Símbolo seleccionado", symbol=self.symbol)
            return True

        except Exception as ex:
            self.logger.error("Error seleccionando símbolo", symbol=self.symbol, error=str(ex))
            return False

    @staticmethod
    def time_now() -> float:
        return time.time()