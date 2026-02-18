# backtest.py
"""
Backtester - Usa las clases de estrategia directamente.

MODOS DE OPERACIÓN:
===================
1. Normal  : python backtest.py --months 12 --strategy REVERSAL --csv
2. Advanced: python backtest.py --months 12 --strategy REVERSAL --advanced --csv
3. Supreme : python backtest.py --months 12 --strategy REVERSAL --supreme --csv

Nota: Todos los modos usan las clases ReversalStrategy / TrendStrategy directamente,
garantizando que el backtest prueba exactamente lo que corre en producción.
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

try:
    from ml.feature_extractor import extract_features
    ML_ENABLED = True
    print("ML Feature Extractor cargado")
except ImportError:
    ML_ENABLED = False
    print("ML Feature Extractor NO disponible")

try:
    from market.strategies.reversal import ReversalStrategy
    from market.strategies.trend import TrendStrategy
    STRATEGIES_AVAILABLE = True
except ImportError as e:
    STRATEGIES_AVAILABLE = False
    print(f"Error importando estrategias: {e}")

try:
    from market.indicators import support_resistance_levels
except ImportError:
    support_resistance_levels = None

# Config
SYMBOL = "XAUUSD-ECN"
MAGIC = 6069104329

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
        print("Error: No se pudo inicializar MT5")
        return False
    if not mt5.login(1022962, password="", server="VTMarkets-Demo"):
        print("Error: Login MT5 fallo")
        mt5.shutdown()
        return False
    if not mt5.symbol_select(SYMBOL, True):
        print(f"Error: No se pudo seleccionar {SYMBOL}")
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
        print(f"Error: Timeframe invalido: {timeframe_str}")
        sys.exit(1)

    candles_per_month = {
        "M1": 43200, "M5": 8640, "M15": 2880,
        "H1": 720, "H4": 180, "D1": 22,
    }
    count = candles_per_month.get(timeframe_str.upper(), 720) * months + 300

    rates = mt5.copy_rates_from_pos(SYMBOL, tf, 0, count)
    if rates is None or len(rates) == 0:
        print("Error: No se pudieron obtener datos historicos")
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
# HELPERS
# ==================================================

def _signal_to_trade(signal, strategy_name: str, ts: pd.Timestamp) -> BacktestTrade:
    """Convierte un Signal de estrategia a BacktestTrade."""
    return BacktestTrade(
        strategy=strategy_name,
        side=signal.side,
        entry=signal.entry,
        sl=signal.sl,
        tp1=signal.tps[0],
        tp2=signal.tps[1],
        tp3=signal.tps[2],
        entry_time=ts,
    )


def _attach_ml_features(trade: BacktestTrade, window: pd.DataFrame, side: str, **kwargs):
    """Adjunta features ML al trade si ML está habilitado."""
    if not ML_ENABLED:
        return
    try:
        features = extract_features(df=window, signal_side=side, **kwargs)
        for key, value in features.items():
            setattr(trade, key, value)
    except Exception:
        pass


def _get_sr_level(window: pd.DataFrame, current_price: float) -> Optional[float]:
    """Obtiene el nivel S/R más cercano."""
    if support_resistance_levels is None:
        return None
    try:
        levels = support_resistance_levels(window, lookback=20)
        return min(levels, key=lambda l: abs(l - current_price)) if levels else None
    except Exception:
        return None


# ==================================================
# EXIT SIMULATION
# ==================================================

PNL_PER_DOLLAR = 0.05


def simulate_exit(trade: BacktestTrade, df: pd.DataFrame, entry_i: int,
                  tp1_only: bool = False, spread_cost: float = 0.0) -> BacktestTrade:
    max_bars = min(entry_i + 201, len(df))
    sl_pnl  = round(-(_SL_DISTANCE * 10 * PNL_PER_DOLLAR) - spread_cost, 2)
    tp1_pnl = round(_TP_DISTANCES[0] * 10 * PNL_PER_DOLLAR - spread_cost, 2)
    tp2_pnl = round(_TP_DISTANCES[1] * 10 * PNL_PER_DOLLAR - spread_cost, 2)
    tp3_pnl = round(_TP_DISTANCES[2] * 10 * PNL_PER_DOLLAR - spread_cost, 2)

    for j in range(entry_i + 1, max_bars):
        candle = df.iloc[j]
        high = float(candle["high"])
        low  = float(candle["low"])

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
# STRATEGY FACTORY
# ==================================================

def _build_reversal_strategy(supreme_mode: bool, rsi_oversold: float,
                              rsi_overbought: float, proximity: float,
                              enable_advanced: bool, strict_session: bool,
                              order_blocks: bool, impulse_filter: bool,
                              min_sr_touches: int) -> ReversalStrategy:
    """Construye ReversalStrategy con los parámetros correctos según el modo."""
    if supreme_mode:
        return ReversalStrategy(
            symbol=SYMBOL,
            magic=MAGIC,
            supreme_mode=True,
            rsi_oversold=rsi_oversold,
            rsi_overbought=rsi_overbought,
            proximity_pips=proximity,
        )

    # Modo normal / advanced — mapear flags a parámetros de la clase
    return ReversalStrategy(
        symbol=SYMBOL,
        magic=MAGIC,
        supreme_mode=False,
        rsi_oversold=rsi_oversold,
        rsi_overbought=rsi_overbought,
        proximity_pips=proximity,
        enable_strict_session=strict_session or enable_advanced,
        enable_order_blocks=order_blocks or enable_advanced,
        enable_fvg=enable_advanced,
        enable_quality_filter=enable_advanced or min_sr_touches > 2,
        min_sr_touches=min_sr_touches,
        impulse_multiplier=1.5 if (impulse_filter or enable_advanced) else 999.0,
    )


def _build_trend_strategy(session_filter: str, ema_filter: bool) -> TrendStrategy:
    """Construye TrendStrategy con los parámetros correctos."""
    return TrendStrategy(
        symbol=SYMBOL,
        magic=MAGIC,
        enable_filters=True,
    )


# ==================================================
# MAIN BACKTEST LOOP
# ==================================================

def run_backtest(
    df_h1: pd.DataFrame,
    df_d1: pd.DataFrame,
    strategies: List[str],
    cooldown_bars: int = 3,
    tp1_only: bool = False,
    ema_filter: bool = False,
    session_filter: str = "24h",
    fix_lookahead: bool = False,
    spread_cost: float = 0.0,
    rsi_oversold: float = 45.0,
    rsi_overbought: float = 55.0,
    proximity: float = 8.0,
    enable_advanced: bool = False,
    strict_session: bool = False,
    order_blocks: bool = False,
    impulse_filter: bool = False,
    min_sr_touches: int = 2,
    supreme_mode: bool = False,
) -> List[BacktestResult]:

    if not STRATEGIES_AVAILABLE:
        print("Error: No se pudieron cargar las estrategias")
        return []

    results_map = {s: BacktestResult(strategy=s) for s in strategies}
    last_trade_i = -999

    # Instanciar estrategias una sola vez
    reversal_strategy = None
    trend_strategy = None

    if "REVERSAL" in strategies:
        reversal_strategy = _build_reversal_strategy(
            supreme_mode, rsi_oversold, rsi_overbought, proximity,
            enable_advanced, strict_session, order_blocks, impulse_filter, min_sr_touches,
        )
        mode_label = "SUPREME" if supreme_mode else ("ADVANCED" if enable_advanced else "NORMAL")
        print(f"ReversalStrategy lista - modo: {mode_label}")

    if "TREND" in strategies:
        trend_strategy = _build_trend_strategy(session_filter, ema_filter)
        print("TrendStrategy lista")

    # Loop principal
    for i in range(len(df_h1)):
        if i - last_trade_i < cooldown_bars:
            continue

        trade = None
        strategy_name = None

        # --- REVERSAL ---
        if reversal_strategy and i >= 30:
            window = df_h1.iloc[max(0, i - 250):i + 1].copy()
            current_price = float(window["close"].iloc[-1])
            ts = window.index[-1]

            signal = reversal_strategy.scan(df=window, current_price=current_price)

            if signal:
                label = "REVERSAL_SUPREME" if supreme_mode else "REVERSAL"
                trade = _signal_to_trade(signal, label, ts)
                strategy_name = "REVERSAL"

                if ML_ENABLED:
                    sr_level = _get_sr_level(window, current_price)
                    _attach_ml_features(trade, window, signal.side,
                                        sr_level=sr_level)

        # --- TREND ---
        if trade is None and trend_strategy and i >= 55:
            window = df_h1.iloc[max(0, i - 100):i + 1].copy()
            current_price = float(window["close"].iloc[-1])
            ts = window.index[-1]

            signal = trend_strategy.scan(df=window, current_price=current_price)

            if signal:
                trade = _signal_to_trade(signal, "TREND", ts)
                strategy_name = "TREND"

                if ML_ENABLED:
                    _attach_ml_features(trade, window, signal.side,
                                        sma_fast=signal.entry,
                                        sma_slow=signal.entry)

        # --- SIMULATE EXIT ---
        if trade and strategy_name:
            entry_index = i + 1 if fix_lookahead else i
            if entry_index >= len(df_h1):
                continue

            closed = simulate_exit(trade, df_h1, entry_index,
                                   tp1_only=tp1_only, spread_cost=spread_cost)
            results_map[strategy_name].trades.append(closed)
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
    print(f"  TP1-only        : {'SI' if tp1_only else 'NO'}")
    print(f"  EMA filter      : {'SI' if ema_filter else 'NO'}")
    print(f"  Session filter  : {session_filter.upper()}")
    print(f"  Fix lookahead   : {'SI' if fix_lookahead else 'NO'}")

    if supreme_mode:
        print(f"  {'---SUPREME MODE---':^58}")
        print(f"  SUPREME MODE    : ACTIVADO (FVG + OB + MTF + Quality)")
    elif enable_advanced or strict_session or order_blocks or impulse_filter or min_sr_touches > 2:
        print(f"  {'---ADVANCED FILTERS---':^58}")
        if enable_advanced:
            print(f"  All advanced    : SI (session+OB+impulse+volume+quality)")
        else:
            if strict_session:
                print(f"  Strict session  : SI (London/NY open only)")
            if order_blocks:
                print(f"  Order Blocks    : SI")
            if impulse_filter:
                print(f"  Impulse filter  : SI (>1.5x ATR)")
            if min_sr_touches > 2:
                print(f"  S/R quality     : SI (min {min_sr_touches} touches)")

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

        buys  = [t for t in r.trades if t.side == "BUY"  and t.result != "OPEN"]
        sells = [t for t in r.trades if t.side == "SELL" and t.result != "OPEN"]
        buy_wins  = len([t for t in buys  if t.result.startswith("TP")])
        sell_wins = len([t for t in sells if t.result.startswith("TP")])

        if buys:
            print(f"  BUY win rate    : {buy_wins}/{len(buys)} = {buy_wins/len(buys)*100:.1f}%")
        if sells:
            print(f"  SELL win rate   : {sell_wins}/{len(sells)} = {sell_wins/len(sells)*100:.1f}%")

        print(f"  P&L total       : ${r.total_pnl:>+.2f}")
        print(f"  P&L promedio    : ${r.avg_pnl:>+.2f} por trade")

        grand_trades += r.total
        grand_wins   += r.wins
        grand_pnl    += r.total_pnl

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
                    if not attr_name.startswith("_") and attr_name not in row:
                        attr_value = getattr(t, attr_name, None)
                        if isinstance(attr_value, (int, float)):
                            row[attr_name] = attr_value
            rows.append(row)

    if rows:
        df = pd.DataFrame(rows)
        df.to_csv(filename, index=False)
        print(f"Trades guardados en {filename}")
        print(f"   Total trades: {len(df)}")


# ==================================================
# MAIN
# ==================================================

def main():
    parser = argparse.ArgumentParser(description="Backtester")
    parser.add_argument("--months",        type=int,   default=3)
    parser.add_argument("--timeframe",     type=str,   default="H1")
    parser.add_argument("--strategy",      type=str,   default="ALL")
    parser.add_argument("--cooldown",      type=int,   default=3)
    parser.add_argument("--tp1-only",      action="store_true")
    parser.add_argument("--ema-filter",    action="store_true")
    parser.add_argument("--session",       type=str,   default="24h",
                        choices=["24h", "eu_ny", "ny_only"])
    parser.add_argument("--fix-lookahead", action="store_true")
    parser.add_argument("--spread",        type=float, default=0.30)
    parser.add_argument("--rsi-oversold",  type=float, default=45.0)
    parser.add_argument("--rsi-overbought",type=float, default=55.0)
    parser.add_argument("--proximity",     type=float, default=8.0)
    parser.add_argument("--sl-distance",   type=float, default=6.0)
    parser.add_argument("--tp1-distance",  type=float, default=5.0)
    parser.add_argument("--csv",           action="store_true")
    parser.add_argument("--advanced",      action="store_true",
                        help="Enable ALL advanced filters")
    parser.add_argument("--supreme",       action="store_true",
                        help="Supreme mode (FVG + OB + MTF + Quality)")
    parser.add_argument("--strict-session",action="store_true",
                        help="Only London/NY open")
    parser.add_argument("--order-blocks",  action="store_true",
                        help="Enable Order Blocks")
    parser.add_argument("--impulse-filter",action="store_true",
                        help="Require impulse >1.5x ATR")
    parser.add_argument("--min-touches",   type=int,   default=2,
                        help="Min S/R touches")

    args = parser.parse_args()

    global _SL_DISTANCE, _TP_DISTANCES
    _SL_DISTANCE = args.sl_distance
    tp1 = args.tp1_distance
    tp2 = round(tp1 * 2.2, 1)
    tp3 = round(tp1 * 3.2, 1)
    _TP_DISTANCES = (tp1, tp2, tp3)

    print(f"Config: SL=${_SL_DISTANCE} | TP1=${tp1} TP2=${tp2} TP3=${tp3} | "
          f"RR={tp1/_SL_DISTANCE:.2f}:1")

    if not connect_mt5():
        sys.exit(1)

    all_strategies = ["REVERSAL", "TREND"]
    if args.strategy.upper() == "ALL":
        strategies = all_strategies
    elif args.strategy.upper() in all_strategies:
        strategies = [args.strategy.upper()]
    else:
        print(f"Error: Estrategia invalida: {args.strategy}")
        sys.exit(1)

    df_h1 = get_historical_data(args.timeframe, args.months)
    df_d1 = get_d1_data()

    results = run_backtest(
        df_h1, df_d1, strategies,
        cooldown_bars=args.cooldown,
        tp1_only=args.tp1_only,
        ema_filter=args.ema_filter,
        session_filter=args.session,
        fix_lookahead=args.fix_lookahead,
        spread_cost=args.spread,
        rsi_oversold=args.rsi_oversold,
        rsi_overbought=args.rsi_overbought,
        proximity=args.proximity,
        enable_advanced=args.advanced,
        strict_session=args.strict_session,
        order_blocks=args.order_blocks,
        impulse_filter=args.impulse_filter,
        min_sr_touches=args.min_touches,
        supreme_mode=args.supreme,
    )

    print_report(
        results, args.timeframe, args.months,
        tp1_only=args.tp1_only,
        ema_filter=args.ema_filter,
        session_filter=args.session,
        fix_lookahead=args.fix_lookahead,
        enable_advanced=args.advanced,
        strict_session=args.strict_session,
        order_blocks=args.order_blocks,
        impulse_filter=args.impulse_filter,
        min_sr_touches=args.min_touches,
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