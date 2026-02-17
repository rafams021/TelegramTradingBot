# market/data_provider.py
"""
Proveedor de datos de mercado desde MetaTrader 5.

Responsabilidad única: obtener velas históricas (OHLCV) de MT5
y devolverlas como DataFrame de pandas para que las estrategias
puedan calcular indicadores.
"""
from __future__ import annotations

from typing import Optional

import MetaTrader5 as mt5
import pandas as pd

from infrastructure.logging import get_logger


class DataProvider:
    """
    Obtiene datos históricos de MT5 en formato DataFrame.

    El DataFrame resultante tiene columnas:
        time, open, high, low, close, tick_volume, spread, real_volume
    Con índice datetime UTC.
    """

    # Timeframes disponibles mapeados a constantes MT5
    TIMEFRAMES = {
        "M1":  mt5.TIMEFRAME_M1,
        "M5":  mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1":  mt5.TIMEFRAME_H1,
        "H4":  mt5.TIMEFRAME_H4,
        "D1":  mt5.TIMEFRAME_D1,
    }

    def __init__(self, symbol: str):
        """
        Args:
            symbol: Símbolo a operar (ej: "XAUUSD-ECN")
        """
        self.symbol = symbol
        self.logger = get_logger()

    def get_candles(
        self,
        timeframe: str = "H1",
        count: int = 100,
    ) -> Optional[pd.DataFrame]:
        """
        Obtiene las últimas N velas del símbolo.

        Args:
            timeframe: Marco temporal ("M1", "M5", "M15", "M30", "H1", "H4", "D1")
            count: Número de velas a obtener (desde la más reciente hacia atrás)

        Returns:
            DataFrame con columnas OHLCV e índice datetime UTC,
            o None si falla la obtención.
        """
        tf = self.TIMEFRAMES.get(timeframe.upper())
        if tf is None:
            self.logger.error(
                "Timeframe inválido",
                timeframe=timeframe,
                valid=list(self.TIMEFRAMES.keys()),
            )
            return None

        try:
            rates = mt5.copy_rates_from_pos(self.symbol, tf, 0, count)
        except Exception as ex:
            self.logger.error(
                "Error obteniendo velas de MT5",
                symbol=self.symbol,
                timeframe=timeframe,
                error=str(ex),
            )
            return None

        if rates is None or len(rates) == 0:
            self.logger.warning(
                "MT5 devolvió velas vacías",
                symbol=self.symbol,
                timeframe=timeframe,
                count=count,
            )
            return None

        # Convertir a DataFrame
        df = pd.DataFrame(rates)

        # Convertir timestamp unix a datetime UTC
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df.set_index("time", inplace=True)

        return df