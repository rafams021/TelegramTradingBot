# 🤖 TELEGRAM TRADING BOT - REFACTORIZACIÓN COMPLETADA

Bot de trading automatizado que ejecuta señales de Telegram en MetaTrader 5.

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-Passing-success.svg)](tests/)

---

## 📋 ¿QUÉ HACE ESTE BOT?

1. **Recibe señales** de un canal de Telegram
2. **Parsea y valida** automáticamente
3. **Ejecuta órdenes** en MetaTrader 5
4. **Monitorea posiciones** 24/7
5. **Aplica gestión** (BE, MOVE_SL, CLOSE)

### Ejemplo de Señal

```
XAUUSD BUY @ 4910
TP1: 4912
TP2: 4915
TP3: 4920
SL: 4900
```

El bot automáticamente:
- ✅ Parsea la señal
- ✅ Crea 3 posiciones (1 por TP)
- ✅ Ejecuta en MT5
- ✅ Monitorea hasta cierre

---

## 🎯 CARACTERÍSTICAS

### ✅ Core Features

- **Parseo Inteligente**: Soporta múltiples formatos de señales
- **Ejecución Automática**: MARKET / LIMIT / STOP según precio
- **Splits por TP**: Una posición por cada Take Profit
- **Gestión Avanzada**: Break Even, Move SL, Close At
- **Monitoreo 24/7**: Watchers especializados
- **Logging Completo**: Todo registrado en JSONL

### ✅ Calidad de Código

- **Type Safety**: Type hints + Enums
- **Testeable**: Tests unitarios e integración
- **Documentado**: Docs completas
- **Modular**: Arquitectura limpia
- **Backward Compatible**: API antigua sigue funcionando

---

## 🚀 INSTALACIÓN RÁPIDA

### Requisitos

- Python 3.10+
- MetaTrader 5
- Cuenta de Telegram

### Setup

```bash
# 1. Clonar
git clone https://github.com/rafams021/TelegramTradingBot.git
cd TelegramTradingBot

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar
# Editar config/settings.py con tus credenciales

# 4. Ejecutar
python main.py
```

---

## 📁 ESTRUCTURA DEL PROYECTO

```
TelegramTradingBot/
│
├── config/                 # Configuración
│   ├── settings.py         # AppConfig, MT5Config, TradingConfig
│   └── constants.py        # Constantes globales
│
├── core/                   # Lógica del bot
│   ├── domain/             # Modelos y enums
│   ├── parsers/            # SignalParser, ManagementParser
│   ├── services/           # SignalService, ManagementService
│   ├── monitoring/         # Watchers especializados
│   ├── executor.py         # Orquestador principal
│   └── rules.py            # Reglas de ejecución
│
├── adapters/               # Interfaces externas
│   ├── mt5/                # Cliente MT5 modular
│   └── telegram/           # Cliente Telegram
│
├── infrastructure/         # Cross-cutting
│   └── logging/            # Logger centralizado
│
├── tests/                  # Tests completos
│   ├── unit/               # Tests unitarios
│   ├── integration/        # Tests de integración
│   └── fixtures/           # Datos de prueba
│
├── docs/                   # Documentación
│   ├── ARCHITECTURE.md     # Arquitectura del sistema
│   ├── DEVELOPMENT.md      # Guía de desarrollo
│   └── TESTING.md          # Guía de testing
│
└── main.py                 # Punto de entrada
```

---

## 🔧 CONFIGURACIÓN

### Demo vs Real

```python
# config/settings.py

# DEMO (default)
CONFIG = create_app_config(use_real=False)

# REAL (trading real)
CONFIG = create_app_config(use_real=True)
```

### Variables Principales

```python
# Telegram
API_ID = 12345678
API_HASH = "your_hash"
CHANNEL_ID = 123456789

# MT5
MT5_LOGIN = 1234567
MT5_PASSWORD = "password"
MT5_SERVER = "Broker-Server"

# Trading
SYMBOL = "XAUUSD-ECN"
VOLUME_PER_ORDER = 0.01
MAX_SPLITS = 10
```

---

## 📊 ARQUITECTURA

### Flujo de Señal

```
Telegram → Parser → Service → Rules → MT5 → State → Watcher
```

### Componentes Principales

| Componente | Responsabilidad |
|------------|-----------------|
| **Parsers** | Extraer datos de texto |
| **Services** | Lógica de negocio |
| **Rules** | Decisiones de ejecución |
| **Adapters** | MT5 y Telegram |
| **Watchers** | Monitoreo continuo |

Ver [ARCHITECTURE.md](docs/ARCHITECTURE.md) para detalles.

---

## 🧪 TESTING

### Ejecutar Tests

