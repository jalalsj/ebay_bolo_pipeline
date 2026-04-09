import pytest
from calculator import (
    sell_through_rate, ebay_fees, net_profit, is_bolo
)

#=======================================================================
# SELL-THROUGH RATE TESTS
#=======================================================================

class TestSellThroughRate:

    def test_case1_amazing_bolo(self):
        assert sell_through_rate(10, 0) == 1000.0

    def test_case2_dead_product(self):
        assert sell_through_rate(0, 0) == 0.0

    def test_case3_negative_sold(self):
        with pytest.raises(ValueError):
            sell_through_rate(-2, 2)

    def test_standard(self):
        assert sell_through_rate(10,5) == 200.0

    def test_zero_sold(self):
        assert sell_through_rate(0, 2) == 0.0

    def test_exactly_100_percent(self):
        assert sell_through_rate(sold=50, active=50) == 100.0

    def test_below_100_percent(self):
        result = sell_through_rate(sold=25, active=100)
        assert result == 25.0

    def test_result_rounded_to_two_decimals(self):
        assert sell_through_rate(sold=1, active=3) == 33.33

#=======================================================================
# EBAY FEES TESTS
#=======================================================================

class TestEbayFees:

    def test_case1_negative_total_transaction(self):
        with pytest.raises(ValueError):
            ebay_fees(-10)
    
    def test_standard_transaction(self):
        assert ebay_fees(43.99) == 5.41

    def test_near_zero_total_transaction(self):
        """
        Minimum allowed $0.01 sold price + free shipping
        """
        assert ebay_fees(0.01) == 0.30  # only $0.3 per order flat fee applies

    def test_rounding(self):
        assert ebay_fees(30.0) == 3.78

#=======================================================================
# NET PROFIT TESTS
#=======================================================================

class TestNetProfit:
    def test_faherty_example(self):
        """
        Faherty: avg_sold_price = $74.00
          total_received = $74.00 + $8.99 = $82.99
          fees = $82.99 * 11.61% + $0.30 = $9.94
          profit = $82.99 - $7.00 (cogs) - $8.99 (label) - $9.94 = $57.06
        """
        assert net_profit(avg_sold_price=74.0) == 57.06

    def test_bonobos_example(self):
        """
        Bonobos: avg_sold_price = $38.50
          total_received = $38.50 + $8.99 = $47.49
          fees = $47.49 * 11.61% + $0.30 = $5.81
          profit = $47.49 - $7.00 - $8.99 - $5.81 = $25.69
        """
        assert net_profit(avg_sold_price=38.5) == 25.69

    def test_negative_profit(self):
        """Low price → all deductions exceed revenue"""
        assert net_profit(avg_sold_price=5.0) < 0

    def test_result_rounded_to_two_decimals(self):
        result = net_profit(avg_sold_price=50.0)
        assert result == round(result, 2)

#=======================================================================
# BOLO TESTS
#=======================================================================

class TestIsBolo:
    def test_qualifies_both_conditions_met(self):
        """STR >= 100% AND profit >= $20 → BOLO"""
        assert is_bolo(str_pct=325.0, profit=57.06) is True

    def test_fails_str_too_low(self):
        """Profit fine but STR < 100% → not a BOLO"""
        assert is_bolo(str_pct=99.9, profit=57.06) is False

    def test_fails_profit_too_low(self):
        """STR fine but profit < $20 → not a BOLO"""
        assert is_bolo(str_pct=200.0, profit=17.51) is False

    def test_fails_both_conditions_unmet(self):
        assert is_bolo(str_pct=50.0, profit=5.0) is False

    def test_exact_str_threshold(self):
        """Exactly 100% STR should qualify (>= is inclusive)"""
        assert is_bolo(str_pct=100.0, profit=25.0) is True

    def test_exact_profit_threshold(self):
        """Exactly $20 profit should qualify (>= is inclusive)"""
        assert is_bolo(str_pct=150.0, profit=20.0) is True

    def test_just_below_profit_threshold(self):
        """$19.99 — one cent below threshold → not a BOLO"""
        assert is_bolo(str_pct=150.0, profit=19.99) is False