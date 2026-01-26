# 👨‍💻 GUÍA DE DESARROLLO

## 🚀 SETUP INICIAL

### Requisitos
- Python 3.10+
- MetaTrader 5 instalado
- Cuenta de Telegram

### Instalación

```bash
# Clonar repositorio
git clone https://github.com/rafams021/TelegramTradingBot.git
cd TelegramTradingBot

# Instalar dependencias
pip install -r requirements.txt

# Configurar credenciales
# Editar config/settings.py con tus datos
```

---

## 📁 ESTRUCTURA DEL PROYECTO

```
TelegramTradingBot/
│
├── config/              # Configuración
├── core/                # Lógica del bot
│   ├── domain/          # Modelos y enums
│   ├── parsers/         # Parseo de texto
│   ├── services/        # Lógica de negocio
│   └── monitoring/      # Watchers
│
├── adapters/            # Interfaces externas
│   ├── mt5/             # MetaTrader 5
│   └── telegram/        # Telegram
│
├── infrastructure/      # Cross-cutting
├── tests/               # Tests
├── docs/                # Documentación
└── utils/               # Utilidades
```

---

## 🧪 TESTING

### Ejecutar Tests

```bash
# Todos los tests
pytest

# Solo tests unitarios
pytest tests/unit/ -v

# Solo tests de integración
pytest tests/integration/ -v

# Con coverage
pytest --cov=core --cov-report=html
```

### Escribir Tests

```python
# tests/unit/test_mymodule.py
import pytest
from core.mymodule import MyClass

class TestMyClass:
    def test_something(self):
        obj = MyClass()
        result = obj.do_something()
        assert result == expected
```

---

## 🔧 CONVENCIONES DE CÓDIGO

### Style Guide

Seguimos PEP 8 con algunas extensiones:

```python
# Imports ordenados
import stdlib
import third_party
from core import local

# Type hints siempre
def function(param: str) -> int:
    return len(param)

# Docstrings para funciones públicas
def public_function(x: int) -> str:
    """
    Brief description.
    
    Args:
        x: Description
    
    Returns:
        Description
    """
    return str(x)
```

### Naming Conventions

```python
# Classes: PascalCase
class SignalParser:
    pass

# Functions/methods: snake_case
def parse_signal(text: str) -> Signal:
    pass

# Constants: UPPER_SNAKE_CASE
MAX_SPLITS = 10

# Private: _leading_underscore
def _internal_helper():
    pass

# Enums: PascalCase members
class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"
```

---

## 📝 LOGGING

### Usar el Logger

```python
from infrastructure.logging import get_logger, event, info, error

# Obtener logger
logger = get_logger()

# Eventos estructurados
event("SIGNAL_PARSED", msg_id=123, side="BUY", entry=4910)

# Logs informativos
info("Processing signal", msg_id=123)

# Errores con contexto
error("Failed to execute", exc_info=True, msg_id=123)
```

### Niveles de Log

- **event()**: Eventos de negocio importantes
- **info()**: Información general
- **warning()**: Advertencias
- **error()**: Errores con traceback
- **debug()**: Debugging detallado

---

## 🔄 WORKFLOW DE DESARROLLO

### 1. Crear Branch

```bash
git checkout -b feature/my-feature
```

### 2. Hacer Cambios

- Escribir código
- Escribir tests
- Actualizar documentación

### 3. Verificar

```bash
# Ejecutar tests
pytest

# Verificar imports
python -c "from core.services import SignalService; print('OK')"

# Ejecutar bot (modo dry-run)
# Editar config para DRY_RUN=True
python main.py
```

### 4. Commit

```bash
git add .
git commit -m "feat: descripción del cambio"
```

Convención de commits:
- `feat:` Nueva funcionalidad
- `fix:` Corrección de bug
- `refactor:` Refactorización
- `docs:` Documentación
- `test:` Tests

### 5. Push y PR

```bash
git push origin feature/my-feature
# Crear Pull Request en GitHub
```

---

## 🐛 DEBUGGING

### Habilitar Debug Logs

```python
# En config/settings.py o como variable de entorno
LOG_LEVEL = "DEBUG"
```

### Debugging de Señales

```python
# Ver qué se parseó
from core.parsers import SignalParser

parser = SignalParser()
signal = parser.parse(text)
print(signal)  # None o Signal object
```

