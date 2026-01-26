# tests/fixtures/sample_signals.py
"""
Señales de prueba para testing.
"""

# Señal BUY válida simple
VALID_BUY_SIGNAL = """
XAUUSD BUY @ 4910
TP1: 4912
TP2: 4915
TP3: 4920
SL: 4900
"""

# Señal SELL válida
VALID_SELL_SIGNAL = """
XAUUSD SELL @ 4880
TP1: 4875
TP2: 4870
TP3: 4865
SL: 4890
"""

# Señal con rango de entrada
SIGNAL_WITH_RANGE = """
XAUUSD BUY
BUY @ (4982.5-4981.5)
TP1: 4985
TP2: 4990
SL: 4975
"""

# Señal formato alternativo
SIGNAL_ALTERNATE_FORMAT = """
XAUUSD | SELL
SELL 4880
TP 4875
TP 4870
STOP LOSS: 4887
"""

# Señal inválida - sin TP
INVALID_NO_TP = """
XAUUSD BUY @ 4910
SL: 4900
"""

# Señal inválida - sin SL
INVALID_NO_SL = """
XAUUSD BUY @ 4910
TP1: 4912
"""

# Señal inválida - TPs incorrectos (BUY con TP abajo)
INVALID_TP_DIRECTION = """
XAUUSD BUY @ 4910
TP1: 4905
SL: 4900
"""

# Comandos de gestión
MANAGEMENT_BE = "BE"
MANAGEMENT_MOVE_SL = "MOVER EL SL A 4905"
MANAGEMENT_CLOSE_TP1 = "CERRAR TP1"
MANAGEMENT_CLOSE_ALL = "CERRAR TODO"

# Texto no relacionado
NOT_A_SIGNAL = "Hola, ¿cómo estás?"