# adapters/mt5/connection.py
"""
Gestión de conexión con MetaTrader 5.
Maneja inicialización, login y estado de la conexión.
"""
from __future__ import annotations

import MetaTrader5 as mt5
from infrastructure.logging import get_logger

from .types import get_mt5_error


class MT5Connection:
    """
    Gestiona la conexión con MetaTrader 5.
    
    Responsabilidades:
    - Inicializar MT5
    - Login con credenciales
    - Mantener estado de conexión
    - Shutdown limpio
    """
    
    def __init__(self, login: int, password: str, server: str):
        """
        Args:
            login: Número de cuenta MT5
            password: Contraseña de la cuenta
            server: Servidor del broker
        """
        self.login = login
        self.password = password
        self.server = server
        self.logger = get_logger()
        self._is_connected = False
    
    def connect(self) -> bool:
        """
        Conecta con MT5: inicializa y hace login.
        
        Returns:
            True si la conexión fue exitosa
        """
        if self._is_connected:
            self.logger.debug("MT5 ya está conectado")
            return True
        
        # 1. Inicializar MT5
        if not mt5.initialize():
            error = get_mt5_error()
            self.logger.error(
                "Fallo inicialización MT5",
                server=self.server,
                login=self.login,
                error_code=error.code,
                error_desc=error.description,
            )
            return False
        
        self.logger.info("MT5 inicializado correctamente")
        
        # 2. Login
        try:
            ok_login = bool(mt5.login(self.login, self.password, self.server))
        except Exception as ex:
            self.logger.error(
                "Excepción en MT5 login",
                login=self.login,
                server=self.server,
                error=str(ex),
            )
            ok_login = False
        
        if not ok_login:
            error = get_mt5_error()
            self.logger.error(
                "Fallo login MT5",
                login=self.login,
                server=self.server,
                error_code=error.code,
                error_desc=error.description,
            )
            return False
        
        # 3. Verificar account_info
        try:
            info = mt5.account_info()
            if info:
                self.logger.info(
                    "Login MT5 exitoso",
                    login=info.login,
                    server=info.server,
                    balance=info.balance,
                    currency=info.currency,
                )
        except Exception as ex:
            self.logger.warning(
                "No se pudo obtener account_info",
                error=str(ex),
            )
        
        self._is_connected = True
        return True
    
    def disconnect(self) -> None:
        """Desconecta de MT5 de forma limpia."""
        if not self._is_connected:
            return
        
        try:
            mt5.shutdown()
            self.logger.info("MT5 desconectado correctamente")
        except Exception as ex:
            self.logger.error("Error al desconectar MT5", error=str(ex))
        finally:
            self._is_connected = False
    
    def is_connected(self) -> bool:
        """
        Verifica si está conectado.
        
        Returns:
            True si la conexión está activa
        """
        return self._is_connected
    
    def get_account_info(self) -> dict:
        """
        Obtiene información de la cuenta.
        
        Returns:
            Dict con login, server, balance, etc.
        """
        if not self._is_connected:
            return {}
        
        try:
            info = mt5.account_info()
            if not info:
                return {}
            
            return {
                "login": info.login,
                "server": info.server,
                "balance": info.balance,
                "equity": info.equity,
                "margin": info.margin,
                "margin_free": info.margin_free,
                "currency": info.currency,
            }
        except Exception as ex:
            self.logger.error("Error obteniendo account_info", error=str(ex))
            return {}