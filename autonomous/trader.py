# autonomous/trader.py
"""
Trader autónomo — arquitectura dual loop.

_candle_loop(): cada SCAN_INTERVAL segundos (default 300s = 5min)
    → Corre H1: Breakout, Reversal, Trend
    → Señales de setup estructurado

_tick_loop(): cada 100ms
    → Corre M1: MomentumStrategy
    → Detecta movimientos explosivos inmediatos
    → Entra a mercado sin esperar siguiente candle loop
    → Heartbeat cada 5 min para confirmar que el loop está vivo
"""
from __future__ import annotations

import asyncio
import time

import config as CFG
from core.executor import execute_signal_direct
from core.state import BotState, BOT_STATE
from infrastructure.logging import get_logger
from market import MarketAnalyzer
from market.data_provider import DataProvider
from market.strategies import MomentumStrategy


class AutonomousTrader:
    """
    Loop de trading autónomo con arquitectura dual.

    Candle loop → estrategias estructurales en H1 cada 5 min.
    Tick loop   → momentum en M1 cada 100ms.
    """

    def __init__(
        self,
        state: BotState = BOT_STATE,
        scan_interval: int = 300,
        timeframe: str = "H1",
        candles: int = 100,
        tick_interval_ms: int = 100,
    ):
        """
        Args:
            state: Estado global del bot
            scan_interval: Segundos entre cada candle scan (default: 300)
            timeframe: Marco temporal para el analyzer (default: "H1")
            candles: Velas históricas a obtener (default: 100)
            tick_interval_ms: Milisegundos entre cada tick scan (default: 100)
        """
        self.state = state
        self.scan_interval = scan_interval
        self.timeframe = timeframe
        self.candles = candles
        self.tick_interval_s = tick_interval_ms / 1000.0
        self.logger = get_logger()
        self.running = False

        # Loop lento: Breakout + Reversal + Trend en H1
        self.analyzer = MarketAnalyzer(
            timeframe=timeframe,
            candles=candles,
        )

        # Loop rápido: Momentum en M1
        self._momentum_symbol = str(CFG.SYMBOL)
        self._momentum_magic = int(CFG.MAGIC)
        self._momentum_data = DataProvider(self._momentum_symbol)
        self._momentum_strategy = MomentumStrategy(
            symbol=self._momentum_symbol,
            magic=self._momentum_magic,
        )

        # Cooldown de momentum: evitar señales repetidas en el mismo movimiento
        # Se resetea cada vez que el precio cambia de dirección
        self._last_momentum_side: str | None = None
        self._momentum_cooldown_s: float = 60.0   # 1 min entre señales momentum
        self._last_momentum_time: float = 0.0

        # Heartbeat del tick loop
        self._tick_count: int = 0
        self._tick_errors: int = 0
        self._tick_last_heartbeat: float = 0.0
        self._tick_heartbeat_interval: float = 300.0  # heartbeat cada 5 min

    async def run(self) -> None:
        """
        Arranca ambos loops de forma concurrente.

        _candle_loop y _tick_loop corren como tasks paralelas.
        Si uno falla, el otro continúa.
        """
        self.running = True

        self.logger.event(
            "AUTONOMOUS_TRADER_STARTED",
            scan_interval=self.scan_interval,
            timeframe=self.timeframe,
            tick_interval_ms=int(self.tick_interval_s * 1000),
        )

        candle_task = asyncio.create_task(self._candle_loop())
        tick_task = asyncio.create_task(self._tick_loop())

        # Esperar ambos (corren indefinidamente hasta self.running = False)
        await asyncio.gather(candle_task, tick_task, return_exceptions=True)

    async def _candle_loop(self) -> None:
        """
        Loop lento — estrategias estructurales H1.

        Cada SCAN_INTERVAL segundos:
        → Breakout: LIMIT en nivel roto
        → Reversal: MARKET en soporte/resistencia + RSI extremo
        → Trend:    MARKET en pullback a SMA20
        """
        self.logger.event(
            "CANDLE_LOOP_STARTED",
            scan_interval=self.scan_interval,
            timeframe=self.timeframe,
        )

        while self.running:
            try:
                await self._scan_and_execute()
            except Exception as ex:
                self.logger.error(
                    "CANDLE_LOOP_ERROR",
                    error=str(ex),
                )

            await asyncio.sleep(self.scan_interval)

    async def _tick_loop(self) -> None:
        """
        Loop rápido — MomentumStrategy en M1.

        Cada 100ms obtiene las últimas 30 velas M1 y
        evalúa si hay momentum explosivo para entrar a mercado.

        Cooldown de 60s entre señales para evitar sobretrading.
        Heartbeat cada 5 min para confirmar que el loop está vivo.
        """
        self.logger.event(
            "TICK_LOOP_STARTED",
            tick_interval_ms=int(self.tick_interval_s * 1000),
        )
        self._tick_last_heartbeat = time.monotonic()

        while self.running:
            try:
                await self._tick_scan()
                self._tick_count += 1
            except Exception as ex:
                self._tick_errors += 1
                self.logger.error(
                    "TICK_LOOP_ERROR",
                    error=str(ex),
                )

            # Heartbeat cada 5 minutos
            now = time.monotonic()
            if (now - self._tick_last_heartbeat) >= self._tick_heartbeat_interval:
                self.logger.event(
                    "TICK_LOOP_HEARTBEAT",
                    ticks_processed=self._tick_count,
                    errors=self._tick_errors,
                    cooldown_active=(
                        (now - self._last_momentum_time) < self._momentum_cooldown_s
                    ),
                    last_momentum_side=self._last_momentum_side,
                )
                self._tick_last_heartbeat = now
                self._tick_count = 0
                self._tick_errors = 0

            await asyncio.sleep(self.tick_interval_s)

    async def _scan_and_execute(self) -> None:
        """Un ciclo completo del candle loop: scan H1 + ejecución."""
        self.logger.event(
            "CANDLE_SCAN_START",
            timeframe=self.timeframe,
        )

        signals = self.analyzer.scan()

        if not signals:
            self.logger.event(
                "CANDLE_SCAN_NO_SIGNALS",
                timeframe=self.timeframe,
            )
            return

        self.logger.event(
            "CANDLE_SCAN_SIGNALS_FOUND",
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
                    "CANDLE_EXECUTE_ERROR",
                    signal_id=signal.message_id,
                    side=signal.side,
                    error=str(ex),
                )

        self.logger.event(
            "CANDLE_SCAN_COMPLETE",
            signals_found=len(signals),
            signals_executed=executed,
            timeframe=self.timeframe,
        )

    async def _tick_scan(self) -> None:
        """Un ciclo del tick loop: obtiene M1 y evalúa momentum."""
        now = time.monotonic()

        # Cooldown activo → saltar
        if (now - self._last_momentum_time) < self._momentum_cooldown_s:
            return

        # Obtener velas M1 recientes (30 velas = 30 minutos)
        df = self._momentum_data.get_candles(timeframe="M1", count=30)
        if df is None or len(df) == 0:
            return

        current_price = float(df["close"].iloc[-1])
        signal = self._momentum_strategy.scan(df, current_price)

        if signal is None:
            return

        # Si la dirección cambió respecto al último momentum, resetear cooldown
        if signal.side != self._last_momentum_side:
            self._last_momentum_side = signal.side
        else:
            # Misma dirección dentro del cooldown → ya está activo
            return

        self.logger.event(
            "MOMENTUM_SIGNAL_FOUND",
            side=signal.side,
            entry=signal.entry,
            sl=signal.sl,
            tps=signal.tps,
            current_price=current_price,
        )

        try:
            success = execute_signal_direct(signal, self.state)
            if success:
                self._last_momentum_time = now
                self.logger.event(
                    "MOMENTUM_EXECUTED",
                    side=signal.side,
                    entry=signal.entry,
                )
        except Exception as ex:
            self.logger.error(
                "MOMENTUM_EXECUTE_ERROR",
                side=signal.side,
                error=str(ex),
            )