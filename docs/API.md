# 📖 API REFERENCE

Referencia completa de las APIs del TelegramTradingBot.

---

## 🎯 PARSERS

### SignalParser

```python
from core.parsers import SignalParser

parser = SignalParser()
signal = parser.parse(text, msg_id=123)
```

**Métodos:**

#### `parse(text: str, msg_id: int = 0) -> Optional[Signal]`

Parsea un mensaje de Telegram en una señal.

**Args:**
- `text`: Texto del mensaje
- `msg_id`: ID del mensaje (opcional)

**Returns:**
- `Signal` si se puede parsear
- `None` si el texto no es una señal válida

**Ejemplo:**
```python
text = """
XAUUSD BUY @ 4910
TP1: 4912
TP2: 4915
SL: 4900
"""

signal = parser.parse(text, msg_id=123)
# Signal(message_id=123, symbol='XAUUSD', side=OrderSide.BUY, ...)
```

---

### ManagementParser

```python
from core.parsers import ManagementParser

parser = ManagementParser()
action = parser.parse(text)
```

**Métodos:**

#### `parse(text: str) -> ManagementAction`

Parsea un comando de gestión.

**Args:**
- `text`: Texto del mensaje

**Returns:**
- `ManagementAction` con el comando parseado

**Ejemplo:**
```python
action = parser.parse("BE")
# ManagementAction(type=ManagementType.BE, price=None, tp_index=None)

action = parser.parse("MOVER EL SL A 4905")
# ManagementAction(type=ManagementType.MOVE_SL, price=4905, tp_index=None)
```

#### `is_management_command(text: str) -> bool`

Verifica si el texto es un comando de gestión.

**Args:**
- `text`: Texto a verificar

**Returns:**
- `True` si es comando de gestión
- `False` en caso contrario

---

## 🔧 SERVICES

### SignalService

```python
from core.services import SignalService
from core.state import BotState

state = BotState()
service = SignalService(state)
```

**Métodos:**

#### `process_signal(msg_id: int, text: str, is_edit: bool = False) -> Optional[Signal]`

Procesa un mensaje de Telegram.

**Args:**
- `msg_id`: ID del mensaje
- `text`: Texto del mensaje
- `is_edit`: Si es una edición

**Returns:**
- `Signal` procesada o `None`

**Funcionalidad:**
- Gestiona cache de mensajes
- Valida duplicados
- Maneja ventana de edits
- Parsea señal
- Agrega a state

#### `create_splits(signal_msg_id: int) -> List[Position]`

Crea splits (posiciones) para cada TP de una señal.

**Args:**
- `signal_msg_id`: ID del mensaje de señal

**Returns:**
- Lista de `Position` (splits)

#### `should_skip_tp(tp: float, side: OrderSide, bid: float, ask: float) -> bool`

Verifica si un TP ya fue alcanzado.

**Args:**
- `tp`: Precio del Take Profit
- `side`: Lado de la operación
- `bid`: Precio bid actual
- `ask`: Precio ask actual

**Returns:**
- `True` si TP ya alcanzado (skipear)
- `False` si aún no alcanzado

---

### ManagementService

```python
from core.services import ManagementService
from core.state import BotState

state = BotState()
service = ManagementService(state)
```

**Métodos:**

#### `apply(action: ManagementAction, msg_id: int, reply_to: Optional[int]) -> bool`

Aplica un comando de gestión.

**Args:**
- `action`: Acción parseada
- `msg_id`: ID del mensaje de comando
- `reply_to`: ID del mensaje de señal original

**Returns:**
- `True` si se aplicó correctamente
- `False` en caso contrario

**Funcionalidad:**
- Valida reply_to
- Encuentra señal original
- Arma flags en posiciones según tipo:
  - `BE`: Arma break even
  - `MOVE_SL`: Arma movimiento de SL
  - `CLOSE_TP_AT`: Arma cierre en TP
  - `CLOSE_ALL_AT`: Arma cierre de todo

---

## 📏 RULES

### decide_execution

