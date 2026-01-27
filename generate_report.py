#!/usr/bin/env python3
# generate_report.py
"""
Script para generar reportes de trading.

Uso:
    python generate_report.py              # Reporte de hoy
    python generate_report.py 2026-01-27   # Reporte de fecha específica
"""
import sys
from analytics.reports import ReportGenerator


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else None
    
    # Reporte diario
    print(ReportGenerator.generate_daily_report(date))
    
    # Strategy breakdown
    print(ReportGenerator.generate_strategy_breakdown())
    
    # Session breakdown
    print(ReportGenerator.generate_session_breakdown())


if __name__ == "__main__":
    main()