# Telegram
API_ID = 32919258
API_HASH = "dfb662cee66fe7b2f337628eeac3316c"
SESSION_NAME = "tg_session_qr"
CHANNEL_ID = 2329472075

# Trading
SYMBOL = "XAUUSD-ECN"
VOLUME = 0.05
DEVIATION = 50
MAGIC = 6069104329

# Risk / policy
MAX_SPLITS = 10
PENDING_TIMEOUT_MIN = 60

# --- Entry execution policy (drift/tolerance) ---
# Definición:
#   delta = current_price - entry
#   current_price: BUY usa ASK, SELL usa BID.
#
# Guardrail duro:
#   si abs(delta) > HARD_DRIFT => SKIP (no operar; demasiado lejos del entry).
HARD_DRIFT = 10.0

# Tolerancias asimétricas para permitir MARKET; si se sale del "colchón" => LIMIT (esperar pullback).
# BUY:
BUY_UP_TOL = 0.30      # precio ARRIBA del entry permitido para BUY MARKET (delta > 0)
BUY_DOWN_TOL = 1.00    # precio ABAJO del entry permitido para BUY MARKET (delta < 0)
# SELL:
SELL_DOWN_TOL = 0.30   # precio ABAJO del entry permitido para SELL MARKET (delta < 0)
SELL_UP_TOL = 1.00     # precio ARRIBA del entry permitido para SELL MARKET (delta > 0)

# Backwards-compat (si algo viejo lo usa); NO usar para lógica nueva
MAX_UP_DRIFT = BUY_UP_TOL
MAX_DOWN_DRIFT = BUY_DOWN_TOL

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

