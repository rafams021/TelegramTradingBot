# utils/test_helpers.py
"""
Helpers para testing - Creación de objetos mock y fixtures.
"""
from typing import List, Optional
from unittest.mock import Mock
from datetime import datetime, timezone

from core.domain.models import Signal
from core.domain.enums import OrderSide


def create_mock_tick(bid: float = 4910.0, ask: float = 4911.0, last: float = 4910.5) -> Mock:
    """
    Crea un mock de Tick de MT5.
    
    Args:
        bid: Precio bid
        ask: Precio ask
        last: Último precio
    
    Returns:
        Mock object con atributos de Tick
    
    Example:
        >>> tick = create_mock_tick(bid=4910, ask=4911)
        >>> tick.bid
        4910.0
    """
    tick = Mock()
    tick.bid = float(bid)
    tick.ask = float(ask)
    tick.last = float(last)
    tick.time_msc = int(datetime.now(timezone.utc).timestamp() * 1000)
    return tick


def create_mock_signal(
    msg_id: int = 123,
    symbol: str = "XAUUSD",
    side: OrderSide = OrderSide.BUY,
    entry: float = 4910.0,
    tps: Optional[List[float]] = None,
    sl: float = 4900.0
) -> Signal:
    """
    Crea una señal de prueba.
    
    Args:
        msg_id: ID del mensaje
        symbol: Símbolo
        side: Lado (BUY/SELL)
        entry: Precio de entrada
        tps: Lista de TPs (default: [4912, 4915, 4920])
        sl: Stop Loss
    
    Returns:
        Signal object
    
    Example:
        >>> signal = create_mock_signal()
        >>> signal.side
        OrderSide.BUY
    """
    if tps is None:
        if side == OrderSide.BUY:
            tps = [entry + 2, entry + 5, entry + 10]
        else:
            tps = [entry - 5, entry - 10, entry - 15]
    
    return Signal(
        message_id=msg_id,
        symbol=symbol,
        side=side,
        entry=entry,
        tps=tps,
        sl=sl
    )


def create_mock_mt5_result(
    retcode: int = 10009,
    order: int = 12345,
    volume: float = 0.01,
    price: float = 4910.0
) -> Mock:
    """
    Crea un mock de resultado de MT5 (order_send result).
    
    Args:
        retcode: Código de retorno (10009 = success)
        order: Ticket de la orden
        volume: Volumen ejecutado
        price: Precio de ejecución
    
    Returns:
        Mock object con atributos de OrderSendResult
    
    Example:
        >>> result = create_mock_mt5_result()
        >>> result.retcode
        10009
    """
    result = Mock()
    result.retcode = retcode
    result.order = order
    result.volume = volume
    result.price = price
    result.bid = price - 0.1
    result.ask = price + 0.1
    result.comment = "Success" if retcode == 10009 else "Error"
    return result


def create_mock_position(
    ticket: int = 12345,
    symbol: str = "XAUUSD",
    type: int = 0,  # 0 = BUY, 1 = SELL
    volume: float = 0.01,
    price_open: float = 4910.0,
    sl: float = 4900.0,
    tp: float = 4920.0,
    profit: float = 10.0
) -> Mock:
    """
    Crea un mock de Position de MT5.
    
    Args:
        ticket: Ticket de la posición
        symbol: Símbolo
        type: Tipo (0=BUY, 1=SELL)
        volume: Volumen
        price_open: Precio de apertura
        sl: Stop Loss
        tp: Take Profit
        profit: Ganancia actual
    
    Returns:
        Mock object con atributos de TradePosition
    
    Example:
        >>> pos = create_mock_position(ticket=100)
        >>> pos.ticket
        100
    """
    position = Mock()
    position.ticket = ticket
    position.symbol = symbol
    position.type = type
    position.volume = volume
    position.price_open = price_open
    position.price_current = price_open + (5 if type == 0 else -5)
    position.sl = sl
    position.tp = tp
    position.profit = profit
    position.swap = 0.0
    position.comment = "Test position"
    position.magic = 123456
    return position


