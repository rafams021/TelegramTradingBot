# config.py

# Telegram API credentials
API_ID = 0
API_HASH = ""
SESSION_NAME = "tg_session_qr"
CHANNEL_ID = 0  # channel/chat id (int)

# MT5 account
MT5_LOGIN = 1022962
MT5_PASSWORD = ""
MT5_SERVER = "VTMarkets-Demo"

# Trading settings
SYMBOL = "XAUUSD-ECN"
VOLUME_PER_ORDER = 0.05
DEVIATION = 50
MAGIC = 6069104329  # ideally TG user_id

# Execution drift policy (price units; XAUUSD-ECN usually 2 digits => 0.30 == $0.30)
BUY_UP_TOL = 0.30
BUY_DOWN_TOL = 1.00
SELL_DOWN_TOL = 0.30
SELL_UP_TOL = 1.00

# Extra safety hard cap
HARD_DRIFT = 10.0

# Optional extra cushion (available if you want to use it in rules.py)
EXTRA_SLIPPAGE = 0.10

# Break-even buffer
BE_BUFFER = 0.0

# Telegram edit handling (typos -> quick edits)
TG_EDIT_REPROCESS_WINDOW_S = 180
TG_EDIT_REPROCESS_MAX_ATTEMPTS = 3

# Logging
LOG_FILE = "bot_events.jsonl"  # written in project root

# Dry run
DRY_RUN = False

