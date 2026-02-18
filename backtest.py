# backtest.py
"""
Backtester refactorizado con soporte para SUPREME MODE

MODOS DE OPERACIÓN:
===================
1. Básico: python backtest.py --months 12 --strategy REVERSAL --csv
2. Advanced filters: python backtest.py --months 12 --strategy REVERSAL --advanced --csv  
3. SUPREME: python backtest.py --months 12 --strategy REVERSAL --supreme --csv

SUPREME MODE:
- Usa ReversalStrategy class con todos los filtros
- Order Blocks + Fair Value Gaps + MTF + Quality filters
- Target: 65-75% WR con 50-150 trades
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from typing import List, Optional

import MetaTrader5 as mt5
import numpy as np
import pandas as pd

# ============================================================================
# IMPORTS
# ============================================================================

# ML Feature Extractor
try:
    from ml.feature_extractor import extract_features
    ML_ENABLED = True
    print("✅ ML Feature Extractor cargado")
except ImportError:
    ML_ENABLED = False
    print("⚠️  ML Feature Extractor NO disponible")

# ReversalStrategy class para Supreme Mode
try:
    from market.strategies.reversal import ReversalStrategy
    SUPREME_AVAILABLE = True
except ImportError:
    SUPREME_AVAILABLE = False
    print("⚠️  ReversalStrategy class not found - Supreme mode disabled")

# Config
SYMBOL = "XAUUSD-ECN"
MAGIC = 6069104329
VOLUME = 0.05

_SL_DISTANCE = 6.0
_TP_DISTANCES = (5.0, 11.0, 16.0)


# ==================================================
# MODELS
# ==================================================

@dataclass
class BacktestTrade:
    strategy: str
    side: str
    entry: float
    sl: float
    tp1: float
    tp2: float
    tp3: float
    entry_time: pd.Timestamp
    exit_time: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    result: str = "OPEN"
    pnl: float = 0.0


@dataclass
class BacktestResult:
    strategy: str
    trades: List[BacktestTrade] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len([t for t in self.trades if t.result != "OPEN"])

    @property
    def wins(self) -> int:
        return len([t for t in self.trades if t.result.startswith("TP")])

    @property
    def losses(self) -> int:
        return len([t for t in self.trades if t.result == "SL"])

    @property
    def win_rate(self) -> float:
        return (self.wins / self.total * 100) if self.total > 0 else 0.0

    @property
    def total_pnl(self) -> float:
        return sum(t.pnl for t in self.trades if t.result != "OPEN")

    @property
    def avg_pnl(self) -> float:
        closed = [t for t in self.trades if t.result != "OPEN"]
        return (sum(t.pnl for t in closed) / len(closed)) if closed else 0.0


# ==================================================
# MT5 CONNECTION
# ==================================================

def connect_mt5() -> bool:
    if not mt5.initialize():
        print("❌ No se pudo inicializar MT5")
        return False
    if not mt5.login(1022962, password="", server="VTMarkets-Demo"):
        print("❌ Login MT5 falló")
        mt5.shutdown()
        return False
    if not mt5.symbol_select(SYMBOL, True):
        print(f"❌ No se pudo seleccionar {SYMBOL}")
        mt5.shutdown()
        return False
    print(f"MT5 conectado - {SYMBOL}")
    return True


def get_historical_data(timeframe_str: str, months: int) -> pd.DataFrame:
    tf_map = {
        "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
        "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4, "D1": mt5.TIMEFRAME_D1,
    }
    tf = tf_map.get(timeframe_str.upper())
    if tf is None:
        print(f"❌ Timeframe inválido: {timeframe_str}")
        sys.exit(1)

    candles_per_month = {
        "M1": 43200, "M5": 8640, "M15": 2880,
        "H1": 720, "H4": 180, "D1": 22,
    }
    count = candles_per_month.get(timeframe_str.upper(), 720) * months + 300

    rates = mt5.copy_rates_from_pos(SYMBOL, tf, 0, count)
    if rates is None or len(rates) == 0:
        print("❌ No se pudieron obtener datos históricos")
        sys.exit(1)

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df.set_index("time", inplace=True)
    print(f"{len(df)} velas descargadas ({timeframe_str}) -- "
          f"{df.index[0].strftime('%Y-%m-%d')} a {df.index[-1].strftime('%Y-%m-%d')}")
    return df


def get_d1_data() -> pd.DataFrame:
    rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_D1, 0, 400)
    if rates is None:
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df.set_index("time", inplace=True)
    return df


# ==================================================
# INDICATORS & HELPERS (importados de backtest original)
# ==================================================

def calc_tps(side: str, entry: float) -> tuple:
    if side == "BUY":
        return tuple(round(entry + d, 2) for d in _TP_DISTANCES)
    return tuple(round(entry - d, 2) for d in _TP_DISTANCES)


def calc_sl(side: str, entry: float) -> float:
    if side == "BUY":
        return round(entry - _SL_DISTANCE, 2)
    return round(entry + _SL_DISTANCE, 2)


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()


def ema_fn(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi_fn(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - (100 / (1 + rs))).fillna(50)


def atr_fn(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"].shift(1)
    tr = pd.concat([high - low, (high - close).abs(), (low - close).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def support_resistance(df: pd.DataFrame, lookback: int = 20) -> List[float]:
    if len(df) < lookback:
        return []
    recent = df.iloc[-lookback:]
    candidates = sorted(list(recent["high"]) + list(recent["low"]))
    levels, used = [], set()
    for i, price in enumerate(candidates):
        if i in used:
            continue
        touches = [j for j, p in enumerate(candidates) if abs(p - price) <= 2.0]
        if len(touches) >= 2:
            levels.append(float(np.mean([candidates[j] for j in touches])))
            used.update(touches)
    return sorted(levels)


def is_valid_session(ts: pd.Timestamp, session_filter: str = "24h") -> bool:
    if session_filter == "24h":
        return True
    hour_utc = ts.hour
    if session_filter == "eu_ny":
        return 8 <= hour_utc < 22
    if session_filter == "ny_only":
        return 13 <= hour_utc < 22
    return True


def check_ema_hard(window: pd.DataFrame, side: str) -> bool:
    if len(window) < 201:
        return True
    ema50 = float(ema_fn(window["close"], 50).iloc[-1])
    ema200 = float(ema_fn(window["close"], 200).iloc[-1])
    if pd.isna(ema50) or pd.isna(ema200):
        return True
    return (ema50 > ema200) if side == "BUY" else (ema50 < ema200)


# ==================================================
# STRATEGY SCANNERS (legacy - para backward compatibility)
# ==================================================

def scan_reversal(df_h1, i, ema_filter=False, session_filter="24h", rsi_oversold=45.0,
                  rsi_overbought=55.0, proximity=8.0, enable_advanced=False,
                  strict_session=False, order_blocks=False, impulse_filter=False,
                  min_sr_touches=2) -> Optional[BacktestTrade]:
    """Legacy reversal scanner con filtros inline (para backward compatibility)"""
    if i < 30:
        return None

    window = df_h1.iloc[max(0, i - 100):i + 1].copy()
    current_price = float(window["close"].iloc[-1])
    ts = window.index[-1]

    if strict_session or enable_advanced:
        hour = ts.hour
        if not ((8 <= hour < 10) or (13 <= hour < 17)):
            return None
    elif not is_valid_session(ts, session_filter):
        return None

    levels = support_resistance(window, lookback=20)
    if not levels:
        return None

    current_rsi = float(rsi_fn(window["close"]).iloc[-1])
    atr_val = float(atr_fn(window).iloc[-1])
    if pd.isna(atr_val) or atr_val <= 0:
        return None

    closest = min(levels, key=lambda l: abs(l - current_price))
    if abs(current_price - closest) > proximity:
        return None

    # Filtros avanzados (código original)
    if enable_advanced or min_sr_touches > 2:
        touches = sum(1 for j in range(max(0, len(window) - 50), len(window))
                     if abs(window.iloc[j]['low'] - closest) < 3.0 or 
                        abs(window.iloc[j]['high'] - closest) < 3.0)
        if touches < min_sr_touches:
            return None

    if impulse_filter or enable_advanced:
        has_impulse = any(abs(window.iloc[j]['close'] - window.iloc[j]['open']) > (1.5 * atr_val)
                         for j in range(max(0, len(window) - 5), len(window)))
        if not has_impulse:
            return None

    if enable_advanced:
        current_volume = float(window['tick_volume'].iloc[-1])
        avg_volume = float(window['tick_volume'].tail(20).mean())
        if current_volume < (avg_volume * 1.3):
            return None

    if order_blocks or enable_advanced:
        in_order_block = False
        for j in range(max(0, len(window) - 30), len(window) - 1):
            curr = window.iloc[j]
            next_c = window.iloc[j + 1]
            next_size = abs(next_c['close'] - next_c['open'])
            
            if current_rsi < rsi_oversold:
                if (curr['close'] < curr['open'] and next_c['close'] > next_c['open'] and
                    next_size > (1.5 * atr_val) and curr['low'] <= current_price <= curr['high']):
                    in_order_block = True
                    break
            
            if current_rsi > rsi_overbought:
                if (curr['close'] > curr['open'] and next_c['close'] < next_c['open'] and
                    next_size > (1.5 * atr_val) and curr['low'] <= current_price <= curr['high']):
                    in_order_block = True
                    break
        
        if not in_order_block:
            return None

    # Generate signals
    if current_price <= closest and current_rsi < rsi_oversold:
        if ema_filter and not check_ema_hard(window, "BUY"):
            return None
        entry = round(current_price, 2)
        sl = calc_sl("BUY", entry)
        tp1, tp2, tp3 = calc_tps("BUY", entry)
        
        trade = BacktestTrade(
            strategy="REVERSAL", side="BUY",
            entry=entry, sl=sl, tp1=tp1, tp2=tp2, tp3=tp3, entry_time=ts,
        )
        
        if ML_ENABLED:
            try:
                features = extract_features(df=window, signal_side="BUY", sr_level=closest)
                for key, value in features.items():
                    setattr(trade, key, value)
            except:
                pass
        return trade

    if current_price >= closest and current_rsi > rsi_overbought:
        if ema_filter and not check_ema_hard(window, "SELL"):
            return None
        entry = round(current_price, 2)
        sl = calc_sl("SELL", entry)
        tp1, tp2, tp3 = calc_tps("SELL", entry)
        
        trade = BacktestTrade(
            strategy="REVERSAL", side="SELL",
            entry=entry, sl=sl, tp1=tp1, tp2=tp2, tp3=tp3, entry_time=ts,
        )
        
        if ML_ENABLED:
            try:
                features = extract_features(df=window, signal_side="SELL", sr_level=closest)
                for key, value in features.items():
                    setattr(trade, key, value)
            except:
                pass
        return trade
    
    return None


def scan_trend(df_h1, i, ema_filter=False, session_filter="24h") -> Optional[BacktestTrade]:
    """Trend strategy scanner"""
    if i < 55:
        return None

    window = df_h1.iloc[max(0, i - 100):i + 1].copy()
    current_price = float(window["close"].iloc[-1])
    ts = window.index[-1]

    if not is_valid_session(ts, session_filter):
        return None

    sma20 = float(sma(window["close"], 20).iloc[-1])
    sma50 = float(sma(window["close"], 50).iloc[-1])

    if pd.isna(sma20) or pd.isna(sma50):
        return None

    atr_val = float(atr_fn(window).iloc[-1])
    if pd.isna(atr_val) or atr_val <= 0:
        return None

    if abs(current_price - sma20) > 2.0:
        return None

    if sma20 > sma50 and current_price >= sma20:
        if ema_filter and not check_ema_hard(window, "BUY"):
            return None
        entry = round(current_price, 2)
        sl = calc_sl("BUY", entry)
        tp1, tp2, tp3 = calc_tps("BUY", entry)
        
        trade = BacktestTrade(
            strategy="TREND", side="BUY",
            entry=entry, sl=sl, tp1=tp1, tp2=tp2, tp3=tp3, entry_time=ts,
        )
        
        if ML_ENABLED:
            try:
                features = extract_features(df=window, signal_side="BUY", sma_fast=sma20, sma_slow=sma50)
                for key, value in features.items():
                    setattr(trade, key, value)
            except:
                pass
        return trade

    if sma20 < sma50 and current_price <= sma20:
        if ema_filter and not check_ema_hard(window, "SELL"):
            return None
        entry = round(current_price, 2)
        sl = calc_sl("SELL", entry)
        tp1, tp2, tp3 = calc_tps("SELL", entry)
        
        trade = BacktestTrade(
            strategy="TREND", side="SELL",
            entry=entry, sl=sl, tp1=tp1, tp2=tp2, tp3=tp3, entry_time=ts,
        )
        
        if ML_ENABLED:
            try:
                features = extract_features(df=window, signal_side="SELL", sma_fast=sma20, sma_slow=sma50)
                for key, value in features.items():
                    setattr(trade, key, value)
            except:
                pass
        return trade
    
    return None


# ==================================================
# EXIT SIMULATION
# ==================================================

PNL_PER_DOLLAR = 0.05

def simulate_exit(trade: BacktestTrade, df: pd.DataFrame, entry_i: int,
                  tp1_only: bool = False, spread_cost: float = 0.0) -> BacktestTrade:
    max_bars = min(entry_i + 201, len(df))
    sl_pnl = round(-(_SL_DISTANCE * 10 * PNL_PER_DOLLAR) - spread_cost, 2)
    tp1_pnl = round(_TP_DISTANCES[0] * 10 * PNL_PER_DOLLAR - spread_cost, 2)
    tp2_pnl = round(_TP_DISTANCES[1] * 10 * PNL_PER_DOLLAR - spread_cost, 2)
    tp3_pnl = round(_TP_DISTANCES[2] * 10 * PNL_PER_DOLLAR - spread_cost, 2)

    for j in range(entry_i + 1, max_bars):
        candle = df.iloc[j]
        high = float(candle["high"])
        low = float(candle["low"])

        if trade.side == "BUY":
            if low <= trade.sl:
                trade.exit_time, trade.exit_price, trade.result, trade.pnl = df.index[j], trade.sl, "SL", sl_pnl
                return trade
            if not tp1_only and high >= trade.tp3:
                trade.exit_time, trade.exit_price, trade.result, trade.pnl = df.index[j], trade.tp3, "TP3", tp3_pnl
                return trade
            if not tp1_only and high >= trade.tp2:
                trade.exit_time, trade.exit_price, trade.result, trade.pnl = df.index[j], trade.tp2, "TP2", tp2_pnl
                return trade
            if high >= trade.tp1:
                trade.exit_time, trade.exit_price, trade.result, trade.pnl = df.index[j], trade.tp1, "TP1", tp1_pnl
                return trade

        elif trade.side == "SELL":
            if high >= trade.sl:
                trade.exit_time, trade.exit_price, trade.result, trade.pnl = df.index[j], trade.sl, "SL", sl_pnl
                return trade
            if not tp1_only and low <= trade.tp3:
                trade.exit_time, trade.exit_price, trade.result, trade.pnl = df.index[j], trade.tp3, "TP3", tp3_pnl
                return trade
            if not tp1_only and low <= trade.tp2:
                trade.exit_time, trade.exit_price, trade.result, trade.pnl = df.index[j], trade.tp2, "TP2", tp2_pnl
                return trade
            if low <= trade.tp1:
                trade.exit_time, trade.exit_price, trade.result, trade.pnl = df.index[j], trade.tp1, "TP1", tp1_pnl
                return trade

    return trade


# ==================================================
# MAIN BACKTEST LOOP
# ==================================================

def run_backtest(df_h1, df_d1, strategies, cooldown_bars=3, tp1_only=False, ema_filter=False,
                 session_filter="24h", fix_lookahead=False, spread_cost=0.0, rsi_oversold=45.0,
                 rsi_overbought=55.0, proximity=8.0, enable_advanced=False, strict_session=False,
                 order_blocks=False, impulse_filter=False, min_sr_touches=2,
                 supreme_mode=False) -> List[BacktestResult]:
    
    results_map = {s: BacktestResult(strategy=s) for s in strategies}
    last_trade_i = -999
    
    # Supreme Mode: Crear instancia de ReversalStrategy
    supreme_strategy = None
    if supreme_mode and SUPREME_AVAILABLE and "REVERSAL" in strategies:
        supreme_strategy = ReversalStrategy(
            symbol=SYMBOL,
            magic=MAGIC,
            supreme_mode=True,
            rsi_oversold=rsi_oversold,
            rsi_overbought=rsi_overbought,
            proximity_pips=proximity,
        )
        print("✅ SUPREME MODE activado - usando ReversalStrategy class")

    for i in range(len(df_h1)):
        if i - last_trade_i < cooldown_bars:
            continue

        signal = None
        strategy_name = None

        if "REVERSAL" in strategies:
            # ================================================================
            # SUPREME MODE: Usa ReversalStrategy class
            # ================================================================
            if supreme_mode and supreme_strategy:
                window = df_h1.iloc[max(0, i - 100):i + 1].copy()
                current_price = float(window["close"].iloc[-1])
                ts = window.index[-1]
                
                # Scan con la clase
                strategy_signal = supreme_strategy.scan(df=window, current_price=current_price)
                
                if strategy_signal:
                    # Convertir Signal a BacktestTrade
                    signal = BacktestTrade(
                        strategy="REVERSAL_SUPREME",
                        side=strategy_signal.side,
                        entry=strategy_signal.entry,
                        sl=strategy_signal.sl,
                        tp1=strategy_signal.tps[0],
                        tp2=strategy_signal.tps[1],
                        tp3=strategy_signal.tps[2],
                        entry_time=ts,
                    )
                    strategy_name = "REVERSAL"
                    
                    # Features ML
                    if ML_ENABLED:
                        try:
                            levels = support_resistance(window, lookback=20)
                            closest = min(levels, key=lambda l: abs(l - current_price)) if levels else current_price
                            features = extract_features(df=window, signal_side=strategy_signal.side, sr_level=closest)
                            for key, value in features.items():
                                setattr(signal, key, value)
                        except:
                            pass
            else:
                # ================================================================
                # MODO NORMAL: Usa scan_reversal() function
                # ================================================================
                signal = scan_reversal(
                    df_h1, i, ema_filter=ema_filter, session_filter=session_filter,
                    rsi_oversold=rsi_oversold, rsi_overbought=rsi_overbought,
                    proximity=proximity, enable_advanced=enable_advanced,
                    strict_session=strict_session, order_blocks=order_blocks,
                    impulse_filter=impulse_filter, min_sr_touches=min_sr_touches,
                )
                if signal:
                    strategy_name = "REVERSAL"

        if signal is None and "TREND" in strategies:
            signal = scan_trend(df_h1, i, ema_filter=ema_filter, session_filter=session_filter)
            if signal:
                strategy_name = "TREND"

        if signal and strategy_name:
            entry_index = i + 1 if fix_lookahead else i
            if entry_index >= len(df_h1):
                continue
            
            closed_trade = simulate_exit(signal, df_h1, entry_index, tp1_only=tp1_only, spread_cost=spread_cost)
            results_map[strategy_name].trades.append(closed_trade)
            last_trade_i = entry_index

    return list(results_map.values())


# ==================================================
# REPORTING
# ==================================================

def print_report(results, timeframe, months, tp1_only=False, ema_filter=False,
                session_filter="24h", fix_lookahead=False, enable_advanced=False,
                strict_session=False, order_blocks=False, impulse_filter=False,
                min_sr_touches=2, supreme_mode=False):
    
    print(f"\n{'='*60}")
    print(f"  BACKTEST - {timeframe} ({months} meses)")
    print(f"{'='*60}")
    print(f"  TP1-only        : {'SÍ' if tp1_only else 'NO'}")
    print(f"  EMA filter      : {'SÍ' if ema_filter else 'NO'}")
    print(f"  Session filter  : {session_filter.upper()}")
    print(f"  Fix lookahead   : {'SÍ' if fix_lookahead else 'NO'}")
    
    if supreme_mode:
        print(f"  {'---SUPREME MODE---':^60}")
        print(f"  SUPREME MODE    : ✅ ACTIVADO (FVG + OB + MTF + Quality)")
    elif enable_advanced or strict_session or order_blocks or impulse_filter or min_sr_touches > 2:
        print(f"  {'---ADVANCED FILTERS---':^60}")
        if enable_advanced:
            print(f"  All advanced    : ✅ SÍ (session+OB+impulse+volume+quality)")
        else:
            if strict_session:
                print(f"  Strict session  : ✅ SÍ (London/NY open only)")
            if order_blocks:
                print(f"  Order Blocks    : ✅ SÍ")
            if impulse_filter:
                print(f"  Impulse filter  : ✅ SÍ (>1.5x ATR)")
            if min_sr_touches > 2:
                print(f"  S/R quality     : ✅ SÍ (min {min_sr_touches} touches)")
    
    print(f"{'='*60}\n")

    grand_trades = grand_wins = 0
    grand_pnl = 0.0

    for r in results:
        if r.total == 0:
            print(f"  {r.strategy:<10} : sin trades")
            continue

        print(f"  {r.strategy}")
        print(f"  {'-'*58}")
        print(f"  Trades          : {r.total}")
        print(f"  Win rate        : {r.wins}/{r.total} = {r.win_rate:.1f}%")

        buys = [t for t in r.trades if t.side == "BUY" and t.result != "OPEN"]
        sells = [t for t in r.trades if t.side == "SELL" and t.result != "OPEN"]
        buy_wr = len([t for t in buys if t.result.startswith("TP")])
        sell_wr = len([t for t in sells if t.result.startswith("TP")])

        if buys:
            print(f"  BUY win rate    : {buy_wr}/{len(buys)} = {buy_wr/len(buys)*100:.1f}%")
        if sells:
            print(f"  SELL win rate   : {sell_wr}/{len(sells)} = {sell_wr/len(sells)*100:.1f}%")
        
        print(f"  P&L total       : ${r.total_pnl:>+.2f}")
        print(f"  P&L promedio    : ${r.avg_pnl:>+.2f} por trade")

        grand_trades += r.total
        grand_wins += r.wins
        grand_pnl += r.total_pnl

    print(f"\n{'='*60}")
    print(f"  TOTAL COMBINADO")
    print(f"{'-'*60}")
    grand_wr = (grand_wins / grand_trades * 100) if grand_trades > 0 else 0
    print(f"  Trades  : {grand_trades}")
    print(f"  Win Rate: {grand_wr:.1f}%")
    print(f"  P&L     : ${grand_pnl:+.2f}")
    print("=" * 60 + "\n")


def save_csv(results, filename="backtest_trades.csv"):
    rows = []
    for r in results:
        for t in r.trades:
            row = {
                "strategy": t.strategy, "side": t.side, "entry_time": t.entry_time,
                "exit_time": t.exit_time, "entry": t.entry, "sl": t.sl,
                "tp1": t.tp1, "tp2": t.tp2, "tp3": t.tp3,
                "exit_price": t.exit_price, "result": t.result, "pnl": t.pnl,
            }
            
            if ML_ENABLED:
                for attr_name in dir(t):
                    if not attr_name.startswith('_') and attr_name not in row:
                        attr_value = getattr(t, attr_name, None)
                        if isinstance(attr_value, (int, float)):
                            row[attr_name] = attr_value
            
            rows.append(row)
    
    if rows:
        df = pd.DataFrame(rows)
        df.to_csv(filename, index=False)
        print(f"✅ Trades guardados en {filename}")
        print(f"   Total trades: {len(df)}")


# ==================================================
# MAIN
# ==================================================

def main():
    parser = argparse.ArgumentParser(description="Backtester con SUPREME MODE")
    parser.add_argument("--months", type=int, default=3)
    parser.add_argument("--timeframe", type=str, default="H1")
    parser.add_argument("--strategy", type=str, default="ALL")
    parser.add_argument("--cooldown", type=int, default=3)
    parser.add_argument("--tp1-only", action="store_true")
    parser.add_argument("--ema-filter", action="store_true")
    parser.add_argument("--session", type=str, default="24h", choices=["24h", "eu_ny", "ny_only"])
    parser.add_argument("--fix-lookahead", action="store_true")
    parser.add_argument("--spread", type=float, default=0.30)
    parser.add_argument("--rsi-oversold", type=float, default=45.0)
    parser.add_argument("--rsi-overbought", type=float, default=55.0)
    parser.add_argument("--proximity", type=float, default=8.0)
    parser.add_argument("--sl-distance", type=float, default=6.0)
    parser.add_argument("--tp1-distance", type=float, default=5.0)
    parser.add_argument("--csv", action="store_true")
    
    # Advanced filters
    parser.add_argument("--advanced", action="store_true", help="Enable ALL advanced filters")
    parser.add_argument("--supreme", action="store_true", help="SUPREME MODE (FVG + OB + MTF + Quality)")
    parser.add_argument("--strict-session", action="store_true", help="Only London/NY open")
    parser.add_argument("--order-blocks", action="store_true", help="Enable Order Blocks")
    parser.add_argument("--impulse-filter", action="store_true", help="Require impulse >1.5x ATR")
    parser.add_argument("--min-touches", type=int, default=2, help="Min S/R touches")
    
    args = parser.parse_args()

    global _SL_DISTANCE, _TP_DISTANCES
    _SL_DISTANCE = args.sl_distance
    tp1 = args.tp1_distance
    tp2 = round(tp1 * 2.2, 1)
    tp3 = round(tp1 * 3.2, 1)
    _TP_DISTANCES = (tp1, tp2, tp3)

    print(f"Config: SL=${_SL_DISTANCE} | TP1=${tp1} TP2=${tp2} TP3=${tp3} | RR={tp1/_SL_DISTANCE:.2f}:1")

    if not connect_mt5():
        sys.exit(1)

    all_strategies = ["REVERSAL", "TREND"]
    if args.strategy.upper() == "ALL":
        strategies = all_strategies
    elif args.strategy.upper() in all_strategies:
        strategies = [args.strategy.upper()]
    else:
        print(f"❌ Estrategia inválida: {args.strategy}")
        sys.exit(1)

    df_h1 = get_historical_data(args.timeframe, args.months)
    df_d1 = get_d1_data()

    results = run_backtest(
        df_h1, df_d1, strategies,
        cooldown_bars=args.cooldown, tp1_only=args.tp1_only, ema_filter=args.ema_filter,
        session_filter=args.session, fix_lookahead=args.fix_lookahead, spread_cost=args.spread,
        rsi_oversold=args.rsi_oversold, rsi_overbought=args.rsi_overbought,
        proximity=args.proximity, enable_advanced=args.advanced,
        strict_session=args.strict_session, order_blocks=args.order_blocks,
        impulse_filter=args.impulse_filter, min_sr_touches=args.min_touches,
        supreme_mode=args.supreme,
    )

    print_report(
        results, args.timeframe, args.months, tp1_only=args.tp1_only,
        ema_filter=args.ema_filter, session_filter=args.session,
        fix_lookahead=args.fix_lookahead, enable_advanced=args.advanced,
        strict_session=args.strict_session, order_blocks=args.order_blocks,
        impulse_filter=args.impulse_filter, min_sr_touches=args.min_touches,
        supreme_mode=args.supreme,
    )

    if args.csv:
        suffix = f"_sl{int(_SL_DISTANCE)}_tp{int(args.tp1_distance)}"
        if args.tp1_only:
            suffix += "_tp1only"
        if ML_ENABLED:
            suffix += "_ml"
        if args.supreme:
            suffix += "_supreme"
        elif args.advanced:
            suffix += "_advanced"
        save_csv(results, filename=f"backtest_trades{suffix}.csv")

    mt5.shutdown()


if __name__ == "__main__":
    main()