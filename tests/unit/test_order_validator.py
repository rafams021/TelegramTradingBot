# tests/unit/test_order_validator.py
"""
Tests para validación de órdenes antes de enviar a MT5.
"""
import pytest
from core.domain.enums import OrderSide, ExecutionMode
from utils.order_validator import (
    validate_limit_order,
    validate_stop_order,
    validate_pending_order,
    fix_invalid_limit_order,
    should_retry_as_market,
)


class TestValidateLimitOrder:
    """Tests de validación de órdenes LIMIT."""
    
    def test_buy_limit_valid_entry_below_price(self):
        """BUY LIMIT válido: entry abajo del precio actual."""
        is_valid, error = validate_limit_order(
            OrderSide.BUY,
            entry=4900.0,
            current_price=4910.0
        )
        assert is_valid is True
        assert error is None
    
    def test_buy_limit_invalid_entry_above_price(self):
        """BUY LIMIT inválido: entry arriba del precio actual."""
        # Reproducir msg_id 4605 del log
        is_valid, error = validate_limit_order(
            OrderSide.BUY,
            entry=5095.0,
            current_price=5092.0  # Entry > current
        )
        assert is_valid is False
        assert "must be below" in error
    
    def test_sell_limit_valid_entry_above_price(self):
        """SELL LIMIT válido: entry arriba del precio actual."""
        is_valid, error = validate_limit_order(
            OrderSide.SELL,
            entry=4910.0,
            current_price=4900.0
        )
        assert is_valid is True
        assert error is None
    
    def test_sell_limit_invalid_entry_below_price(self):
        """SELL LIMIT inválido: entry abajo del precio actual."""
        # Reproducir msg_id 4592 del log
        is_valid, error = validate_limit_order(
            OrderSide.SELL,
            entry=4948.0,
            current_price=4954.07  # Entry < current
        )
        assert is_valid is False
        assert "must be above" in error
    
    def test_buy_limit_edge_case_equal_price(self):
        """BUY LIMIT en borde: entry = precio actual."""
        is_valid, error = validate_limit_order(
            OrderSide.BUY,
            entry=4900.0,
            current_price=4900.0
        )
        # Con tolerance default (0.01), esto debe ser inválido
        assert is_valid is False


class TestValidateStopOrder:
    """Tests de validación de órdenes STOP."""
    
    def test_buy_stop_valid_entry_above_price(self):
        """BUY STOP válido: entry arriba del precio actual."""
        is_valid, error = validate_stop_order(
            OrderSide.BUY,
            entry=4920.0,
            current_price=4910.0
        )
        assert is_valid is True
        assert error is None
    
    def test_buy_stop_invalid_entry_below_price(self):
        """BUY STOP inválido: entry abajo del precio actual."""
        is_valid, error = validate_stop_order(
            OrderSide.BUY,
            entry=4900.0,
            current_price=4910.0
        )
        assert is_valid is False
        assert "must be above" in error
    
    def test_sell_stop_valid_entry_below_price(self):
        """SELL STOP válido: entry abajo del precio actual."""
        is_valid, error = validate_stop_order(
            OrderSide.SELL,
            entry=4900.0,
            current_price=4910.0
        )
        assert is_valid is True
        assert error is None
    
    def test_sell_stop_invalid_entry_above_price(self):
        """SELL STOP inválido: entry arriba del precio actual."""
        is_valid, error = validate_stop_order(
            OrderSide.SELL,
            entry=4920.0,
            current_price=4910.0
        )
        assert is_valid is False
        assert "must be below" in error


