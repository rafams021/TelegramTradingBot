# Telegram
API_ID = 32919258
API_HASH = "dfb662cee66fe7b2f337628eeac3316c"
SESSION_NAME = "tg_session_qr"
CHANNEL_ID = 2329472075

# Trading
SYMBOL = "XAUUSD-ECN"
VOLUME = 0.01
DEVIATION = 50
MAGIC = 6069104329

# Risk / policy
MAX_SPLITS = 10
PENDING_TIMEOUT_MIN = 60

MAX_UP_DRIFT = 0.30     # si precio se fue arriba del entry (BUY)
MAX_DOWN_DRIFT = 1.00   # si precio está debajo del entry (BUY)

DEFAULT_SL_DISTANCE = 50.0  # <- solicitado

# Watcher
WATCHER_INTERVAL_SEC = 5

# BE policy
# Extra buffer (en precio) además de stops/freeze level para evitar 10016 en broker.
BE_EXTRA_BUFFER = 0.10

# Close-at policy
CLOSE_AT_BUFFER = 0.00

# Logging
LOG_FILE = "bot_events.jsonl"

# Dry run
DRY_RUN = False

