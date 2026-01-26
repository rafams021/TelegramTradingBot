# 🧪 GUÍA DE TESTING

Guía completa para ejecutar y escribir tests en TelegramTradingBot.

---

## 📋 ESTRUCTURA DE TESTS

```
tests/
├── conftest.py              # Fixtures compartidos
├── unit/                    # Tests unitarios
│   ├── test_signal_parser.py
│   ├── test_management_parser.py
│   ├── test_rules.py
│   └── test_signal_service.py
├── integration/             # Tests de integración
│   └── test_signal_flow.py
└── fixtures/                # Datos de prueba
    └── sample_signals.py
```

---

## 🚀 SETUP

### Instalar Dependencias

```bash
pip install pytest pytest-cov
```

### Estructura Mínima

Para que pytest funcione, necesitas:

```
TelegramTradingBot/
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   └── unit/
│       ├── __init__.py
│       └── test_*.py
```

---

## ▶️ EJECUTAR TESTS

### Todos los Tests

```bash
pytest
```

**Salida esperada:**
```
tests/unit/test_signal_parser.py ............ [10 passed]
tests/unit/test_management_parser.py ........ [10 passed]
tests/unit/test_rules.py ................ [15 passed]
tests/unit/test_signal_service.py ........ [8 passed]
tests/integration/test_signal_flow.py ........ [10 passed]

=============== 50+ passed in 2.5s ===============
```

### Solo Tests Unitarios

```bash
pytest tests/unit/ -v
```

### Solo Tests de Integración

```bash
pytest tests/integration/ -v
```

### Un Test Específico

```bash
# Por archivo
pytest tests/unit/test_signal_parser.py

# Por clase
pytest tests/unit/test_signal_parser.py::TestSignalParser

# Por método
pytest tests/unit/test_signal_parser.py::TestSignalParser::test_parse_valid_buy_signal
```

### Con Verbosidad

```bash
pytest -v    # Verbose
pytest -vv   # Extra verbose
```

### Mostrar Prints

```bash
pytest -s
```

---

## 📊 COVERAGE

### Ejecutar con Coverage

```bash
pytest --cov=core --cov=adapters --cov=infrastructure
```

### Reporte HTML

```bash
pytest --cov=core --cov-report=html

# Abre htmlcov/index.html en navegador
```

### Coverage por Módulo

```bash
pytest --cov=core --cov-report=term-missing
```

**Salida:**
```
Name                              Stmts   Miss  Cover   Missing
---------------------------------------------------------------
core/parsers/signal_parser.py       45      2    96%   78-79
core/parsers/management_parser.py   38      1    97%   92
core/services/signal_service.py     67      8    88%   45, 89-95
core/rules.py                       32      0   100%
---------------------------------------------------------------
TOTAL                              182     11    94%
```

### Coverage Mínimo

```bash
# Falla si coverage < 80%
pytest --cov=core --cov-fail-under=80
```

---

## ✍️ ESCRIBIR TESTS

### Estructura Básica

```python
# tests/unit/test_mymodule.py
import pytest
from core.mymodule import MyClass


class TestMyClass:
    """Tests para MyClass."""
    
    def setup_method(self):
        """Setup antes de cada test."""
        self.obj = MyClass()
    
    def test_something(self):
        """Debe hacer algo correctamente."""
        result = self.obj.do_something()
        assert result == expected
    
    def test_edge_case(self):
        """Debe manejar caso extremo."""
        with pytest.raises(ValueError):
            self.obj.invalid_input(None)
```

### Usar Fixtures

```python
# tests/conftest.py
import pytest
from core.state import BotState

@pytest.fixture
def bot_state():
    """Estado limpio del bot."""
    return BotState()


# tests/unit/test_mymodule.py
def test_with_fixture(bot_state):
    """Usa fixture automáticamente."""
    assert bot_state is not None
    assert len(bot_state.signals) == 0
```

### Parametrizar Tests

```python
@pytest.mark.parametrize("side,entry,expected", [
    ("BUY", 4910, 4912),
    ("SELL", 4880, 4875),
])
def test_multiple_cases(side, entry, expected):
    """Test con múltiples casos."""
    result = calculate(side, entry)
    assert result == expected
```

### Mocking

```python
from unittest.mock import Mock, patch

def test_with_mock():
    """Test con mock."""
    mock_client = Mock()
    mock_client.get_tick.return_value = Mock(bid=4910, ask=4911)
    
    result = process_with_client(mock_client)
    assert result is not None
    mock_client.get_tick.assert_called_once()


@patch('adapters.mt5_client.symbol_tick')
def test_with_patch(mock_tick):
    """Test con patch."""
    mock_tick.return_value = Mock(bid=4910, ask=4911)
    
    result = process_signal()
    assert result is not None
```

---

## 🎯 COBERTURA POR MÓDULO

### Parsers (95%+ target)

```python
# tests/unit/test_signal_parser.py
class TestSignalParser:
    def test_parse_valid_buy(self):
        """Señal BUY válida."""
        
    def test_parse_valid_sell(self):
        """Señal SELL válida."""
        
    def test_parse_invalid_no_tp(self):
        """Sin TP debe fallar."""
        
    def test_parse_invalid_no_sl(self):
        """Sin SL debe fallar."""
```

**Coverage objetivo:** 95%+

### Services (85%+ target)

```python
# tests/unit/test_signal_service.py
class TestSignalService:
    def test_process_signal_valid(self):
        """Procesamiento normal."""
        
    def test_process_signal_duplicate(self):
        """Duplicados rechazados."""
        
    def test_create_splits(self):
        """Creación de splits."""
```