```python
from core.rules import decide_execution
from core.domain.enums import OrderSide, ExecutionMode

mode = decide_execution(side, entry, current_price)
```

**Función:**

```python
def decide_execution(
    side: OrderSide,
    entry: float,
    current_price: float
) -> ExecutionMode
```

**Args:**
- `side`: Lado de la operación (BUY/SELL)
- `entry`: Precio de entrada deseado
- `current_price`: Precio actual del mercado

**Returns:**
- `ExecutionMode.MARKET`: Ejecutar a mercado
- `ExecutionMode.LIMIT`: Orden límite
- `ExecutionMode.STOP`: Orden stop
- `ExecutionMode.SKIP`: No ejecutar (demasiado lejos)

**Lógica:**
```python
delta = current_price - entry

# Si |delta| > HARD_DRIFT => SKIP
# Si dentro de tolerancia => MARKET
# Si fuera de tolerancia:
#   BUY: entry arriba => STOP, entry abajo => LIMIT
#   SELL: entry abajo => STOP, entry arriba => LIMIT
```

---

### tp_reached

```python
from core.rules import tp_reached

reached = tp_reached(side, tp, bid, ask)
```

**Función:**

```python
def tp_reached(
    side: str,
    tp: float,
    bid: float,
    ask: float
) -> bool
```

**Args:**
- `side`: Lado de la operación ("BUY"/"SELL")
- `tp`: Precio del Take Profit
- `bid`: Precio bid actual
- `ask`: Precio ask actual

**Returns:**
- `True` si TP fue alcanzado
- `False` si no

**Lógica:**
- BUY: `bid >= tp`
- SELL: `ask <= tp`

---

### be_allowed

```python
from core.rules import be_allowed

allowed = be_allowed(side, be_price, bid, ask, min_dist)
```

**Función:**

```python
def be_allowed(
    side: str,
    be_price: float,
    bid: float,
    ask: float,
    min_dist: float
) -> bool
```

**Args:**
- `side`: Lado ("BUY"/"SELL")
- `be_price`: Precio del break even
- `bid`: Precio bid actual
- `ask`: Precio ask actual
- `min_dist`: Distancia mínima del stop

**Returns:**
- `True` si BE está permitido
- `False` si no (muy cerca del precio actual)

**Lógica:**
- BUY: `(bid - be_price) >= min_dist`
- SELL: `(be_price - ask) >= min_dist`

---

### close_at_triggered

```python
from core.rules import close_at_triggered

triggered = close_at_triggered(side, target, bid, ask, buffer)
```

**Función:**

```python
def close_at_triggered(
    side: str,
    target: float,
    bid: float,
    ask: float,
    buffer: float = 0.0
) -> bool
```

**Args:**
- `side`: Lado ("BUY"/"SELL")
- `target`: Precio objetivo de cierre
- `bid`: Precio bid actual
- `ask`: Precio ask actual
- `buffer`: Buffer adicional (opcional)

**Returns:**
- `True` si debe cerrar
- `False` si no

**Lógica:**
- BUY: `bid >= (target + buffer)`
- SELL: `ask <= (target - buffer)`

---

## 🔌 ADAPTERS

### MT5Client

```python
from adapters.mt5 import MT5Client

client = MT5Client(
    login=1234567,
    password="password",
    server="Broker-Server",
    symbol="XAUUSD-ECN",
    deviation=50,
    magic=123456
)
```

**Métodos Principales:**

#### `connect() -> bool`

Conecta con MT5.

**Returns:**
- `True` si conexión exitosa
- `False` si falla

#### `disconnect() -> None`

Desconecta de MT5.

#### `get_tick() -> Optional[Tick]`

Obtiene tick actual del símbolo.

**Returns:**
- `Tick(bid, ask, last, time_msc)` o `None`

#### `open_market(side: str, vol: float, sl: float, tp: float) -> Tuple[dict, Any]`

Abre orden a mercado.

**Args:**
- `side`: "BUY" o "SELL"
- `vol`: Volumen (lotes)
- `sl`: Stop Loss
- `tp`: Take Profit

**Returns:**
- `(request_dict, result_object)`