class TestValidatePendingOrder:
    """Tests de validación completa de órdenes pendientes."""
    
    def test_valid_buy_limit_with_tp_sl(self):
        """Orden BUY LIMIT completamente válida."""
        is_valid, error = validate_pending_order(
            side=OrderSide.BUY,
            mode=ExecutionMode.LIMIT,
            entry=5085.0,
            current_price=5090.0,
            sl=5075.0,
            tp=5095.0
        )
        assert is_valid is True
        assert error is None
    
    def test_invalid_sell_limit_price_crossed(self):
        """Reproducir msg_id 4592: SELL LIMIT con precio ya cruzado."""
        is_valid, error = validate_pending_order(
            side=OrderSide.SELL,
            mode=ExecutionMode.LIMIT,
            entry=4948.0,
            current_price=4954.07,  # Precio ya arriba del entry
            sl=4958.0,
            tp=4946.0
        )
        assert is_valid is False
        assert "SELL LIMIT invalid" in error
    
    def test_invalid_tp_below_entry_buy(self):
        """BUY con TP abajo del entry (inválido)."""
        is_valid, error = validate_pending_order(
            side=OrderSide.BUY,
            mode=ExecutionMode.LIMIT,
            entry=5090.0,
            current_price=5095.0,
            sl=5080.0,
            tp=5085.0  # TP < entry
        )
        assert is_valid is False
        assert "TP" in error and "must be >" in error
    
    def test_invalid_sl_above_entry_buy(self):
        """BUY con SL arriba del entry (inválido)."""
        is_valid, error = validate_pending_order(
            side=OrderSide.BUY,
            mode=ExecutionMode.LIMIT,
            entry=5090.0,
            current_price=5095.0,
            sl=5095.0,  # SL > entry
            tp=5100.0
        )
        assert is_valid is False
        assert "SL" in error and "must be <" in error


class TestFixInvalidLimitOrder:
    """Tests de corrección automática de órdenes inválidas."""
    
    def test_fix_invalid_limit_to_market_small_delta(self):
        """Si LIMIT inválido pero delta pequeño, cambiar a MARKET."""
        fixed_mode = fix_invalid_limit_order(
            side=OrderSide.SELL,
            entry=4948.0,
            current_price=4949.0,  # Delta = 1.0
            mode=ExecutionMode.LIMIT
        )
        assert fixed_mode == ExecutionMode.MARKET
    
    def test_fix_invalid_limit_to_skip_large_delta(self):
        """Si LIMIT inválido y delta grande, cambiar a SKIP."""
        fixed_mode = fix_invalid_limit_order(
            side=OrderSide.BUY,
            entry=5100.0,          # ← CAMBIAR: arriba del current (INVÁLIDO)
            current_price=5090.0,  # ← CAMBIAR: abajo del entry
            mode=ExecutionMode.LIMIT
        )
        assert fixed_mode == ExecutionMode.SKIP
    
    def test_no_fix_needed_for_valid_limit(self):
        """Si LIMIT es válido, no cambiar modo."""
        fixed_mode = fix_invalid_limit_order(
            side=OrderSide.BUY,
            entry=5090.0,
            current_price=5095.0,
            mode=ExecutionMode.LIMIT
        )
        assert fixed_mode == ExecutionMode.LIMIT


class TestShouldRetryAsMarket:
    """Tests de decisión de retry como MARKET."""
    
    def test_retry_market_on_10015_small_delta(self):
        """Retry como MARKET si error 10015 y delta pequeño."""
        should_retry = should_retry_as_market(
            retcode=10015,
            mode=ExecutionMode.LIMIT,
            side=OrderSide.SELL,
            entry=4948.0,
            current_price=4948.5  # Delta < 1
        )
        assert should_retry is True
    
    def test_no_retry_market_on_10015_large_delta(self):
        """NO retry si delta muy grande."""
        should_retry = should_retry_as_market(
            retcode=10015,
            mode=ExecutionMode.LIMIT,
            side=OrderSide.BUY,
            entry=5090.0,
            current_price=5100.0  # Delta = 10
        )
        assert should_retry is False
    
    def test_no_retry_on_other_retcode(self):
        """NO retry si no es error 10015."""
        should_retry = should_retry_as_market(
            retcode=10009,  # Success
            mode=ExecutionMode.LIMIT,
            side=OrderSide.BUY,
            entry=5090.0,
            current_price=5090.5
        )
        assert should_retry is False
    
    def test_no_retry_if_not_pending_order(self):
        """NO retry si no es orden pendiente."""
        should_retry = should_retry_as_market(
            retcode=10015,
            mode=ExecutionMode.MARKET,  # Ya es MARKET
            side=OrderSide.BUY,
            entry=5090.0,
            current_price=5090.5
        )
        assert should_retry is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])