### Debugging de State

```python
# Inspeccionar state del bot
from core.state import BOT_STATE

# Ver señales activas
print(BOT_STATE.signals)

# Ver cache de mensajes
print(BOT_STATE.msg_cache)
```

---

## 🔍 TROUBLESHOOTING

### ImportError

```bash
# Verificar estructura de carpetas
ls -R

# Verificar __init__.py existen
find . -name "__init__.py"
```

### MT5 No Conecta

1. Verificar MT5 está corriendo
2. Verificar credenciales en config
3. Ver logs en `bot_events.jsonl`

```bash
# Ver últimos eventos
tail -f bot_events.jsonl | jq
```

### Telegram No Conecta

1. Verificar API_ID y API_HASH
2. Borrar sesión y re-autenticar:

```bash
rm tg_session_qr.session
python main.py
# Escanear QR
```

---

## 📚 RECURSOS

### Documentación Interna

- `docs/ARCHITECTURE.md` - Arquitectura del sistema
- `docs/API.md` - Referencia de APIs
- `docs/TESTING.md` - Guía de testing

### Documentación Externa

- [Telethon Docs](https://docs.telethon.dev/)
- [MetaTrader5 Python](https://www.mql5.com/en/docs/python_metatrader5)
- [Python AsyncIO](https://docs.python.org/3/library/asyncio.html)

---

## 🎯 BEST PRACTICES

### 1. Type Hints Siempre

```python
# ✅ Bueno
def parse_signal(text: str) -> Optional[Signal]:
    pass

# ❌ Malo
def parse_signal(text):
    pass
```

### 2. Usar Enums en Vez de Strings

```python
# ✅ Bueno
if signal.side == OrderSide.BUY:
    pass

# ❌ Malo
if signal.side == "BUY":
    pass
```

### 3. Validar en Domain Models

```python
@dataclass
class Signal:
    entry: float
    tps: List[float]
    
    def __post_init__(self):
        if not self.tps:
            raise ValueError("Must have TPs")
```

### 4. Logging Estructurado

```python
# ✅ Bueno
event("ORDER_SENT", side="BUY", price=4910, vol=0.01)

# ❌ Malo
print("Order sent: BUY 4910 vol 0.01")
```

### 5. Separar Responsabilidades

```python
# ✅ Bueno
parser = SignalParser()
signal = parser.parse(text)

service = SignalService(state)
splits = service.create_splits(signal)

# ❌ Malo
def parse_and_create_splits(text):
    # Todo mezclado
    pass
```

---

## 🚀 AÑADIR NUEVA FUNCIONALIDAD

### Ejemplo: Nuevo Comando de Gestión

#### 1. Agregar Enum

```python
# core/domain/enums.py
class ManagementType(str, Enum):
    # ...
    PARTIAL_CLOSE = "PARTIAL_CLOSE"  # Nuevo
```

#### 2. Actualizar Parser

```python
# core/parsers/management_parser.py
_PARTIAL_CLOSE_RE = re.compile(r"CERRAR\s+(\d+)%", re.I)

def parse(self, text: str) -> ManagementAction:
    # ...
    m = self._PARTIAL_CLOSE_RE.search(text)
    if m:
        return ManagementAction(
            type=ManagementType.PARTIAL_CLOSE,
            percentage=int(m.group(1))
        )
```

#### 3. Implementar en Service

```python
# core/services/management_service.py
def _apply_partial_close(self, splits, percentage, ...):
    # Lógica de cierre parcial
    pass
```

#### 4. Escribir Tests

```python
# tests/unit/test_management_parser.py
def test_parse_partial_close():
    parser = ManagementParser()
    action = parser.parse("CERRAR 50%")
    assert action.type == ManagementType.PARTIAL_CLOSE
    assert action.percentage == 50
```

---

## ✅ CHECKLIST ANTES DE COMMIT

- [ ] Tests pasan: `pytest`
- [ ] Type hints correctos
- [ ] Docstrings actualizados
- [ ] Logs apropiados
- [ ] Sin prints() de debug
- [ ] Backward compatibility preservada
- [ ] README actualizado si necesario

---

**Versión:** 1.0  
**Última Actualización:** 2025-01-26