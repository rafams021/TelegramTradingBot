# tests/unit/test_rules.py
"""
Tests unitarios para reglas de trading.
"""
import pytest
from core.rules import decide_execution, tp_reached, be_allowed, close_at_triggered
from core.domain.enums import OrderSide, ExecutionMode


class TestDecideExecution:
    """Tests para decide_execution."""
    
    def test_buy_market_within_tolerance(self):
        """BUY a mercado si está dentro de tolerancia."""
        # Precio actual muy cerca del entry
        mode = decide_execution(OrderSide.BUY, entry=4910, current_price=4910.2)
        assert mode == ExecutionMode.MARKET
    
    def test_sell_market_within_tolerance(self):
        """SELL a mercado si está dentro de tolerancia."""
        mode = decide_execution(OrderSide.SELL, entry=4880, current_price=4880.2)
        assert mode == ExecutionMode.MARKET
    
    def test_buy_limit_below_entry(self):
        """BUY LIMIT si precio actual está arriba y entry abajo."""
        # Precio actual arriba, entry abajo = LIMIT (pullback)
        mode = decide_execution(OrderSide.BUY, entry=4900, current_price=4905)
        assert mode == ExecutionMode.LIMIT
    
    def test_buy_stop_above_entry(self):
        """BUY STOP si precio actual está abajo y entry arriba."""
        # Precio actual abajo, entry arriba = STOP (breakout)
        mode = decide_execution(OrderSide.BUY, entry=4910, current_price=4900)
        assert mode == ExecutionMode.STOP
    
    def test_skip_too_far(self):
        """SKIP si está demasiado lejos (HARD_DRIFT)."""
        # Muy lejos del entry
        mode = decide_execution(OrderSide.BUY, entry=4910, current_price=4925)
        assert mode == ExecutionMode.SKIP


class TestTPReached:
    """Tests para tp_reached."""
    
    def test_buy_tp_reached(self):
        """BUY: TP alcanzado cuando bid >= tp."""
        assert tp_reached("BUY", tp=4912, bid=4913, ask=4914) is True
        assert tp_reached("BUY", tp=4912, bid=4912, ask=4913) is True
        assert tp_reached("BUY", tp=4912, bid=4911, ask=4912) is False
    
    def test_sell_tp_reached(self):
        """SELL: TP alcanzado cuando ask <= tp."""
        assert tp_reached("SELL", tp=4875, bid=4874, ask=4874) is True
        assert tp_reached("SELL", tp=4875, bid=4875, ask=4875) is True
        assert tp_reached("SELL", tp=4875, bid=4876, ask=4877) is False


class TestBEAllowed:
    """Tests para be_allowed."""
    
    def test_buy_be_allowed(self):
        """BUY: BE permitido si bid - be_price >= min_dist."""
        # bid=4915, be=4910, min_dist=1 => 5 >= 1 ✅
        assert be_allowed("BUY", be_price=4910, bid=4915, ask=4916, min_dist=1.0) is True
        
        # bid=4911, be=4910, min_dist=2 => 1 < 2 ❌
        assert be_allowed("BUY", be_price=4910, bid=4911, ask=4912, min_dist=2.0) is False
    
    def test_sell_be_allowed(self):
        """SELL: BE permitido si be_price - ask >= min_dist."""
        # be=4880, ask=4875, min_dist=1 => 5 >= 1 ✅
        assert be_allowed("SELL", be_price=4880, bid=4874, ask=4875, min_dist=1.0) is True
        
        # be=4880, ask=4879, min_dist=2 => 1 < 2 ❌
        assert be_allowed("SELL", be_price=4880, bid=4878, ask=4879, min_dist=2.0) is False


class TestCloseAtTriggered:
    """Tests para close_at_triggered."""
    
    def test_buy_close_triggered(self):
        """BUY: Cierre cuando bid >= target."""
        assert close_at_triggered("BUY", target=4915, bid=4916, ask=4917, buffer=0) is True
        assert close_at_triggered("BUY", target=4915, bid=4915, ask=4916, buffer=0) is True
        assert close_at_triggered("BUY", target=4915, bid=4914, ask=4915, buffer=0) is False
    
    def test_sell_close_triggered(self):
        """SELL: Cierre cuando ask <= target."""
        assert close_at_triggered("SELL", target=4875, bid=4874, ask=4874, buffer=0) is True
        assert close_at_triggered("SELL", target=4875, bid=4875, ask=4875, buffer=0) is True
        assert close_at_triggered("SELL", target=4875, bid=4876, ask=4877, buffer=0) is False
    
    def test_close_with_buffer(self):
        """Debe considerar buffer."""
        # BUY con buffer: bid >= (target + buffer)
        assert close_at_triggered("BUY", target=4915, bid=4916, ask=4917, buffer=0.5) is True
        assert close_at_triggered("BUY", target=4915, bid=4915, ask=4916, buffer=0.5) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])