#### `open_pending(side: str, mode: str, vol: float, price: float, sl: float, tp: float)`

Abre orden pendiente.

**Args:**
- `side`: "BUY" o "SELL"
- `mode`: "LIMIT" o "STOP"
- `vol`: Volumen
- `price`: Precio de la orden
- `sl`: Stop Loss
- `tp`: Take Profit

**Returns:**
- `(request_dict, result_object)`

#### `modify_sl(ticket: int, sl: float, fallback_tp: float = None)`

Modifica Stop Loss preservando TP.

**Args:**
- `ticket`: Ticket de la posición
- `sl`: Nuevo Stop Loss
- `fallback_tp`: TP a usar si no existe (opcional)

**Returns:**
- `(request_dict, result_object)`

#### `close_position(ticket: int, side: str, vol: float)`

Cierra una posición.

**Args:**
- `ticket`: Ticket de la posición
- `side`: "BUY" o "SELL"
- `vol`: Volumen a cerrar

**Returns:**
- `(request_dict, result_object)`

---

### TelegramBotClient

```python
from adapters.telegram import TelegramBotClient

client = TelegramBotClient(
    api_id=12345678,
    api_hash="your_hash",
    session_name="session",
    channel_id=123456789,
    state=bot_state
)
```

**Métodos:**

#### `async start() -> bool`

Inicia el cliente de Telegram.

**Returns:**
- `True` si conexión exitosa

#### `setup_handlers(on_message: Callable, on_edit: Callable) -> None`

Configura handlers de mensajes.

**Args:**
- `on_message`: Callback para mensajes nuevos
- `on_edit`: Callback para mensajes editados

**Firma de Callbacks:**
```python
async def on_message(
    msg_id: int,
    text: str,
    reply_to: int,
    date_iso: str,
    is_edit: bool
) -> None:
    pass
```

#### `async run() -> None`

Ejecuta el cliente hasta desconexión.

#### `async disconnect() -> None`

Desconecta el cliente.

---

## 🔍 MONITORING (WATCHERS)

### PendingOrderWatcher

```python
from core.monitoring import PendingOrderWatcher
from core.state import BotState

state = BotState()
watcher = PendingOrderWatcher(state, poll_interval=1.0)
watcher.start()  # Blocking
```

**Funcionalidad:**
- Monitorea órdenes pendientes
- Cancela si TP alcanzado
- Cancela por timeout

### ManagementApplier

```python
from core.monitoring import ManagementApplier
from core.state import BotState

state = BotState()
applier = ManagementApplier(state, poll_interval=1.0)
applier.start()  # Blocking
```

**Funcionalidad:**
- Aplica Break Even cuando está armado
- Aplica Move SL cuando está armado
- Aplica Close At cuando está armado

---

## 📊 DOMAIN MODELS

### Signal

```python
from core.domain.models import Signal
from core.domain.enums import OrderSide

signal = Signal(
    message_id=123,
    symbol="XAUUSD",
    side=OrderSide.BUY,
    entry=4910.0,
    tps=[4912.0, 4915.0, 4920.0],
    sl=4900.0
)
```

**Atributos:**
- `message_id: int` - ID del mensaje de Telegram
- `symbol: str` - Símbolo (ej: "XAUUSD")
- `side: OrderSide` - BUY o SELL
- `entry: float` - Precio de entrada
- `tps: List[float]` - Lista de Take Profits
- `sl: float` - Stop Loss
- `created_at: str` - Timestamp ISO

**Propiedades:**
- `num_tps: int` - Número de TPs

**Validaciones:**
- BUY: TPs > entry, SL < entry
- SELL: TPs < entry, SL > entry

---

### Position (Split)

```python
from core.domain.models import Position
from core.domain.enums import OrderSide, OrderStatus

position = Position(
    split_id="123_split_0",
    split_index=0,
    signal_message_id=123,
    symbol="XAUUSD",
    side=OrderSide.BUY,
    entry=4910.0,
    tp=4912.0,
    sl=4900.0,
    volume=0.01
)
```

