# analytics/reports.py
"""
Generador de reportes de trading.
"""
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict

from .metrics_tracker import SignalMetrics, PositionMetrics


class ReportGenerator:
    """Genera reportes de performance."""
    
    @staticmethod
    def load_metrics(filepath: str = "trading_metrics.jsonl") -> tuple[List[SignalMetrics], List[PositionMetrics]]:
        """Carga métricas desde archivo."""
        signals = []
        positions = []
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    data = json.loads(line)
                    
                    if data.get("type") == "signal":
                        # Recrear SignalMetrics
                        data.pop("type")
                        signals.append(SignalMetrics(**data))
                    elif data.get("type") == "position":
                        data.pop("type")
                        positions.append(PositionMetrics(**data))
        except FileNotFoundError:
            pass
        
        return signals, positions
    
    @classmethod
    def generate_daily_report(cls, date: str = None) -> str:
        """Genera reporte diario en texto."""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        
        signals, positions = cls.load_metrics()
        
        # Filtrar por fecha
        signals = [s for s in signals if s.timestamp.startswith(date)]
        positions = [p for p in positions if p.open_time and p.open_time.startswith(date)]
        
        # Stats
        executed = len([s for s in signals if s.status == "EXECUTED"])
        skipped = len([s for s in signals if s.status == "SKIPPED"])
        
        closed_positions = [p for p in positions if p.status in ("TP_HIT", "SL_HIT")]
        tp_hit = len([p for p in closed_positions if p.status == "TP_HIT"])
        
        win_rate = (tp_hit / len(closed_positions) * 100) if closed_positions else 0
        
        total_pnl = sum(p.pnl_pips or 0 for p in closed_positions)
        
        # Report
        report = f"""
╔═══════════════════════════════════════════════════════╗
║         TRADING BOT - DAILY REPORT                   ║
║         {date}                                ║
╠═══════════════════════════════════════════════════════╣
║                                                       ║
║  📊 SIGNALS                                           ║
║  ├─ Total Received:  {len(signals):>4}                          ║
║  ├─ Executed:        {executed:>4}  ({executed/len(signals)*100 if signals else 0:>5.1f}%)          ║
║  └─ Skipped:         {skipped:>4}  ({skipped/len(signals)*100 if signals else 0:>5.1f}%)          ║
║                                                       ║
║  💰 PERFORMANCE                                       ║
║  ├─ Win Rate:        {win_rate:>5.1f}%                        ║
║  ├─ Total PnL:       {total_pnl:>+6.1f} pips                  ║
║  ├─ Positions TP:    {tp_hit:>4}                          ║
║  └─ Positions SL:    {len(closed_positions) - tp_hit:>4}                          ║
║                                                       ║
╚═══════════════════════════════════════════════════════╝
"""
        return report
    
    @classmethod
    def generate_strategy_breakdown(cls) -> str:
        """Genera breakdown por estrategia."""
        signals, positions = cls.load_metrics()
        
        # Agrupar por estrategia (si existe)
        strategies = {}
        for signal in signals:
            strategy = signal.strategy or "UNKNOWN"
            if strategy not in strategies:
                strategies[strategy] = {"total": 0, "executed": 0}
            
            strategies[strategy]["total"] += 1
            if signal.status == "EXECUTED":
                strategies[strategy]["executed"] += 1
        
        report = "\n📈 STRATEGY BREAKDOWN:\n"
        report += "─" * 50 + "\n"
        
        for strategy, stats in strategies.items():
            exec_rate = stats["executed"] / stats["total"] * 100 if stats["total"] > 0 else 0
            report += f"{strategy:15} | Total: {stats['total']:3} | Executed: {stats['executed']:3} ({exec_rate:>5.1f}%)\n"
        
        return report
    
    @classmethod
    def generate_session_breakdown(cls) -> str:
        """Genera breakdown por sesión de trading."""
        signals, _ = cls.load_metrics()
        
        # Agrupar por sesión
        sessions = {}
        for signal in signals:
            session = signal.session or "UNKNOWN"
            if session not in sessions:
                sessions[session] = {"total": 0, "executed": 0}
            
            sessions[session]["total"] += 1
            if signal.status == "EXECUTED":
                sessions[session]["executed"] += 1
        
        report = "\n🕐 SESSION BREAKDOWN:\n"
        report += "─" * 50 + "\n"
        
        for session, stats in sessions.items():
            exec_rate = stats["executed"] / stats["total"] * 100 if stats["total"] > 0 else 0
            report += f"{session:20} | Total: {stats['total']:3} | Executed: {stats['executed']:3} ({exec_rate:>5.1f}%)\n"
        
        return report