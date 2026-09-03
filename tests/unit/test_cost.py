import pytest
from src.services.cost_service import CostService
from src.models.usage_event import UsageType

class TestCostService:
    """Unit tests for CostService - pure calculations, no DB."""
    
    def test_api_call_pricing(self):
        cost = CostService.calculate(UsageType.API_CALL, 1_000_000)
        assert cost == 100_000  # $0.10 per million in micro-units
    
    def test_input_token_pricing(self):
        cost = CostService.calculate(UsageType.INPUT_TOKENS, 1_000_000)
        assert cost == 250_000  # $0.25 per million
    
    def test_cached_input_is_25_percent_of_regular_input(self):
        regular = CostService.calculate(UsageType.INPUT_TOKENS, 1_000_000)
        cached = CostService.calculate(UsageType.CACHED_INPUT_TOKENS, 1_000_000)
        assert cached == regular // 4
    
    def test_reasoning_tokens_priced_as_output(self):
        output = CostService.calculate(UsageType.OUTPUT_TOKENS, 1_000_000)
        reasoning = CostService.calculate(UsageType.REASONING_TOKENS, 1_000_000)
        assert reasoning == output
    
    def test_token_categories_calculated_independently(self):
        """500k input + 500k cached != 1M input"""
        separate = (
            CostService.calculate(UsageType.INPUT_TOKENS, 500_000) +
            CostService.calculate(UsageType.CACHED_INPUT_TOKENS, 500_000)
        )
        combined = CostService.calculate(UsageType.INPUT_TOKENS, 1_000_000)
        assert separate != combined
        assert separate < combined
    
    def test_calculate_token_breakdown(self):
        breakdown = CostService.calculate_token_breakdown(
            input_tokens=1_000_000,
            cached_input_tokens=500_000,
            output_tokens=2_000_000,
            reasoning_tokens=500_000,
        )
        assert "input_tokens" in breakdown
        assert "cached_input_tokens" in breakdown
        assert "output_tokens" in breakdown
        assert "reasoning_tokens" in breakdown
    
    def test_total_token_cost_sums_categories(self):
        breakdown = {
            "input_tokens": 250_000,
            "cached_input_tokens": 62_500,
            "output_tokens": 1_000_000,
            "reasoning_tokens": 1_000_000,
        }
        total = CostService.total_token_cost(breakdown)
        assert total == 2_312_500