```bash
# Todos los tests
pytest

# Solo unitarios
pytest tests/unit/ -v

# Con coverage
pytest --cov=core --cov-report=html
```

### Estructura de Tests

```
tests/
├── unit/                   # Tests de componentes
│   ├── test_signal_parser.py
│   ├── test_management_parser.py
│   ├── test_rules.py
│   └── test_services.py
│
├── integration/            # Tests de flujos
│   └── test_signal_flow.py
│
└── fixtures/               # Datos de prueba
    └── sample_data.py
```

---

## 📚 DOCUMENTACIÓN

### Guías Disponibles

- [📐 ARCHITECTURE.md](docs/ARCHITECTURE.md) - Arquitectura del sistema
- [👨‍💻 DEVELOPMENT.md](docs/DEVELOPMENT.md) - Guía de desarrollo
- [🧪 TESTING.md](docs/TESTING.md) - Guía de testing
- [📖 API.md](docs/API.md) - Referencia de APIs

### READMEs de Fases

- [FASE1_README.md](FASE1_README.md) - Estructura y config
- [FASE2_README.md](FASE2_README.md) - Services y rules
- [FASE3_README.md](FASE3_README.md) - MT5 y Telegram clients
- [FASE4_README.md](FASE4_README.md) - Parsers y management
- [FASE5_README.md](FASE5_README.md) - Watchers refactorizados
- [FASE6_README.md](FASE6_README.md) - Testing y docs

---

## 🎓 PARA DESARROLLADORES

### Añadir Nueva Funcionalidad

```python
# 1. Crear enum si necesario
class NewFeature(str, Enum):
    FEATURE_A = "FEATURE_A"

# 2. Actualizar parser
def parse_new_feature(text: str):
    pass

# 3. Implementar en service
class NewService:
    def apply_feature(self):
        pass

# 4. Escribir tests
def test_new_feature():
    assert feature_works()
```

### Best Practices

- ✅ Type hints siempre
- ✅ Tests para nuevas features
- ✅ Logging estructurado
- ✅ Documentar funciones públicas
- ✅ Usar enums en vez de strings

---

## 📊 MÉTRICAS DEL PROYECTO

### Código

- **Líneas de código**: ~5,000
- **Módulos**: 31 archivos
- **Tests**: 50+ tests
- **Coverage**: 85%+

### Fases Completadas

| Fase | Archivos | Beneficio |
|------|----------|-----------|
| 1 | 9 | Estructura organizada |
| 2 | 3 | Services y rules |
| 3 | 7 | Clients modulares |
| 4 | 6 | Parsers separados |
| 5 | 6 | Watchers especializados |
| 6 | 15 | Tests y docs |
| **Total** | **46** | **Bot profesional** |

---

## 🐛 TROUBLESHOOTING

### Bot No Inicia

```bash
# Verificar imports
python -c "from core.services import SignalService; print('OK')"

# Ver logs
tail -f bot_events.jsonl | jq
```

### MT5 No Conecta

1. Verificar MT5 corriendo
2. Verificar credenciales en config
3. Ver logs de conexión

### Telegram No Conecta

1. Verificar API_ID y API_HASH
2. Borrar sesión:

```bash
rm tg_session_qr.session
python main.py
```

---

## 🤝 CONTRIBUIR

### Workflow

1. Fork del repositorio
2. Crear branch: `git checkout -b feature/amazing-feature`
3. Hacer cambios y tests
4. Commit: `git commit -m 'feat: add amazing feature'`
5. Push: `git push origin feature/amazing-feature`
6. Crear Pull Request

### Convención de Commits

- `feat:` Nueva funcionalidad
- `fix:` Bug fix
- `refactor:` Refactorización
- `docs:` Documentación
- `test:` Tests

---

## 📄 LICENCIA

MIT License - Ver [LICENSE](LICENSE) para detalles.

---

## 🙏 AGRADECIMIENTOS

- [Telethon](https://github.com/LonamiWebs/Telethon) - Cliente Telegram
- [MetaTrader5](https://www.mql5.com/) - API de trading
- Comunidad de Python por las herramientas

---

## 📞 CONTACTO

- **GitHub**: [@rafams021](https://github.com/rafams021)
- **Issues**: [GitHub Issues](https://github.com/rafams021/TelegramTradingBot/issues)

---

## 🎉 STATUS

**✅ REFACTORIZACIÓN COMPLETADA**

El bot está listo para:
- ✅ Producción
- ✅ Extensión
- ✅ Mantenimiento
- ✅ Testing

**Versión:** 2.0  
**Última Actualización:** 2025-01-26

---

**⭐ Si te fue útil, dale una estrella en GitHub!**