**Coverage objetivo:** 85%+

### Rules (90%+ target)

```python
# tests/unit/test_rules.py
class TestDecideExecution:
    def test_market_within_tolerance(self):
    def test_limit_below_entry(self):
    def test_stop_above_entry(self):
    def test_skip_too_far(self):
```

**Coverage objetivo:** 90%+

### Integration (70%+ target)

```python
# tests/integration/test_signal_flow.py
class TestSignalFlow:
    def test_full_signal_flow_buy(self):
        """Flujo completo BUY."""
        
    def test_signal_with_edit(self):
        """Flujo con edición."""
        
    def test_management_command_flow(self):
        """Flujo de gestión."""
```

**Coverage objetivo:** 70%+

---

## 🔍 DEBUGGING TESTS

### Ejecutar con Debugger

```python
def test_something():
    result = do_something()
    breakpoint()  # Pausa aquí
    assert result == expected
```

```bash
pytest -s  # Permite interactuar con debugger
```

### Ver Prints

```python
def test_with_print():
    print(f"Debug: {value}")
    assert value > 0
```

```bash
pytest -s  # Muestra prints
```

### Ver Variables

```python
def test_debug():
    result = complex_function()
    print(f"Result: {result}")
    print(f"Type: {type(result)}")
    assert result is not None
```

---

## 📋 CHECKLIST DE TESTS

### Para Cada Feature Nueva

- [ ] Test de caso normal (happy path)
- [ ] Test de casos extremos (edge cases)
- [ ] Test de errores (error handling)
- [ ] Test con datos inválidos
- [ ] Docstring explicando qué testea

### Antes de Commit

- [ ] `pytest` pasa sin errores
- [ ] Coverage no baja
- [ ] No hay prints de debug
- [ ] Tests son deterministas (no dependen de tiempo/azar)

---

## 🎓 BEST PRACTICES

### 1. Nombres Descriptivos

```python
# ✅ Bueno
def test_parse_buy_signal_with_multiple_tps():
    """Debe parsear señal BUY con 3 TPs correctamente."""

# ❌ Malo
def test_parser():
    """Test."""
```

### 2. Un Assert por Test (generalmente)

```python
# ✅ Bueno
def test_signal_has_correct_side():
    signal = parse("BUY...")
    assert signal.side == OrderSide.BUY

def test_signal_has_correct_entry():
    signal = parse("BUY @ 4910...")
    assert signal.entry == 4910

# ❌ Malo
def test_signal():
    signal = parse("BUY @ 4910...")
    assert signal.side == OrderSide.BUY
    assert signal.entry == 4910
    assert len(signal.tps) == 3
    # ... muchos asserts
```

**Excepción:** Tests de integración pueden tener múltiples asserts.

### 3. Fixtures para Setup Común

```python
# ✅ Bueno
@pytest.fixture
def sample_signal():
    return Signal(...)

def test_something(sample_signal):
    # Usa fixture

# ❌ Malo
def test_something():
    signal = Signal(...)  # Duplicado en cada test
```

### 4. Mocks Solo cuando Necesario

```python
# ✅ Bueno - Mock de API externa
@patch('adapters.mt5_client.symbol_tick')
def test_with_mt5_mock(mock_tick):
    # MT5 es externo, merece mock

# ❌ Malo - Mock de lógica propia
@patch('core.services.signal_service.process_signal')
def test_with_service_mock(mock_process):
    # Testea el mock, no el código real
```

### 5. Tests Deterministas

```python
# ✅ Bueno
def test_parse_signal():
    result = parser.parse("XAUUSD BUY...")
    assert result.entry == 4910

# ❌ Malo
def test_current_time():
    result = get_current_time()
    assert result > 0  # Puede fallar dependiendo del tiempo
```

---

## 🐛 TROUBLESHOOTING

### "ModuleNotFoundError"

```bash
# Asegurar que estás en el directorio raíz
cd TelegramTradingBot
pytest
```

### "No tests ran"

```bash
# Verificar que archivos empiezan con test_
ls tests/unit/test_*.py

# Verificar __init__.py existen
find tests -name "__init__.py"
```

### Tests Lentos

```bash
# Ver cuáles tests son lentos
pytest --durations=10
```

### Coverage No Funciona

```bash
# Instalar coverage
pip install pytest-cov

# Verificar paths
pytest --cov=core --cov-report=term
```

---

## 📊 MÉTRICAS OBJETIVO

| Componente | Coverage Target | Tests Mínimos |
|------------|----------------|---------------|
| **Parsers** | 95% | 20+ |
| **Services** | 85% | 15+ |
| **Rules** | 90% | 15+ |
| **Domain** | 80% | (implícito) |
| **Integration** | 70% | 10+ |
| **TOTAL** | **85%+** | **50+** |

---

## 🚀 CI/CD (Futuro)

### GitHub Actions

```yaml
# .github/workflows/tests.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: 3.10
      - run: pip install -r requirements.txt
      - run: pip install pytest pytest-cov
      - run: pytest --cov=core --cov-fail-under=80
```

---

## 📚 RECURSOS

### Documentación

- [Pytest Docs](https://docs.pytest.org/)
- [Coverage.py](https://coverage.readthedocs.io/)
- [Mock Objects](https://docs.python.org/3/library/unittest.mock.html)

### Nuestros Docs

- `tests/conftest.py` - Fixtures compartidos
- `tests/fixtures/sample_signals.py` - Datos de prueba

---

**Versión:** 1.0  
**Última Actualización:** 2025-01-26