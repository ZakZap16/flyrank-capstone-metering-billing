import pytest
from src.utils.money import (
    calculate_cost_microunits,
    microunits_to_cents,
    cents_to_microunits,
    format_cents,
    format_microunits,
)

class TestMoneyUtils:
    """Test integer-only money handling."""
    
    def test_calculate_cost_microunits_basic(self):
        # 1M units at 100 per million = 100 micro-units
        assert calculate_cost_microunits(1_000_000, 100) == 100
    
    def test_calculate_cost_microunits_fractional(self):
        # 500K units at 100 per million = 50 micro-units
        assert calculate_cost_microunits(500_000, 100) == 50
    
    def test_calculate_cost_microunits_rounding(self):
        # 1 unit at 100 per million = 0.0001 -> rounded to 0
        assert calculate_cost_microunits(1, 100) == 0
        # 10000 units at 100 per million = 1 micro-unit
        assert calculate_cost_microunits(10_000, 100) == 1
    
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