**Atributos Principales:**
- `split_id: str` - ID único del split
- `split_index: int` - Índice (0, 1, 2...)
- `signal_message_id: int` - ID de señal padre
- `symbol: str` - Símbolo
- `side: OrderSide` - BUY/SELL
- `entry: float` - Precio entrada
- `tp: float` - Take Profit
- `sl: float` - Stop Loss
- `volume: float` - Volumen en lotes
- `status: OrderStatus` - Estado actual

**Estados Posibles:**
- `NEW` - Recién creado
- `PENDING` - Orden pendiente en MT5
- `OPEN` - Posición abierta
- `CLOSED` - Posición cerrada
- `CANCELED` - Orden cancelada
- `ERROR` - Error en ejecución

**Métodos:**
- `mark_pending(ticket, timestamp)` - Marca como pendiente
- `mark_open(ticket, price, timestamp)` - Marca como abierta
- `mark_closed(price, timestamp)` - Marca como cerrada
- `mark_canceled(timestamp)` - Marca como cancelada
- `arm_be()` - Arma break even
- `apply_be(timestamp)` - Aplica break even
- `arm_sl_move(new_sl)` - Arma movimiento de SL
- `arm_close(target)` - Arma cierre

---

## 🔐 ENUMS

### OrderSide

```python
from core.domain.enums import OrderSide

OrderSide.BUY   # "BUY"
OrderSide.SELL  # "SELL"
```

### OrderStatus

```python
from core.domain.enums import OrderStatus

OrderStatus.NEW       # "NEW"
OrderStatus.PENDING   # "PENDING"
OrderStatus.OPEN      # "OPEN"
OrderStatus.CLOSED    # "CLOSED"
OrderStatus.CANCELED  # "CANCELED"
OrderStatus.ERROR     # "ERROR"
```

### ExecutionMode

```python
from core.domain.enums import ExecutionMode

ExecutionMode.MARKET  # "MARKET"
ExecutionMode.LIMIT   # "LIMIT"
ExecutionMode.STOP    # "STOP"
ExecutionMode.SKIP    # "SKIP"
```

### ManagementType

```python
from core.domain.enums import ManagementType

ManagementType.NONE          # "NONE"
ManagementType.BE            # "BE"
ManagementType.MOVE_SL       # "MOVE_SL"
ManagementType.CLOSE_TP_AT   # "CLOSE_TP_AT"
ManagementType.CLOSE_ALL_AT  # "CLOSE_ALL_AT"
```

---

## 📝 LOGGING

### BotLogger

```python
from infrastructure.logging import get_logger

logger = get_logger()
```

**Métodos:**

#### `event(event_type: str, **data: Any) -> None`

Registra un evento estructurado.

```python
logger.event("SIGNAL_PARSED", msg_id=123, side="BUY", entry=4910)
```

#### `info(message: str, **context: Any) -> None`

Log informativo.

```python
logger.info("Processing signal", msg_id=123)
```

#### `warning(message: str, **context: Any) -> None`

Log de advertencia.

```python
logger.warning("Price too far", delta=15.5)
```

#### `error(message: str, exc_info: bool = False, **context: Any) -> None`

Log de error.

```python
logger.error("Failed to execute", exc_info=True, msg_id=123)
```

---

## 🔄 STATE

### BotState

```python
from core.state import BotState

state = BotState()
```

**Atributos:**
- `signals: Dict[int, SignalState]` - Señales activas
- `msg_cache: Dict[int, MsgCacheEntry]` - Cache de mensajes
- `tg_startup_cutoff_iso: Optional[str]` - Cutoff para mensajes

**Métodos:**

#### `add_signal(signal: Signal) -> None`

Agrega una señal al state.

#### `has_signal(signal_msg_id: int) -> bool`

Verifica si existe una señal.

#### `get_signal(signal_msg_id: int) -> Optional[SignalState]`

Obtiene una señal.

#### `build_splits_for_signal(signal_msg_id: int) -> List[Position]`

Crea splits para una señal.

---

**Versión:** 1.0  
**Última Actualización:** 2025-01-26