# =========================
# Environment switch
# =========================
USE_REAL_ACCOUNT = False   # True = real | False = demo

# Telegram API credentials
API_ID = 32919258
API_HASH = "dfb662cee66fe7b2f337628eeac3316c"
SESSION_NAME = "tg_session_qr"
CHANNEL_ID = 2329472075  # channel/chat id (int)

if USE_REAL_ACCOUNT:
    # REAL
    MT5_LOGIN = 77034995
    MT5_PASSWORD = "real_pass"
    MT5_SERVER = "RoboForex-ECN"

    HARD_DRIFT = 8.0
    MAX_SPLITS = 4
    PENDING_TIMEOUT_MIN = 30
else:
    # DEMO
    MT5_LOGIN = 1022962
    MT5_PASSWORD = ""
    MT5_SERVER = "VTMarkets-Demo"

    HARD_DRIFT = 10.0
    MAX_SPLITS = 10
    PENDING_TIMEOUT_MIN = 60

# Trading settings
SYMBOL = "XAUUSD-ECN"
VOLUME_PER_ORDER = 0.05
DEVIATION = 50
MAGIC = 6069104329  # ideally TG user_id

# Execution drift policy
# XAUUSD-ECN usually 2 digits => 0.30 == $0.30
BUY_UP_TOL = 0.30
BUY_DOWN_TOL = 1.00
SELL_DOWN_TOL = 0.30
SELL_UP_TOL = 1.00


# Optional extra cushion (available if you want to use it in rules.py)
EXTRA_SLIPPAGE = 0.10

# Break-even buffer
BE_BUFFER = 0.0

# =========================
# Telegram edit handling
# =========================

# Typos / quick edits
TG_EDIT_REPROCESS_WINDOW_S = 180
TG_EDIT_REPROCESS_MAX_ATTEMPTS = 3

# =========================
# Logging
# =========================

LOG_FILE = "bot_events.jsonl"  # written in project root

# =========================
# Dry run
# =========================

DRY_RUN = False

