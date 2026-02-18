# test_advanced.py
import sys
sys.path.insert(0, 'C:\\Users\\Robo\\TelegramTradingBot')

import MetaTrader5 as mt5
import pandas as pd
from market.strategies.reversal_advanced import ReversalAdvancedStrategy

# Conectar MT5
mt5.initialize()
mt5.login(1022962, password="", server="VTMarkets-Demo")

# Descargar datos H1 (12 meses)
rates = mt5.copy_rates_from_pos("XAUUSD-ECN", mt5.TIMEFRAME_H1, 0, 8940)
df = pd.DataFrame(rates)
df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
df.set_index("time", inplace=True)

print(f"{len(df)} velas descargadas\n")

# Crear estrategia
strategy = ReversalAdvancedStrategy(
    symbol="XAUUSD-ECN",
    magic=100,
    enable_mtf=True,
    enable_order_blocks=True,
    enable_quality_filter=True,
    min_sr_touches=3,
    impulse_multiplier=1.5
)

# Escanear señales
signals_found = 0
for i in range(200, len(df)):
    window = df.iloc[:i+1]
    current_price = float(window['close'].iloc[-1])
    
    signal = strategy.scan(window, current_price)
    
    if signal:
        signals_found += 1
        print(f"Signal #{signals_found}: {signal.side} @ {signal.entry} | Time: {window.index[-1]}")

print(f"\n✅ Total signals found: {signals_found}")
print(f"   Signals per month: {signals_found / 12:.1f}")
print(f"\n🎯 Expected improvement:")
print(f"   If WR improves from 48% to 60%+")
print(f"   This strategy should find 50-150 HIGH QUALITY signals")

mt5.shutdown()