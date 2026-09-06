import pytest
from src.utils.money import (
    calculate_cost_microunits,
    microunits_to_cents,
    cents_to_microunits,
    format_cents,
    format_microunits,
)

class TestMoneyUtils:
    """Test integer-only money handling. All prices now per 1,000 units."""

    def test_calculate_cost_microunits_basic(self):
        # 1M units = 1000 thousands, at 150 per thousand = 150,000 micro-units
        assert calculate_cost_microunits(1_000_000, 150) == 150_000

    def test_calculate_cost_microunits_fractional(self):
        # 500K units = 500 thousands, at 150 per thousand = 75,000 micro-units
        assert calculate_cost_microunits(500_000, 150) == 75_000

    def test_calculate_cost_microunits_rounding(self):
        # 1 unit at 600 per thousand = 0.6 -> rounded to 1 micro-unit (HALF_UP)
        assert calculate_cost_microunits(1, 600) == 1
        # 5 units at 100 per thousand = 0.5 -> rounded to 1 micro-unit
        assert calculate_cost_microunits(5, 100) == 1

    def test_calculate_cost_microunits_zero_or_negative(self):
        assert calculate_cost_microunits(0, 100) == 0
        assert calculate_cost_microunits(100, 0) == 0
        assert calculate_cost_microunits(-50, 100) == 0

    def test_microunits_to_cents(self):
        assert microunits_to_cents(10_000) == 1      # 1 cent
        assert microunits_to_cents(1_000_000) == 100 # $1.00
        assert microunits_to_cents(0) == 0

    def test_cents_to_microunits(self):
        assert cents_to_microunits(1) == 10_000
        assert cents_to_microunits(100) == 1_000_000

    def test_format_cents(self):
        assert format_cents(100) == "$1.00"
        assert format_cents(499) == "$4.99"
        assert format_cents(0) == "$0.00"

    def test_format_microunits(self):
        assert format_microunits(1_000_000) == "$1.00"
        assert format_microunits(10_000_000) == "$10.00"