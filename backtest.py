# backtest.py
"""
Backtester para las estrategias del bot autónomo.

Usa las mismas clases de estrategia del bot (BreakoutStrategy,
ReversalStrategy, TrendStrategy, MomentumStrategy) pero les pasa
datos históricos en vez de datos live.

Uso:
    python backtest.py                        # últimos 3 meses H1
    python backtest.py --months 6             # últimos 6 meses
    python backtest.py --strategy REVERSAL    # solo una estrategia
    python backtest.py --timeframe H4         # otro timeframe

Requiere MT5 corriendo y conectado.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

import MetaTrader5 as mt5
import numpy as np
import pandas as pd

# ── Config básica (sin importar todo el proyecto) ──
SYMBOL       = "XAUUSD-ECN"
MAGIC        = 6069104329
VOLUME       = 0.05

# Defaults — sobreescritos por --sl-distance y --tp1-distance
_SL_DISTANCE  = 6.0
_TP_DISTANCES = (5.0, 11.0, 16.0)


# ══════════════════════════════════════════════════
# MODELOS
# ══════════════════════════════════════════════════

@dataclass
class BacktestTrade:
    strategy:    str
    side:        str
    entry:       float
    sl:          float
    tp1:         float
    tp2:         float
    tp3:         float
    entry_time:  pd.Timestamp
    exit_time:   Optional[pd.Timestamp] = None
    exit_price:  Optional[float] = None
    result:      str = "OPEN"      # TP1 / TP2 / TP3 / SL / OPEN
    pnl:         float = 0.0       # en dólares (0.05 lot)


@dataclass
class BacktestResult:
    strategy:    str
    trades:      List[BacktestTrade] = field(default_factory=list)

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


# ══════════════════════════════════════════════════
# CONEXIÓN MT5
# ══════════════════════════════════════════════════

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
    print(f"✅ MT5 conectado — {SYMBOL}")
    return True


def get_historical_data(timeframe_str: str, months: int) -> pd.DataFrame:
    """Descarga datos históricos de MT5."""
    tf_map = {
        "M1":  mt5.TIMEFRAME_M1,
        "M5":  mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "H1":  mt5.TIMEFRAME_H1,
        "H4":  mt5.TIMEFRAME_H4,
        "D1":  mt5.TIMEFRAME_D1,
    }
    tf = tf_map.get(timeframe_str.upper())
    if tf is None:
        print(f"❌ Timeframe inválido: {timeframe_str}")
        sys.exit(1)

    # Calcular cuántas velas necesitamos
    candles_per_month = {
        "M1": 43200, "M5": 8640, "M15": 2880,
        "H1": 720,   "H4": 180,  "D1": 22,
    }
    count = candles_per_month.get(timeframe_str.upper(), 720) * months + 300

    rates = mt5.copy_rates_from_pos(SYMBOL, tf, 0, count)
    if rates is None or len(rates) == 0:
        print("❌ No se pudieron obtener datos históricos")
        sys.exit(1)

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df.set_index("time", inplace=True)
    print(f"✅ {len(df)} velas descargadas ({timeframe_str}) — "
          f"{df.index[0].strftime('%Y-%m-%d')} → {df.index[-1].strftime('%Y-%m-%d')}")
    return df


def get_d1_data() -> pd.DataFrame:
    """Descarga velas D1 para BreakoutStrategy."""
    rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_D1, 0, 400)
    if rates is None:
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df.set_index("time", inplace=True)
    return df


# ══════════════════════════════════════════════════
# SIMULACIÓN DE ESTRATEGIAS
# (réplica directa sin importar el proyecto)
# ══════════════════════════════════════════════════

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
    import numpy as np
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


# ── Breakout ──
def scan_breakout(
    df_h1: pd.DataFrame,
    df_d1: pd.DataFrame,
    i: int,
) -> Optional[BacktestTrade]:
    """Simula BreakoutStrategy en la vela i."""
    if i < 30:
        return None

    window = df_h1.iloc[max(0, i - 100):i + 1].copy()
    current_price = float(window["close"].iloc[-1])
    ts = window.index[-1]

    atr_val = float(atr_fn(window).iloc[-1])
    if pd.isna(atr_val) or atr_val <= 0:
        return None

    # High/Low del día anterior desde D1
    d1_before = df_d1[df_d1.index < ts]
    if len(d1_before) < 2:
        return None
    prev_day = d1_before.iloc[-1]
    daily_high = float(prev_day["high"])
    daily_low  = float(prev_day["low"])

    # EMA 50/200
    if len(window) >= 201:
        ema50  = float(ema_fn(window["close"], 50).iloc[-1])
        ema200 = float(ema_fn(window["close"], 200).iloc[-1])
        ema_bull = ema50 > ema200
    else:
        ema_bull = None  # sin datos, no filtrar

    breakout_buffer = 2.0
    max_chase = 1.0 * atr_val
    fresh_candles = 4

    # SELL BREAKOUT
    sell_level = daily_low - breakout_buffer
    if current_price < sell_level:
        if (sell_level - current_price) <= max_chase:
            # Frescura: buscar vela de ruptura en las últimas fresh_candles
            broke = False
            for k in range(1, fresh_candles + 2):
                if i - k < 0:
                    break
                if float(df_h1["close"].iloc[i - k]) < daily_low:
                    broke = True
                    break
            if broke:
                entry = round(daily_low, 2)
                sl = calc_sl("SELL", entry)
                tp1, tp2, tp3 = calc_tps("SELL", entry)
                return BacktestTrade(
                    strategy="BREAKOUT", side="SELL",
                    entry=entry, sl=sl, tp1=tp1, tp2=tp2, tp3=tp3,
                    entry_time=ts,
                )

    # BUY BREAKOUT
    buy_level = daily_high + breakout_buffer
    if current_price > buy_level:
        if (current_price - buy_level) <= max_chase:
            broke = False
            for k in range(1, fresh_candles + 2):
                if i - k < 0:
                    break
                if float(df_h1["close"].iloc[i - k]) > daily_high:
                    broke = True
                    break
            if broke:
                entry = round(daily_high, 2)
                sl = calc_sl("BUY", entry)
                tp1, tp2, tp3 = calc_tps("BUY", entry)
                return BacktestTrade(
                    strategy="BREAKOUT", side="BUY",
                    entry=entry, sl=sl, tp1=tp1, tp2=tp2, tp3=tp3,
                    entry_time=ts,
                )
    return None


# ── Reversal ──
def scan_reversal(df_h1: pd.DataFrame, i: int) -> Optional[BacktestTrade]:
    if i < 30:
        return None

    window = df_h1.iloc[max(0, i - 100):i + 1].copy()
    current_price = float(window["close"].iloc[-1])
    ts = window.index[-1]

    levels = support_resistance(window, lookback=20)
    if not levels:
        return None

    current_rsi = float(rsi_fn(window["close"]).iloc[-1])
    atr_val = float(atr_fn(window).iloc[-1])
    if pd.isna(atr_val) or atr_val <= 0:
        return None

    proximity = 8.0
    closest = min(levels, key=lambda l: abs(l - current_price))
    if abs(current_price - closest) > proximity:
        return None

    if current_price <= closest and current_rsi < 45.0:
        entry = round(current_price, 2)
        sl = calc_sl("BUY", entry)
        tp1, tp2, tp3 = calc_tps("BUY", entry)
        return BacktestTrade(
            strategy="REVERSAL", side="BUY",
            entry=entry, sl=sl, tp1=tp1, tp2=tp2, tp3=tp3,
            entry_time=ts,
        )

    if current_price >= closest and current_rsi > 55.0:
        entry = round(current_price, 2)
        sl = calc_sl("SELL", entry)
        tp1, tp2, tp3 = calc_tps("SELL", entry)
        return BacktestTrade(
            strategy="REVERSAL", side="SELL",
            entry=entry, sl=sl, tp1=tp1, tp2=tp2, tp3=tp3,
            entry_time=ts,
        )
    return None


# ── Trend ──
def scan_trend(df_h1: pd.DataFrame, i: int) -> Optional[BacktestTrade]:
    if i < 55:
        return None

    window = df_h1.iloc[max(0, i - 100):i + 1].copy()
    current_price = float(window["close"].iloc[-1])
    ts = window.index[-1]

    sma20 = float(sma(window["close"], 20).iloc[-1])
    sma50 = float(sma(window["close"], 50).iloc[-1])

    if pd.isna(sma20) or pd.isna(sma50):
        return None

    atr_val = float(atr_fn(window).iloc[-1])
    if pd.isna(atr_val) or atr_val <= 0:
        return None

    proximity = 2.0
    if abs(current_price - sma20) > proximity:
        return None

    if sma20 > sma50 and current_price >= sma20:
        entry = round(current_price, 2)
        sl = calc_sl("BUY", entry)
        tp1, tp2, tp3 = calc_tps("BUY", entry)
        return BacktestTrade(
            strategy="TREND", side="BUY",
            entry=entry, sl=sl, tp1=tp1, tp2=tp2, tp3=tp3,
            entry_time=ts,
        )

    if sma20 < sma50 and current_price <= sma20:
        entry = round(current_price, 2)
        sl = calc_sl("SELL", entry)
        tp1, tp2, tp3 = calc_tps("SELL", entry)
        return BacktestTrade(
            strategy="TREND", side="SELL",
            entry=entry, sl=sl, tp1=tp1, tp2=tp2, tp3=tp3,
            entry_time=ts,
        )
    return None


# ══════════════════════════════════════════════════
# SIMULACIÓN DE SALIDAS (SL/TP hit)
# ══════════════════════════════════════════════════

PNL_PER_DOLLAR = 0.05  # 0.05 lot × $1 = $0.05 por pip en XAUUSD mini

def simulate_exit(
    trade: BacktestTrade,
    df: pd.DataFrame,
    entry_i: int,
    tp1_only: bool = False,
) -> BacktestTrade:
    """
    Recorre las velas siguientes buscando cuál se toca primero: SL o TP.
    Usa el high/low de cada vela para detectar el toque.
    Máximo 200 velas hacia adelante (~200 horas en H1).

    tp1_only=True: ignora TP2/TP3, cierra todo en TP1.
    """
    max_bars = min(entry_i + 201, len(df))
    sl_pnl  = round(-(_SL_DISTANCE * 10 * PNL_PER_DOLLAR), 2)
    tp1_pnl = round(_TP_DISTANCES[0] * 10 * PNL_PER_DOLLAR, 2)
    tp2_pnl = round(_TP_DISTANCES[1] * 10 * PNL_PER_DOLLAR, 2)
    tp3_pnl = round(_TP_DISTANCES[2] * 10 * PNL_PER_DOLLAR, 2)

    for j in range(entry_i + 1, max_bars):
        candle = df.iloc[j]
        high = float(candle["high"])
        low  = float(candle["low"])

        if trade.side == "BUY":
            if low <= trade.sl:
                trade.exit_time  = df.index[j]
                trade.exit_price = trade.sl
                trade.result     = "SL"
                trade.pnl        = sl_pnl
                return trade
            if not tp1_only and high >= trade.tp3:
                trade.exit_time  = df.index[j]
                trade.exit_price = trade.tp3
                trade.result     = "TP3"
                trade.pnl        = tp3_pnl
                return trade
            if not tp1_only and high >= trade.tp2:
                trade.exit_time  = df.index[j]
                trade.exit_price = trade.tp2
                trade.result     = "TP2"
                trade.pnl        = tp2_pnl
                return trade
            if high >= trade.tp1:
                trade.exit_time  = df.index[j]
                trade.exit_price = trade.tp1
                trade.result     = "TP1"
                trade.pnl        = tp1_pnl
                return trade
        else:  # SELL
            if high >= trade.sl:
                trade.exit_time  = df.index[j]
                trade.exit_price = trade.sl
                trade.result     = "SL"
                trade.pnl        = sl_pnl
                return trade
            if not tp1_only and low <= trade.tp3:
                trade.exit_time  = df.index[j]
                trade.exit_price = trade.tp3
                trade.result     = "TP3"
                trade.pnl        = tp3_pnl
                return trade
            if not tp1_only and low <= trade.tp2:
                trade.exit_time  = df.index[j]
                trade.exit_price = trade.tp2
                trade.result     = "TP2"
                trade.pnl        = tp2_pnl
                return trade
            if low <= trade.tp1:
                trade.exit_time  = df.index[j]
                trade.exit_price = trade.tp1
                trade.result     = "TP1"
                trade.pnl        = tp1_pnl
                return trade

    return trade


# ══════════════════════════════════════════════════
# MOTOR PRINCIPAL DE BACKTESTING
# ══════════════════════════════════════════════════

def run_backtest(
    df_h1: pd.DataFrame,
    df_d1: pd.DataFrame,
    strategies: List[str],
    cooldown_bars: int = 3,
    tp1_only: bool = False,
) -> List[BacktestResult]:
    """
    Recorre las velas una por una simulando el bot.

    cooldown_bars: velas de cooldown entre señales de la misma estrategia
    tp1_only: si True, cierra todo en TP1 (ignora TP2/TP3)
    """
    results = {s: BacktestResult(strategy=s) for s in strategies}
    last_signal_bar = {s: -cooldown_bars for s in strategies}

    mode_label = "TP1 ONLY" if tp1_only else "TP1/TP2/TP3"
    total = len(df_h1)
    print(f"\n⏳ Procesando {total} velas... [{mode_label}]")

    for i in range(200, total - 1):
        if i % 500 == 0:
            pct = i / total * 100
            print(f"   {pct:.0f}% — vela {i}/{total}", end="\r")

        for strategy in strategies:
            if i - last_signal_bar[strategy] < cooldown_bars:
                continue

            trade = None

            if strategy == "BREAKOUT":
                trade = scan_breakout(df_h1, df_d1, i)
            elif strategy == "REVERSAL":
                trade = scan_reversal(df_h1, i)
            elif strategy == "TREND":
                trade = scan_trend(df_h1, i)

            if trade is not None:
                trade = simulate_exit(trade, df_h1, i, tp1_only=tp1_only)
                results[strategy].trades.append(trade)
                last_signal_bar[strategy] = i

    print(f"   100% — {total} velas procesadas ✅")
    return list(results.values())


# ══════════════════════════════════════════════════
# REPORTE
# ══════════════════════════════════════════════════

def print_report(results: List[BacktestResult], timeframe: str, months: int, tp1_only: bool = False) -> None:
    mode = "TP1 ONLY" if tp1_only else "TP1/TP2/TP3"
    print("\n" + "═" * 60)
    print(f"  BACKTEST REPORT — {SYMBOL} {timeframe} ({months} meses) [{mode}]")
    print(f"  SL=${_SL_DISTANCE} | TP={_TP_DISTANCES} | RR={_TP_DISTANCES[0]/_SL_DISTANCE:.2f}:1")
    print("═" * 60)

    grand_trades = 0
    grand_wins   = 0
    grand_pnl    = 0.0

    for r in results:
        if r.total == 0:
            print(f"\n{'─'*60}")
            print(f"  {r.strategy}: 0 trades cerrados")
            continue

        tp1 = len([t for t in r.trades if t.result == "TP1"])
        tp2 = len([t for t in r.trades if t.result == "TP2"])
        tp3 = len([t for t in r.trades if t.result == "TP3"])
        sl  = r.losses
        opn = len([t for t in r.trades if t.result == "OPEN"])

        buys  = len([t for t in r.trades if t.side == "BUY"  and t.result != "OPEN"])
        sells = len([t for t in r.trades if t.side == "SELL" and t.result != "OPEN"])
        buy_wr  = len([t for t in r.trades if t.side == "BUY"  and t.result.startswith("TP")])
        sell_wr = len([t for t in r.trades if t.side == "SELL" and t.result.startswith("TP")])

        print(f"\n{'─'*60}")
        print(f"  📊 {r.strategy}")
        print(f"{'─'*60}")
        print(f"  Trades cerrados : {r.total:>4}  (OPEN pendientes: {opn})")
        print(f"  Win Rate        : {r.win_rate:>5.1f}%  ({r.wins}W / {r.losses}L)")
        print(f"  TP1 / TP2 / TP3 : {tp1} / {tp2} / {tp3}")
        print(f"  SL hits         : {sl}")
        print(f"  BUY  win rate   : {buy_wr}/{buys} = {buy_wr/buys*100:.1f}%" if buys else "  BUY             : sin trades")
        print(f"  SELL win rate   : {sell_wr}/{sells} = {sell_wr/sells*100:.1f}%" if sells else "  SELL            : sin trades")
        print(f"  P&L total       : ${r.total_pnl:>+.2f}")
        print(f"  P&L promedio    : ${r.avg_pnl:>+.2f} por trade")

        grand_trades += r.total
        grand_wins   += r.wins
        grand_pnl    += r.total_pnl

    print(f"\n{'═'*60}")
    print(f"  TOTAL COMBINADO")
    print(f"{'─'*60}")
    grand_wr = (grand_wins / grand_trades * 100) if grand_trades > 0 else 0
    print(f"  Trades  : {grand_trades}")
    print(f"  Win Rate: {grand_wr:.1f}%")
    print(f"  P&L     : ${grand_pnl:+.2f}")
    print("═" * 60 + "\n")


def save_csv(results: List[BacktestResult], filename: str = "backtest_trades.csv") -> None:
    """Guarda todos los trades en CSV para análisis posterior."""
    rows = []
    for r in results:
        for t in r.trades:
            rows.append({
                "strategy":   t.strategy,
                "side":       t.side,
                "entry_time": t.entry_time,
                "exit_time":  t.exit_time,
                "entry":      t.entry,
                "sl":         t.sl,
                "tp1":        t.tp1,
                "tp2":        t.tp2,
                "tp3":        t.tp3,
                "exit_price": t.exit_price,
                "result":     t.result,
                "pnl":        t.pnl,
            })
    if rows:
        df = pd.DataFrame(rows)
        df.to_csv(filename, index=False)
        print(f"💾 Trades guardados en {filename}")


# ══════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Backtester del bot autónomo")
    parser.add_argument("--months",       type=int,   default=3,
                        help="Meses de historia (default: 3)")
    parser.add_argument("--timeframe",    type=str,   default="H1",
                        help="Timeframe H1/H4/M15 (default: H1)")
    parser.add_argument("--strategy",     type=str,   default="ALL",
                        help="BREAKOUT/REVERSAL/TREND/ALL (default: ALL)")
    parser.add_argument("--cooldown",     type=int,   default=3,
                        help="Velas de cooldown entre señales (default: 3)")
    parser.add_argument("--tp1-only",     action="store_true",
                        help="Cerrar todo en TP1, ignorar TP2/TP3")
    parser.add_argument("--sl-distance",  type=float, default=6.0,
                        help="Distancia del SL en dólares (default: 6.0)")
    parser.add_argument("--tp1-distance", type=float, default=5.0,
                        help="Distancia del TP1 en dólares (default: 5.0)")
    parser.add_argument("--csv",          action="store_true",
                        help="Guardar trades en CSV")
    args = parser.parse_args()

    # Aplicar SL/TP a las variables globales
    global _SL_DISTANCE, _TP_DISTANCES
    _SL_DISTANCE  = args.sl_distance
    tp1 = args.tp1_distance
    # TP2 y TP3 escalan proporcionalmente al cambio de TP1
    # Base original: TP1=5, TP2=11, TP3=16
    # Ratio: TP2 = TP1×2.2, TP3 = TP1×3.2
    tp2 = round(tp1 * 2.2, 1)
    tp3 = round(tp1 * 3.2, 1)
    _TP_DISTANCES = (tp1, tp2, tp3)

    print(f"⚙️  Config: SL=${_SL_DISTANCE} | TP1=${tp1} TP2=${tp2} TP3=${tp3} "
          f"| RR={tp1/_SL_DISTANCE:.2f}:1")

    # Conectar MT5
    if not connect_mt5():
        sys.exit(1)

    # Determinar estrategias
    all_strategies = ["BREAKOUT", "REVERSAL", "TREND"]
    if args.strategy.upper() == "ALL":
        strategies = all_strategies
    elif args.strategy.upper() in all_strategies:
        strategies = [args.strategy.upper()]
    else:
        print(f"❌ Estrategia inválida: {args.strategy}")
        sys.exit(1)

    tp1_only = args.tp1_only

    # Descargar datos
    df_h1 = get_historical_data(args.timeframe, args.months)
    df_d1 = get_d1_data()

    # Correr backtest
    results = run_backtest(df_h1, df_d1, strategies, cooldown_bars=args.cooldown, tp1_only=tp1_only)

    # Mostrar reporte
    print_report(results, args.timeframe, args.months, tp1_only=tp1_only)

    # Guardar CSV si se pidió
    if args.csv:
        suffix = f"_sl{int(_SL_DISTANCE)}_tp{int(args.tp1_distance)}"
        if tp1_only:
            suffix += "_tp1only"
        save_csv(results, filename=f"backtest_trades{suffix}.csv")

    mt5.shutdown()


if __name__ == "__main__":
    main()