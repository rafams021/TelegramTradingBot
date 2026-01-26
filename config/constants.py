# config/constants.py
"""
Constantes y valores mágicos usados en todo el proyecto.
Centraliza números mágicos y strings hardcodeados.
"""

# =========================
# MT5 Return Codes
# =========================
MT5_RETCODE_SUCCESS = 10009
MT5_RETCODE_INVALID_FILL = 10030

# =========================
# Order Comments
# =========================
COMMENT_MARKET_ORDER = "TG_BOT"
COMMENT_PENDING_ORDER = "TG_BOT_PENDING"
COMMENT_CLOSE_ORDER = "TG_BOT_CLOSE"
COMMENT_MODIFY_BE = "TG_BOT_BE"
COMMENT_MODIFY_SLTP = "TG_BOT_MODIFY"

# =========================
# Default Values
# =========================
DEFAULT_LOT = 0.01
DEFAULT_DEVIATION = 50
DEFAULT_POLL_INTERVAL_S = 1.0
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_DELAY_S = 0.2

# =========================
# Timeouts
# =========================
STARTUP_CUTOFF_TOLERANCE_S = 5
SYMBOL_SELECT_RETRIES = 3
SYMBOL_SELECT_DELAY_S = 0.2

# =========================
# Logging
# =========================
DEFAULT_EVENTS_PATH = "bot_events.jsonl"
LOG_TEXT_SAMPLE_LIMIT = 300






