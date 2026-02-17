# market/analyzer.py
"""
Orquestador principal del análisis de mercado.

MarketAnalyzer coordina DataProvider y las estrategias para
generar señales de trading de forma autónoma.
"""
from __future__ import annotations

from typing import List, Optional

import config as CFG
from core.models import Signal
from infrastructure.logging import get_logger

from .data_provider import DataProvider
from .strategies import BreakoutStrategy, ReversalStrategy, TrendStrategy


class MarketAnalyzer:
    """
    Orquestador del análisis de mercado autónomo.

    Responsabilidades:
    - Obtener datos históricos via DataProvider
    - Ejecutar cada estrategia activa
    - Devolver lista de señales encontradas
    - Loggear cada señal y cada scan sin señales

    Uso:
        analyzer = MarketAnalyzer()
        signals = analyzer.scan()
        for signal in signals:
            # ejecutar signal igual que las de Telegram
    """

    def __init__(
        self,
        symbol: Optional[str] = None,
        magic: Optional[int] = None,
        timeframe: str = "H1",
        candles: int = 100,
    ):
        """
        Args:
            symbol: Símbolo a analizar (default: CFG.SYMBOL)
            magic: Número mágico (default: CFG.MAGIC)
            timeframe: Marco temporal para las velas (default: "H1")
            candles: Número de velas históricas a obtener (default: 100)
        """
        self.symbol = symbol or str(CFG.SYMBOL)
        self.magic = magic or int(CFG.MAGIC)
        self.timeframe = timeframe
        self.candles = candles
        self.logger = get_logger()

        # Inicializar proveedor de datos
        self.data_provider = DataProvider(self.symbol)

        # Inicializar estrategias activas
        self.strategies = [
            BreakoutStrategy(
                symbol=self.symbol,
                magic=self.magic,
            ),
            ReversalStrategy(
                symbol=self.symbol,
                magic=self.magic,
            ),
            TrendStrategy(
                symbol=self.symbol,
                magic=self.magic,
            ),
        ]

        self.logger.event(
            "MARKET_ANALYZER_INIT",
            symbol=self.symbol,
            timeframe=self.timeframe,
            candles=self.candles,
            strategies=[s.name for s in self.strategies],
        )

    def scan(self, current_price: Optional[float] = None) -> List[Signal]:
        """
        Ejecuta un ciclo completo de análisis de mercado.

        Args:
            current_price: Precio actual (opcional, para testing).
                          Si es None, usa el último close del DataFrame.

        Returns:
            Lista de señales encontradas (puede ser vacía)
        """
        # Obtener datos históricos
        df = self.data_provider.get_candles(
            timeframe=self.timeframe,
            count=self.candles,
        )

        if df is None or len(df) == 0:
            self.logger.warning(
                "MARKET_SCAN_NO_DATA",
                symbol=self.symbol,
                timeframe=self.timeframe,
            )
            return []

        # Usar último close si no se provee precio
        price = current_price if current_price is not None else float(df["close"].iloc[-1])

        signals: List[Signal] = []

        # Ejecutar cada estrategia
        for strategy in self.strategies:
            try:
                signal = strategy.scan(df, price)

                if signal is not None:
                    signals.append(signal)
                    self.logger.event(
                        "MARKET_SIGNAL_FOUND",
                        strategy=strategy.name,
                        symbol=signal.symbol,
                        side=signal.side,
                        entry=signal.entry,
                        sl=signal.sl,
                        tps=signal.tps,
                        current_price=price,
                    )

            except Exception as ex:
                self.logger.error(
                    "MARKET_STRATEGY_ERROR",
                    strategy=strategy.name,
                    error=str(ex),
                )

        # Loggear resultado del scan
        self.logger.event(
            "MARKET_SCAN_COMPLETE",
            symbol=self.symbol,
            timeframe=self.timeframe,
            current_price=price,
            signals_found=len(signals),
            strategies_run=len(self.strategies),
        )

        return signals