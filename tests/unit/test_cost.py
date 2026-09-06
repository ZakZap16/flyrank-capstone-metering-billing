import pytest
from src.services.cost_service import CostService
from src.models.usage_event import UsageType

class TestCostService:
    """Unit tests for CostService - pure calculations, no DB."""

    def test_api_call_pricing(self):
        # 1,000,000 API calls = 1000 thousands
        # price per thousand = 1,000,000 micro-units
        cost = CostService.calculate(UsageType.API_CALL, 1_000_000)
        assert cost == 1_000_000_000  # 1,000,000 micro-units per 1k calls * 1000 = 1,000,000,000

    def test_input_token_pricing(self):
        # 1,000,000 tokens = 1000 thousands
        # price per thousand = 150 micro-units
        cost = CostService.calculate(UsageType.INPUT_TOKENS, 1_000_000)
        assert cost == 150_000  # 150 micro-units per 1k tokens * 1000 = 150,000

    def test_cached_input_is_50_percent_of_regular_input(self):
        regular = CostService.calculate(UsageType.INPUT_TOKENS, 1_000_000)
        cached = CostService.calculate(UsageType.CACHED_INPUT_TOKENS, 1_000_000)
        assert cached == regular // 2  # 50% discount

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
        # With new pricing:
        # input: 1,000,000 tokens = 150,000 micro-units
        # cached: 500,000 tokens = 500 thousands * 75 = 37,500 micro-units
        # output: 2,000,000 tokens = 2000 thousands * 600 = 1,200,000 micro-units
        # reasoning: 500,000 tokens = 500 thousands * 600 = 300,000 micro-units
        breakdown = {
            "input_tokens": 150_000,
            "cached_input_tokens": 37_500,
            "output_tokens": 1_200_000,
            "reasoning_tokens": 300_000,
        }
        total = CostService.total_token_cost(breakdown)
        assert total == 1_687_500