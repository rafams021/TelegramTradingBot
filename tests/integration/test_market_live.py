# tests/integration/test_market_live.py
"""
Prueba de integración del MarketAnalyzer con datos reales de MT5.
Requiere MT5 activo y conectado.

No ejecuta órdenes — solo muestra las señales que encontraría.

Uso:
    python tests/integration/test_market_live.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import MetaTrader5 as mt5
import config as CFG


def main():
    print("=" * 50)
    print("TEST: MarketAnalyzer — datos reales MT5")
    print("=" * 50)

    # Conectar MT5
    print("\n[1/3] Conectando a MT5...")
    if not mt5.initialize():
        print("ERROR: No se pudo inicializar MT5")
        sys.exit(1)

    if not mt5.login(CFG.MT5_LOGIN, CFG.MT5_PASSWORD, CFG.MT5_SERVER):
        print(f"ERROR: No se pudo hacer login en {CFG.MT5_SERVER}")
        mt5.shutdown()
        sys.exit(1)

    print(f"✅ Conectado: {CFG.MT5_SERVER} | Login: {CFG.MT5_LOGIN}")

    # Importar después de conectar MT5
    from market import MarketAnalyzer

    # Correr en múltiples timeframes
    timeframes = ["M15", "H1", "H4"]

    for tf in timeframes:
        print(f"\n[2/3] Scanning {CFG.SYMBOL} en {tf}...")
        analyzer = MarketAnalyzer(timeframe=tf, candles=100)
        signals = analyzer.scan()

        if signals:
            print(f"  🎯 {len(signals)} señal(es):")
            for s in signals:
                rr = abs(s.tps[0] - s.entry) / abs(s.entry - s.sl) if s.entry != s.sl else 0
                print(f"    {s.side} | Entry: {s.entry} | SL: {s.sl} | TP1: {s.tps[0]} | R:R {rr:.1f}")
        else:
            print(f"  ⏳ Sin señales en {tf}")

    mt5.shutdown()
    print("\n[3/3] MT5 desconectado.")
    print("\nDone ✅")


if __name__ == "__main__":
    main()