# 🏗️ ARQUITECTURA DEL TELEGRAM TRADING BOT

## 📋 VISIÓN GENERAL

TelegramTradingBot es un sistema automatizado de trading que:
1. Recibe señales de un canal de Telegram
2. Las parsea y valida
3. Ejecuta órdenes en MetaTrader 5
4. Monitorea posiciones activas
5. Aplica gestión (Break Even, Move SL, Close)

---

## 🎯 ARQUITECTURA DE ALTO NIVEL

```
┌─────────────────────────────────────────────────────────────┐
│                    TELEGRAM CHANNEL                          │
│              (Señales y Comandos de Trading)                 │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  TELEGRAM CLIENT                             │
│            (adapters/telegram/client.py)                     │
│  • Recibe mensajes y ediciones                              │
│  • Filtra por startup cutoff                                │
│  • Delega a handlers                                        │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    EXECUTOR                                  │
│              (core/executor.py)                              │
│  • Orquesta flujo de procesamiento                          │
│  • Delega a Parsers y Services                              │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │               │
        ▼              ▼               ▼
┌─────────────┐ ┌────────────┐ ┌─────────────┐
│   PARSERS   │ │  SERVICES  │ │    RULES    │
│             │ │            │ │             │
│ • Signal    │ │ • Signal   │ │ • Execution │
│ • Mgmt      │ │ • Mgmt     │ │ • TP/BE/SL  │
└──────┬──────┘ └─────┬──────┘ └──────┬──────┘
       │              │               │
       └──────────────┼───────────────┘
                      │
                      ▼
            ┌──────────────────┐
            │   DOMAIN MODELS  │
            │                  │
            │ • Signal         │
            │ • Position       │
            │ • Enums          │
            └────────┬─────────┘
                     │
                     ▼
            ┌──────────────────┐
            │      STATE       │
            │  (En memoria)    │
            └────────┬─────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
        ▼            ▼            ▼
┌─────────────┐ ┌────────┐ ┌──────────┐
│  MT5 CLIENT │ │WATCHER │ │  LOGGER  │
│             │ │        │ │          │
│ • Orders    │ │• Pending│ │• Events  │
│ • Positions │ │• Mgmt   │ │• Errors  │
└─────────────┘ └────────┘ └──────────┘
```

---

## 📦 MÓDULOS PRINCIPALES

### 1. **config/** - Configuración
```python
config/
├── settings.py     # AppConfig, MT5Config, TradingConfig
└── constants.py    # Constantes globales
```
**Responsabilidad:** Centralizar toda la configuración del bot.

### 2. **core/domain/** - Modelos de Dominio
```python
core/domain/
├── enums.py        # OrderSide, OrderStatus, ExecutionMode, etc.
└── models.py       # Signal, Position, MessageCache
```
**Responsabilidad:** Definir entidades de negocio y tipos.

### 3. **core/parsers/** - Parsers
```python
core/parsers/
├── signal_parser.py       # SignalParser
└── management_parser.py   # ManagementParser
```
**Responsabilidad:** Extraer información estructurada de texto.

### 4. **core/services/** - Lógica de Negocio
```python
core/services/
├── signal_service.py      # SignalService
└── management_service.py  # ManagementService
```
**Responsabilidad:** Implementar lógica de negocio del bot.

### 5. **core/monitoring/** - Watchers
```python
core/monitoring/
├── base_watcher.py         # BaseWatcher (abstracto)
├── pending_watcher.py      # PendingOrderWatcher
└── management_applier.py   # ManagementApplier
```
**Responsabilidad:** Monitorear y gestionar posiciones activas.

### 6. **adapters/** - Interfaces Externas
```python
adapters/
├── mt5/                    # MT5Client
│   ├── client.py
│   ├── connection.py
│   └── types.py
└── telegram/               # TelegramBotClient
    └── client.py
```
**Responsabilidad:** Comunicación con servicios externos.

### 7. **infrastructure/** - Cross-cutting
```python
infrastructure/
└── logging/
    └── logger.py           # BotLogger
```
**Responsabilidad:** Servicios transversales (logging, etc).

---

## 🔄 FLUJOS PRINCIPALES

### Flujo 1: Procesamiento de Señal

```
1. Usuario publica señal en Telegram
                ↓
2. TelegramBotClient recibe mensaje
                ↓
3. Verifica startup cutoff
                ↓
4. Executor.execute_signal()
                ↓
5. SignalService.process_signal()
   - Valida cache de mensajes
   - SignalParser parsea texto
   - Valida señal
                ↓
6. SignalService.create_splits()
   - Crea Position por cada TP
                ↓
7. Rules.decide_execution()
   - MARKET / LIMIT / STOP / SKIP
                ↓
8. MT5Client ejecuta órdenes
                ↓
9. State actualizado con tickets
                ↓
10. Logger registra todo
```

