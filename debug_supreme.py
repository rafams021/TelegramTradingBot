# debug_supreme.py
"""
Script para debuggear por qué Supreme Mode da 0 trades
"""
import sys
sys.path.insert(0, 'C:\\Users\\Robo\\TelegramTradingBot')

import MetaTrader5 as mt5
import pandas as pd
from market.strategies.reversal import ReversalStrategy

# Conectar MT5
mt5.initialize()
mt5.login(1022962, password="", server="VTMarkets-Demo")

# Descargar datos
rates = mt5.copy_rates_from_pos("XAUUSD-ECN", mt5.TIMEFRAME_H1, 0, 8940)
df = pd.DataFrame(rates)
df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
df.set_index("time", inplace=True)

print(f"✅ {len(df)} velas descargadas\n")

# Crear estrategia BÁSICA primero
strategy_basic = ReversalStrategy(
    symbol="XAUUSD-ECN",
    magic=100,
    supreme_mode=False,  # Modo básico
)

# Crear estrategia SUPREME
strategy_supreme = ReversalStrategy(
    symbol="XAUUSD-ECN",
    magic=100,
    supreme_mode=True,  # Modo supreme
)

# Escanear con BÁSICO
print("="*60)
print("TEST 1: MODO BÁSICO")
print("="*60)
signals_basic = 0
for i in range(200, min(500, len(df))):  # Solo primeras 300 velas para debug
    window = df.iloc[:i+1]
    current_price = float(window['close'].iloc[-1])
    
    signal = strategy_basic.scan(window, current_price)
    
    if signal:
        signals_basic += 1
        if signals_basic <= 3:  # Mostrar primeras 3
            print(f"✅ Señal #{signals_basic}: {signal.side} @ {signal.entry} | {window.index[-1]}")

print(f"\n📊 Total señales BÁSICO en 300 velas: {signals_basic}")

# Escanear con SUPREME
print("\n" + "="*60)
print("TEST 2: MODO SUPREME")
print("="*60)
signals_supreme = 0
for i in range(200, min(500, len(df))):
    window = df.iloc[:i+1]
    current_price = float(window['close'].iloc[-1])
    
    signal = strategy_supreme.scan(window, current_price)
    
    if signal:
        signals_supreme += 1
        if signals_supreme <= 3:
            print(f"✅ Señal #{signals_supreme}: {signal.side} @ {signal.entry} | {window.index[-1]}")

print(f"\n📊 Total señales SUPREME en 300 velas: {signals_supreme}")

# DEBUG: Escanear UNA vela con logging detallado
print("\n" + "="*60)
print("TEST 3: DEBUG DETALLADO DE UNA VELA")
print("="*60)

# Buscar una vela que dé señal en básico
for i in range(200, len(df)):
    window = df.iloc[:i+1]
    current_price = float(window['close'].iloc[-1])
    ts = window.index[-1]
    
    signal_basic = strategy_basic.scan(window, current_price)
    
    if signal_basic:
        print(f"\n🔍 Vela con señal BÁSICA encontrada: {ts}")
        print(f"   Precio: {current_price}")
        print(f"   Señal: {signal_basic.side}")
        
        # Ahora probar con SUPREME y ver qué pasa
        print(f"\n🔍 Probando SUPREME en la misma vela...")
        
        # Verificar cada filtro manualmente
        from market.indicators import support_resistance_levels, rsi, atr
        
        # 1. Sesión
        hour = ts.hour
        in_session = (8 <= hour < 10) or (13 <= hour < 17)
        print(f"   1. Sesión ({hour}h): {'✅ OK' if in_session else '❌ RECHAZADO'}")
        
        # 2. S/R levels
        levels = support_resistance_levels(window, lookback=20)
        print(f"   2. S/R Levels: {len(levels) if levels else 0} niveles")
        
        if levels:
            closest = min(levels, key=lambda l: abs(l - current_price))
            distance = abs(current_price - closest)
            print(f"      Nivel más cercano: {closest:.2f} (distancia: {distance:.2f})")
            print(f"      Proximidad: {'✅ OK' if distance <= 8.0 else '❌ RECHAZADO'}")
            
            # 3. Quality S/R
            touches = sum(1 for j in range(max(0, len(window) - 50), len(window))
                         if abs(window.iloc[j]['low'] - closest) < 3.0 or 
                            abs(window.iloc[j]['high'] - closest) < 3.0)
            print(f"   3. S/R Quality: {touches} toques ({'✅ OK' if touches >= 2 else '❌ RECHAZADO'})")
            
            # 4. RSI
            current_rsi = float(rsi(window, period=14).iloc[-1])
            print(f"   4. RSI: {current_rsi:.1f}")
            
            # 5. Order Blocks
            strategy_supreme.enable_order_blocks = True
            order_blocks = strategy_supreme._detect_order_blocks(window)
            print(f"   5. Order Blocks: {len(order_blocks)} detectados")
            
            if order_blocks:
                in_ob = strategy_supreme._is_near_order_block(current_price, order_blocks, signal_basic.side)
                print(f"      En Order Block: {'✅ SÍ' if in_ob else '❌ NO'}")
            
            # 6. FVG
            fvg_zones = strategy_supreme._detect_fair_value_gaps(window)
            print(f"   6. FVG: {len(fvg_zones)} detectadas")
            
            if fvg_zones:
                in_fvg = strategy_supreme._is_near_fvg(current_price, fvg_zones, signal_basic.side)
                print(f"      En FVG: {'✅ SÍ' if in_fvg else '❌ NO'}")
            
            # 7. Estructura (OB o FVG)
            has_structure = False
            if order_blocks:
                has_structure = strategy_supreme._is_near_order_block(current_price, order_blocks, signal_basic.side)
            if fvg_zones and not has_structure:
                has_structure = strategy_supreme._is_near_fvg(current_price, fvg_zones, signal_basic.side)
            
            print(f"   7. Estructura (OB o FVG): {'✅ OK' if has_structure else '❌ RECHAZADO'}")
            
            # 8. Impulse
            has_impulse = strategy_supreme._has_recent_impulse(window, signal_basic.side)
            print(f"   8. Impulse: {'✅ SÍ' if has_impulse else '⚠️  NO (pero no obligatorio)'}")
            
            # 9. Volume
            has_volume = strategy_supreme._has_volume_confirmation(window)
            print(f"   9. Volume: {'✅ SÍ' if has_volume else '⚠️  NO (pero no obligatorio)'}")
        
        # Ahora scan real con supreme
        signal_supreme = strategy_supreme.scan(window, current_price)
        print(f"\n🎯 Resultado SUPREME: {'✅ SEÑAL GENERADA' if signal_supreme else '❌ RECHAZADA'}")
        
        break  # Solo debuggear la primera

print("\n" + "="*60)
print("FIN DEL DEBUG")
print("="*60)

mt5.shutdown()