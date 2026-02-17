# autonomous/trader.py
"""
Trader autónomo — loop principal de scanning y ejecución.

Corre en un asyncio task independiente. Cada SCAN_INTERVAL segundos:
1. Llama a MarketAnalyzer.scan()
2. Por cada señal encontrada, llama a execute_signal_direct()
3. Loggea el resultado
"""
from __future__ import annotations

import asyncio

from core.executor import execute_signal_direct
from core.state import BotState, BOT_STATE
from infrastructure.logging import get_logger
from market import MarketAnalyzer


class AutonomousTrader:
    """
    Loop de trading autónomo.

    Escanea el mercado en intervalos regulares y ejecuta
    las señales usando el mismo executor que usaba Telegram.
    """

    def __init__(
        self,
        state: BotState = BOT_STATE,
        scan_interval: int = 300,
        timeframe: str = "H1",
        candles: int = 100,
    ):
        """
        Args:
            state: Estado global del bot
            scan_interval: Segundos entre cada scan (default: 300 = 5 min)
            timeframe: Marco temporal para el analyzer (default: "H1")
            candles: Velas históricas a obtener (default: 100)
        """
        self.state = state
        self.scan_interval = scan_interval
        self.timeframe = timeframe
        self.candles = candles
        self.logger = get_logger()
        self.running = False

        self.analyzer = MarketAnalyzer(
            timeframe=timeframe,
            candles=candles,
        )

    async def run(self) -> None:
        """
        Loop principal del trader autónomo.

        Corre indefinidamente. Los errores no detienen el loop
        — se loggean y se continúa en el siguiente ciclo.
        """
        self.running = True

        self.logger.event(
            "AUTONOMOUS_TRADER_STARTED",
            scan_interval=self.scan_interval,
            timeframe=self.timeframe,
        )

        while self.running:
            try:
                await self._scan_and_execute()
            except Exception as ex:
                self.logger.error(
                    "AUTONOMOUS_TRADER_ERROR",
                    error=str(ex),
                )

            await asyncio.sleep(self.scan_interval)

    async def _scan_and_execute(self) -> None:
        """Un ciclo completo de scan + ejecución."""
        self.logger.event(
            "AUTONOMOUS_SCAN_START",
            timeframe=self.timeframe,
        )

        signals = self.analyzer.scan()

        if not signals:
            self.logger.event(
                "AUTONOMOUS_SCAN_NO_SIGNALS",
                timeframe=self.timeframe,
            )
            return

        self.logger.event(
            "AUTONOMOUS_SCAN_SIGNALS_FOUND",
            count=len(signals),
            timeframe=self.timeframe,
        )

        executed = 0
        for signal in signals:
            try:
                success = execute_signal_direct(signal, self.state)
                if success:
                    executed += 1
            except Exception as ex:
                self.logger.error(
                    "AUTONOMOUS_EXECUTE_ERROR",
                    signal_id=signal.message_id,
                    side=signal.side,
                    error=str(ex),
                )

        self.logger.event(
            "AUTONOMOUS_SCAN_COMPLETE",
            signals_found=len(signals),
            signals_executed=executed,
            timeframe=self.timeframe,
        )