### Flujo 2: Gestión de Posiciones

```
1. Usuario envía comando (ej: "BE")
                ↓
2. TelegramBotClient recibe mensaje
                ↓
3. Executor clasifica como management
                ↓
4. ManagementParser parsea comando
                ↓
5. ManagementService.apply()
   - Encuentra señal original (reply_to)
   - Arma flags en positions
                ↓
6. Watcher detecta flags armados
                ↓
7. ManagementApplier aplica gestión
   - Verifica condiciones
   - Modifica en MT5
                ↓
8. State actualizado
```

### Flujo 3: Monitoreo Continuo

```
PendingOrderWatcher (cada 1s):
    ↓
1. Obtiene tick de MT5
    ↓
2. Itera sobre pending orders
    ↓
3. Verifica si TP alcanzado → Cancela
4. Verifica timeout → Cancela
    ↓
5. Actualiza State

ManagementApplier (cada 1s):
    ↓
1. Obtiene tick de MT5
    ↓
2. Itera sobre posiciones OPEN
    ↓
3. Si be_armed → Aplica BE
4. Si sl_move_armed → Mueve SL
5. Si close_armed → Cierra
    ↓
6. Actualiza State
```

---

## 🎯 PATRONES DE DISEÑO APLICADOS

### 1. **Hexagonal Architecture**
- Domain en el centro
- Adapters en los bordes
- Independencia de frameworks

### 2. **Service Layer Pattern**
- Lógica de negocio en Services
- Coordinación en Executor
- Datos en Domain Models

### 3. **Repository Pattern**
- State actúa como repository
- En memoria (no persistente)

### 4. **Strategy Pattern**
- Diferentes modos de ejecución (MARKET/LIMIT/STOP)
- Intercambiables

### 5. **Template Method Pattern**
- BaseWatcher define estructura
- Subclases implementan watch_cycle()

### 6. **Observer Pattern**
- Watchers observan State
- Reaccionan a cambios

---

## 🔐 DECISIONES ARQUITECTÓNICAS

### 1. **State en Memoria**
**Decisión:** No persistir state en base de datos.
**Razón:** 
- Simplicidad
- Bot se reinicia rápido
- Posiciones persisten en MT5

### 2. **Backward Compatibility**
**Decisión:** Mantener API antigua funcionando.
**Razón:**
- Migración gradual
- No romper código existente
- Menos riesgo

### 3. **Logging a JSONL**
**Decisión:** Logs estructurados en archivo JSONL.
**Razón:**
- Fácil parsear
- Herramientas estándar (jq, grep)
- No requiere base de datos

### 4. **Type Safety con Enums**
**Decisión:** Usar enums en vez de strings.
**Razón:**
- Prevenir typos
- Mejor autocompletado
- Validación en tiempo de desarrollo

### 5. **Watchers en Threads**
**Decisión:** Blocking threads en vez de async tasks.
**Razón:**
- MT5 API es bloqueante
- Evitar complejidad de async-await
- Auto-restart simple

---

## 📊 DEPENDENCIAS PRINCIPALES

```
telethon        → Cliente Telegram
MetaTrader5     → API de MT5
dataclasses     → Modelos de datos
typing          → Type hints
asyncio         → Event loop principal
threading       → Watchers
```

---

## 🚀 ESCALABILIDAD

### Limitaciones Actuales
- State en memoria (no sobrevive reinicio)
- Un solo símbolo a la vez
- Single-threaded por watcher

### Posibles Mejoras
- Persistir state en SQLite/Redis
- Multi-símbolo con pools de watchers
- WebSocket de MT5 en vez de polling
- Dashboard web de monitoreo

---

## 📝 CONVENCIONES DE CÓDIGO

### Naming
- Classes: PascalCase
- Functions: snake_case
- Constants: UPPER_SNAKE_CASE
- Private: _leading_underscore

### Imports
```python
# 1. Standard library
import asyncio
import time

# 2. Third party
from telethon import TelegramClient

# 3. Local
from core.domain import Signal
from adapters.mt5 import MT5Client
```

### Docstrings
```python
def function(param: Type) -> ReturnType:
    """
    Brief description.
    
    Args:
        param: Description
    
    Returns:
        Description
    """
```

---

**Versión:** 1.0  
**Última Actualización:** 2025-01-26