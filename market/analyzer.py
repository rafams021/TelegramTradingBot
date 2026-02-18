# market/analyzer.py
from __future__ import annotations

from typing import List, Optional

import config as CFG
from core.state import Signal
from infrastructure.logging import get_logger

from .data_provider import DataProvider
from .strategies import ReversalStrategy, TrendStrategy


class MarketAnalyzer:
    """
    Orquestador del analisis de mercado autonomo.

    Ejecuta Reversal y Trend sobre datos H1 y devuelve señales.
    Breakout descartado tras backtest (4.4% win rate, -$609 en 6 meses).
    """

    def __init__(
        self,
        symbol: Optional[str] = None,
        magic: Optional[int] = None,
        timeframe: str = "H1",
        candles: int = 100,
    ):
        self.symbol = symbol or str(CFG.SYMBOL)
        self.magic = magic or int(CFG.MAGIC)
        self.timeframe = timeframe
        self.candles = candles
        self.logger = get_logger()

        self.data_provider = DataProvider(self.symbol)

        self.strategies = [
            ReversalStrategy(symbol=self.symbol, magic=self.magic),
            TrendStrategy(symbol=self.symbol, magic=self.magic),
        ]

        self.logger.event(
            "MARKET_ANALYZER_INIT",
            symbol=self.symbol,
            timeframe=self.timeframe,
            candles=self.candles,
            strategies=[s.name for s in self.strategies],
        )

    def scan(self, current_price: Optional[float] = None) -> List[Signal]:
        df = self.data_provider.get_candles(
            timeframe=self.timeframe,
            count=self.candles,
        )

        if df is None or df.empty:
            self.logger.event("MARKET_ANALYZER_NO_DATA", symbol=self.symbol)
            return []

        price = current_price or float(df["close"].iloc[-1])
        signals: List[Signal] = []

        for strategy in self.strategies:
            try:
                signal = strategy.scan(df, price)
                if signal:
                    self.logger.event(
                        "SIGNAL_GENERATED",
                        strategy=strategy.name,
                        side=signal.side,
                        entry=signal.entry,
                        sl=signal.sl,
                        tps=signal.tps,
                    )
                    signals.append(signal)
            except Exception as ex:
                self.logger.error(
                    "STRATEGY_SCAN_ERROR",
                    strategy=strategy.name,
                    error=str(ex),
                )

        if not signals:
            self.logger.event("MARKET_ANALYZER_NO_SIGNALS", symbol=self.symbol)

        return signals