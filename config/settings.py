# config/settings.py
"""
Configuración centralizada del bot con validación.

FASE C: Agrega MAX_OPEN_POSITIONS
FASE AUTONOMOUS: Agrega SCAN_INTERVAL
"""
from dataclasses import dataclass
from typing import Optional
import os


@dataclass(frozen=True)
class TelegramConfig:
    api_id: int
    api_hash: str
    session_name: str
    channel_id: int
    edit_reprocess_window_s: int = 180
    edit_reprocess_max_attempts: int = 3


@dataclass(frozen=True)
class MT5Config:
    login: int
    password: str
    server: str


@dataclass(frozen=True)
class TradingConfig:
    symbol: str
    volume_per_order: float
    deviation: int
    magic: int
    hard_drift: float
    max_splits: int
    pending_timeout_min: int
    buy_up_tol: float
    buy_down_tol: float
    sell_down_tol: float
    sell_up_tol: float
    extra_slippage: float = 0.10
    be_buffer: float = 0.0
    close_at_buffer: float = 0.0
    stop_extra_buffer: float = 0.0
    max_open_positions: int = 5       # 0 = sin límite
    scan_interval: int = 300          # segundos entre cada scan autónomo


@dataclass(frozen=True)
class AppConfig:
    use_real_account: bool
    dry_run: bool
    log_file: str
    telegram: TelegramConfig
    mt5: MT5Config
    trading: TradingConfig


def _create_demo_mt5_config() -> MT5Config:
    return MT5Config(login=1022962, password="", server="VTMarkets-Demo")


def _create_real_mt5_config() -> MT5Config:
    return MT5Config(login=77034995, password="real_pass", server="RoboForex-ECN")


def _create_demo_trading_config() -> TradingConfig:
    return TradingConfig(
        symbol="XAUUSD-ECN",
        volume_per_order=0.05,
        deviation=50,
        magic=6069104329,
        hard_drift=10.0,
        max_splits=10,
        pending_timeout_min=60,
        buy_up_tol=0.30,
        buy_down_tol=1.00,
        sell_down_tol=0.30,
        sell_up_tol=1.00,
        extra_slippage=0.10,
        be_buffer=0.0,
        max_open_positions=5,
        scan_interval=300,
    )


def _create_real_trading_config() -> TradingConfig:
    return TradingConfig(
        symbol="XAUUSD-ECN",
        volume_per_order=0.05,
        deviation=50,
        magic=6069104329,
        hard_drift=8.0,
        max_splits=4,
        pending_timeout_min=30,
        buy_up_tol=0.30,
        buy_down_tol=1.00,
        sell_down_tol=0.30,
        sell_up_tol=1.00,
        extra_slippage=0.10,
        be_buffer=0.0,
        max_open_positions=5,
        scan_interval=300,
    )


def _create_telegram_config() -> TelegramConfig:
    return TelegramConfig(
        api_id=32919258,
        api_hash="dfb662cee66fe7b2f337628eeac3316c",
        session_name="tg_session_qr",
        channel_id=2329472075,
        edit_reprocess_window_s=180,
        edit_reprocess_max_attempts=3,
    )


def create_app_config(use_real: Optional[bool] = None) -> AppConfig:
    if use_real is None:
        use_real = os.getenv("USE_REAL_ACCOUNT", "false").lower() == "true"
    return AppConfig(
        use_real_account=use_real,
        dry_run=os.getenv("DRY_RUN", "false").lower() == "true",
        log_file=os.getenv("LOG_FILE", "bot_events.jsonl"),
        telegram=_create_telegram_config(),
        mt5=_create_real_mt5_config() if use_real else _create_demo_mt5_config(),
        trading=_create_real_trading_config() if use_real else _create_demo_trading_config(),
    )


CONFIG = create_app_config(use_real=False)


def get_config() -> AppConfig:
    return CONFIG


def set_config(config: AppConfig) -> None:
    global CONFIG
    CONFIG = config


# =========================
# Backward compatibility
# =========================

USE_REAL_ACCOUNT = CONFIG.use_real_account
DRY_RUN = CONFIG.dry_run
LOG_FILE = CONFIG.log_file

API_ID = CONFIG.telegram.api_id
API_HASH = CONFIG.telegram.api_hash
SESSION_NAME = CONFIG.telegram.session_name
CHANNEL_ID = CONFIG.telegram.channel_id
TG_EDIT_REPROCESS_WINDOW_S = CONFIG.telegram.edit_reprocess_window_s
TG_EDIT_REPROCESS_MAX_ATTEMPTS = CONFIG.telegram.edit_reprocess_max_attempts

MT5_LOGIN = CONFIG.mt5.login
MT5_PASSWORD = CONFIG.mt5.password
MT5_SERVER = CONFIG.mt5.server

SYMBOL = CONFIG.trading.symbol
VOLUME_PER_ORDER = CONFIG.trading.volume_per_order
DEVIATION = CONFIG.trading.deviation
MAGIC = CONFIG.trading.magic
HARD_DRIFT = CONFIG.trading.hard_drift
MAX_SPLITS = CONFIG.trading.max_splits
PENDING_TIMEOUT_MIN = CONFIG.trading.pending_timeout_min
BUY_UP_TOL = CONFIG.trading.buy_up_tol
BUY_DOWN_TOL = CONFIG.trading.buy_down_tol
SELL_DOWN_TOL = CONFIG.trading.sell_down_tol
SELL_UP_TOL = CONFIG.trading.sell_up_tol
EXTRA_SLIPPAGE = CONFIG.trading.extra_slippage
BE_BUFFER = CONFIG.trading.be_buffer
MAX_OPEN_POSITIONS = CONFIG.trading.max_open_positions
SCAN_INTERVAL = CONFIG.trading.scan_interval