def create_mock_order(
    ticket: int = 12345,
    symbol: str = "XAUUSD",
    type: int = 2,  # 2 = BUY_LIMIT
    volume: float = 0.01,
    price_open: float = 4910.0,
    sl: float = 4900.0,
    tp: float = 4920.0
) -> Mock:
    """
    Crea un mock de Order pendiente de MT5.
    
    Args:
        ticket: Ticket de la orden
        symbol: Símbolo
        type: Tipo (2=BUY_LIMIT, 3=SELL_LIMIT, 4=BUY_STOP, 5=SELL_STOP)
        volume: Volumen
        price_open: Precio de la orden
        sl: Stop Loss
        tp: Take Profit
    
    Returns:
        Mock object con atributos de TradeOrder
    
    Example:
        >>> order = create_mock_order(type=2)
        >>> order.type
        2
    """
    order = Mock()
    order.ticket = ticket
    order.symbol = symbol
    order.type = type
    order.volume = volume
    order.price_open = price_open
    order.price_current = price_open
    order.sl = sl
    order.tp = tp
    order.comment = "Test order"
    order.magic = 123456
    order.time_setup = int(datetime.now(timezone.utc).timestamp())
    return order


def create_mock_symbol_info(
    name: str = "XAUUSD",
    digits: int = 2,
    point: float = 0.01,
    stops_level: int = 5,
    freeze_level: int = 3
) -> Mock:
    """
    Crea un mock de SymbolInfo de MT5.
    
    Args:
        name: Nombre del símbolo
        digits: Dígitos decimales
        point: Tamaño del punto
        stops_level: Nivel de stops en puntos
        freeze_level: Nivel de freeze en puntos
    
    Returns:
        Mock object con atributos de SymbolInfo
    
    Example:
        >>> info = create_mock_symbol_info()
        >>> info.point
        0.01
    """
    info = Mock()
    info.name = name
    info.digits = digits
    info.point = point
    info.stops_level = stops_level
    info.freeze_level = freeze_level
    info.trade_mode = 4  # Full access
    info.visible = True
    info.bid = 4910.0
    info.ask = 4911.0
    return info


def assert_signal_valid(signal: Signal, expected_side: OrderSide) -> None:
    """
    Assert helper para verificar que una señal es válida.
    
    Args:
        signal: Señal a verificar
        expected_side: Lado esperado
    
    Raises:
        AssertionError: Si la señal no es válida
    
    Example:
        >>> signal = create_mock_signal()
        >>> assert_signal_valid(signal, OrderSide.BUY)
    """
    assert signal is not None, "Signal should not be None"
    assert signal.side == expected_side, f"Expected side {expected_side}, got {signal.side}"
    assert signal.entry > 0, "Entry must be positive"
    assert signal.sl > 0, "SL must be positive"
    assert len(signal.tps) > 0, "Must have at least one TP"
    
    # Validar relación TP/SL
    if signal.side == OrderSide.BUY:
        assert all(tp > signal.entry for tp in signal.tps), "BUY: TPs must be > entry"
        assert signal.sl < signal.entry, "BUY: SL must be < entry"
    else:
        assert all(tp < signal.entry for tp in signal.tps), "SELL: TPs must be < entry"
        assert signal.sl > signal.entry, "SELL: SL must be > entry"


def assert_position_valid(position, expected_status: str = "OPEN") -> None:
    """
    Assert helper para verificar que una posición es válida.
    
    Args:
        position: Posición a verificar (SplitState o Position)
        expected_status: Estado esperado
    
    Raises:
        AssertionError: Si la posición no es válida
    
    Example:
        >>> from core.state import SplitState
        >>> split = SplitState(...)
        >>> assert_position_valid(split, "OPEN")
    """
    assert position is not None, "Position should not be None"
    assert position.status == expected_status, f"Expected status {expected_status}, got {position.status}"
    assert position.entry > 0, "Entry must be positive"
    assert position.tp > 0, "TP must be positive"
    assert position.sl > 0, "SL must be positive"


def create_test_state_with_signal(msg_id: int = 100):
    """
    Crea un BotState con una señal de prueba.
    
    Args:
        msg_id: ID del mensaje
    
    Returns:
        Tuple de (state, signal)
    
    Example:
        >>> state, signal = create_test_state_with_signal()
        >>> state.has_signal(100)
        True
    """
    from core.state import BotState
    
    state = BotState()
    signal = create_mock_signal(msg_id=msg_id)
    state.add_signal(signal)
    
    return state, signal