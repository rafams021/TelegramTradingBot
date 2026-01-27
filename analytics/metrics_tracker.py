# analytics/metrics_tracker.py
"""
Sistema de tracking de métricas del trading bot.

Trackea:
- Success rate de señales
- Performance por estrategia
- Latency y slippage
- Win/Loss ratio
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional
from pathlib import Path


@dataclass
class SignalMetrics:
    """Métricas de una señal individual."""
    # Identificación
    msg_id: int
    timestamp: str
    
    # Signal data
    side: str  # BUY/SELL
    entry: float
    tps: List[float]
    sl: float
    
    # Execution
    execution_mode: str  # MARKET/LIMIT/STOP/SKIP
    num_splits: int
    executed_splits: int = 0
    
    # Timing
    parse_time_ms: Optional[float] = None
    execution_time_ms: Optional[float] = None
    
    # Slippage
    intended_price: float = 0.0
    actual_price: float = 0.0
    slippage_pips: float = 0.0
    
    # Results
    status: str = "PENDING"  # PENDING/EXECUTED/SKIPPED/FAILED
    skip_reason: Optional[str] = None
    
    # Strategy classification
    strategy: Optional[str] = None
    risk_reward_ratio: Optional[float] = None
    session: Optional[str] = None


@dataclass
class PositionMetrics:
    """Métricas de una posición (split) individual."""
    # Identificación
    signal_msg_id: int
    split_index: int
    ticket: Optional[int] = None
    
    # Trading
    side: str
    entry_intended: float
    entry_actual: Optional[float] = None
    tp: float
    sl: float
    volume: float
    
    # Results
    status: str = "OPEN"
    close_price: Optional[float] = None
    pnl_pips: Optional[float] = None
    pnl_usd: Optional[float] = None
    
    # Timing
    open_time: Optional[str] = None
    close_time: Optional[str] = None
    duration_seconds: Optional[float] = None
    
    # Management
    be_applied: bool = False
    sl_moved: bool = False


@dataclass
class SessionStats:
    """Estadísticas de una sesión de trading."""
    date: str
    
    # Signals
    total_signals: int = 0
    signals_executed: int = 0
    signals_skipped: int = 0
    signals_failed: int = 0
    
    # Execution breakdown
    market_orders: int = 0
    pending_orders: int = 0
    
    # Performance
    total_positions: int = 0
    positions_tp: int = 0
    positions_sl: int = 0
    positions_open: int = 0
    
    # Win rate
    win_rate: float = 0.0
    avg_win_pips: float = 0.0
    avg_loss_pips: float = 0.0
    
    # PnL
    total_pnl_pips: float = 0.0
    total_pnl_usd: float = 0.0
    
    # Timing
    avg_latency_ms: float = 0.0
    avg_slippage_pips: float = 0.0


class MetricsTracker:
    """
    Tracker centralizado de métricas.
    
    Mantiene historial de señales y posiciones para analytics.
    """
    
    def __init__(self, metrics_file: str = "trading_metrics.jsonl"):
        self.metrics_file = Path(metrics_file)
        self.signals: Dict[int, SignalMetrics] = {}
        self.positions: List[PositionMetrics] = []
        self._session_start = datetime.now(timezone.utc).isoformat()
    
    # ==========================================
    # Signal Tracking
    # ==========================================
    
    def track_signal_parsed(
        self,
        msg_id: int,
        side: str,
        entry: float,
        tps: List[float],
        sl: float,
        parse_time_ms: float,
    ) -> None:
        """Registra que una señal fue parseada exitosamente."""
        self.signals[msg_id] = SignalMetrics(
            msg_id=msg_id,
            timestamp=self._utc_now(),
            side=side,
            entry=entry,
            tps=tps,
            sl=sl,
            execution_mode="UNKNOWN",
            num_splits=len(tps),
            parse_time_ms=parse_time_ms,
        )
    
    def track_execution_decided(
        self,
        msg_id: int,
        mode: str,
        current_price: float,
    ) -> None:
        """Registra la decisión de ejecución."""
        if msg_id not in self.signals:
            return
        
        signal = self.signals[msg_id]
        signal.execution_mode = mode
        signal.intended_price = signal.entry
        signal.actual_price = current_price
        signal.slippage_pips = abs(current_price - signal.entry)
    
    def track_signal_executed(
        self,
        msg_id: int,
        num_executed: int,
        execution_time_ms: float,
    ) -> None:
        """Registra que una señal fue ejecutada."""
        if msg_id not in self.signals:
            return
        
        signal = self.signals[msg_id]
        signal.status = "EXECUTED"
        signal.executed_splits = num_executed
        signal.execution_time_ms = execution_time_ms
        
        self._save_signal_metrics(signal)
    
    def track_signal_skipped(
        self,
        msg_id: int,
        reason: str,
    ) -> None:
        """Registra que una señal fue skippeada."""
        if msg_id not in self.signals:
            return
        
        signal = self.signals[msg_id]
        signal.status = "SKIPPED"
        signal.skip_reason = reason
        signal.executed_splits = 0
        
        self._save_signal_metrics(signal)
    
    def track_signal_failed(
        self,
        msg_id: int,
        reason: str,
    ) -> None:
        """Registra que una señal falló."""
        if msg_id not in self.signals:
            return
        
        signal = self.signals[msg_id]
        signal.status = "FAILED"
        signal.skip_reason = reason
        
        self._save_signal_metrics(signal)
    
    # ==========================================
    # Position Tracking
    # ==========================================
    
    def track_position_opened(
        self,
        signal_msg_id: int,
        split_index: int,
        ticket: int,
        side: str,
        entry_intended: float,
        entry_actual: float,
        tp: float,
        sl: float,
        volume: float,
    ) -> None:
        """Registra que una posición fue abierta."""
        pos = PositionMetrics(
            signal_msg_id=signal_msg_id,
            split_index=split_index,
            ticket=ticket,
            side=side,
            entry_intended=entry_intended,
            entry_actual=entry_actual,
            tp=tp,
            sl=sl,
            volume=volume,
            open_time=self._utc_now(),
        )
        self.positions.append(pos)
    
    def track_position_closed(
        self,
        ticket: int,
        close_price: float,
        status: str,
    ) -> None:
        """Registra que una posición fue cerrada."""
        pos = self._find_position_by_ticket(ticket)
        if not pos:
            return
        
        pos.status = status
        pos.close_price = close_price
        pos.close_time = self._utc_now()
        
        # Calcular PnL en pips
        if pos.entry_actual:
            if pos.side == "BUY":
                pos.pnl_pips = (close_price - pos.entry_actual)
            else:
                pos.pnl_pips = (pos.entry_actual - close_price)
        
        # Calcular duración
        if pos.open_time and pos.close_time:
            open_dt = datetime.fromisoformat(pos.open_time)
            close_dt = datetime.fromisoformat(pos.close_time)
            pos.duration_seconds = (close_dt - open_dt).total_seconds()
        
        self._save_position_metrics(pos)
    
    def track_position_be_applied(self, ticket: int) -> None:
        """Registra que se aplicó break even."""
        pos = self._find_position_by_ticket(ticket)
        if pos:
            pos.be_applied = True
    
    def track_position_sl_moved(self, ticket: int) -> None:
        """Registra que se movió el SL."""
        pos = self._find_position_by_ticket(ticket)
        if pos:
            pos.sl_moved = True
    
    # ==========================================
    # Analytics & Reports
    # ==========================================
    
    def get_session_stats(self) -> SessionStats:
        """Genera estadísticas de la sesión actual."""
        stats = SessionStats(date=self._session_start[:10])
        
        # Signal stats
        for signal in self.signals.values():
            stats.total_signals += 1
            
            if signal.status == "EXECUTED":
                stats.signals_executed += 1
                if signal.execution_mode == "MARKET":
                    stats.market_orders += 1
                elif signal.execution_mode in ("LIMIT", "STOP"):
                    stats.pending_orders += 1
            elif signal.status == "SKIPPED":
                stats.signals_skipped += 1
            elif signal.status == "FAILED":
                stats.signals_failed += 1
        
        # Position stats
        wins = []
        losses = []
        
        for pos in self.positions:
            stats.total_positions += 1
            
            if pos.status == "TP_HIT":
                stats.positions_tp += 1
                if pos.pnl_pips:
                    wins.append(pos.pnl_pips)
            elif pos.status == "SL_HIT":
                stats.positions_sl += 1
                if pos.pnl_pips:
                    losses.append(pos.pnl_pips)
            elif pos.status == "OPEN":
                stats.positions_open += 1
        
        # Win rate
        closed = stats.positions_tp + stats.positions_sl
        if closed > 0:
            stats.win_rate = (stats.positions_tp / closed) * 100
        
        # Averages
        if wins:
            stats.avg_win_pips = sum(wins) / len(wins)
            stats.total_pnl_pips += sum(wins)
        
        if losses:
            stats.avg_loss_pips = sum(losses) / len(losses)
            stats.total_pnl_pips += sum(losses)
        
        # Latency & Slippage
        latencies = [s.execution_time_ms for s in self.signals.values() if s.execution_time_ms]
        if latencies:
            stats.avg_latency_ms = sum(latencies) / len(latencies)
        
        slippages = [s.slippage_pips for s in self.signals.values() if s.slippage_pips]
        if slippages:
            stats.avg_slippage_pips = sum(slippages) / len(slippages)
        
        return stats
    
    def get_success_rate_by_side(self) -> Dict[str, float]:
        """Retorna win rate separado por BUY vs SELL."""
        buy_wins = 0
        buy_total = 0
        sell_wins = 0
        sell_total = 0
        
        for pos in self.positions:
            if pos.status not in ("TP_HIT", "SL_HIT"):
                continue
            
            if pos.side == "BUY":
                buy_total += 1
                if pos.status == "TP_HIT":
                    buy_wins += 1
            else:
                sell_total += 1
                if pos.status == "TP_HIT":
                    sell_wins += 1
        
        return {
            "BUY": (buy_wins / buy_total * 100) if buy_total > 0 else 0.0,
            "SELL": (sell_wins / sell_total * 100) if sell_total > 0 else 0.0,
        }
    
    def get_skip_reasons_breakdown(self) -> Dict[str, int]:
        """Retorna breakdown de por qué se skipean señales."""
        reasons = {}
        for signal in self.signals.values():
            if signal.status == "SKIPPED" and signal.skip_reason:
                reasons[signal.skip_reason] = reasons.get(signal.skip_reason, 0) + 1
        return reasons
    
    # ==========================================
    # Persistence
    # ==========================================
    
    def _save_signal_metrics(self, signal: SignalMetrics) -> None:
        """Guarda métricas de señal en archivo."""
        try:
            with open(self.metrics_file, "a", encoding="utf-8") as f:
                data = {"type": "signal", **asdict(signal)}
                f.write(json.dumps(data, default=str) + "\n")
        except Exception:
            pass
    
    def _save_position_metrics(self, position: PositionMetrics) -> None:
        """Guarda métricas de posición en archivo."""
        try:
            with open(self.metrics_file, "a", encoding="utf-8") as f:
                data = {"type": "position", **asdict(position)}
                f.write(json.dumps(data, default=str) + "\n")
        except Exception:
            pass
    
    # ==========================================
    # Helpers
    # ==========================================
    
    def _find_position_by_ticket(self, ticket: int) -> Optional[PositionMetrics]:
        """Encuentra una posición por ticket."""
        for pos in self.positions:
            if pos.ticket == ticket:
                return pos
        return None
    
    @staticmethod
    def _utc_now() -> str:
        """Retorna timestamp UTC actual."""
        return datetime.now(timezone.utc).isoformat()


# ==========================================
# Global instance
# ==========================================

_metrics_tracker: Optional[MetricsTracker] = None


def get_metrics_tracker() -> MetricsTracker:
    """Obtiene o crea la instancia global del tracker."""
    global _metrics_tracker
    if _metrics_tracker is None:
        _metrics_tracker = MetricsTracker()
    return _metrics_tracker