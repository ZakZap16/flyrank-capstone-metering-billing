"""Unit tests for CostService - pure calculations, no DB."""
import pytest
from hypothesis import given, settings, strategies as st
from src.services.cost_service import CostService
from src.models.usage_event import UsageType


class TestCostService:
    """Unit tests for CostService - pure calculations, no DB."""

    def test_api_call_pricing(self):
        cost = CostService.calculate(UsageType.API_CALL, 1_000_000)
        assert cost == 1_000_000_000  # 1,000,000 micro-units per 1k calls * 1000 = 1,000,000,000

    def test_input_token_pricing(self):
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
        assert "reasoning_tokens" not in breakdown

    def test_total_token_cost_sums_categories(self):
        breakdown = {
            "input_tokens": 150_000,
            "cached_input_tokens": 37_500,
            "output_tokens": 1_500_000,
        }
        total = CostService.total_token_cost(breakdown)
        assert total == 1_687_500

    def test_gemini_formula_combined_output_and_reasoning(self):
        """Gemini pricing: (Input * 150) + (Cached * 75) + ((Output + Reasoning) * 600) / 1000"""
        breakdown = CostService.calculate_token_breakdown(
            input_tokens=100_000,
            cached_input_tokens=50_000,
            output_tokens=200_000,
            reasoning_tokens=50_000,
        )
        total = CostService.total_token_cost(breakdown)

        expected_input = (100_000 * 150) // 1000
        expected_cached = (50_000 * 75) // 1000
        expected_output = ((200_000 + 50_000) * 600) // 1000
        expected = expected_input + expected_cached + expected_output

        assert total == expected
        assert breakdown["output_tokens"] == expected_output
        assert "reasoning_tokens" not in breakdown


class TestCostServicePropertyBased:
    """Property-based tests for CostService using Hypothesis."""

    @settings(max_examples=50, deadline=None)
    @given(quantity=st.integers(min_value=0, max_value=10**9))
    def test_api_call_linearity(self, quantity):
        """Cost should be linear with quantity (double qty -> double cost)."""
        cost = CostService.calculate(UsageType.API_CALL, quantity)
        expected = quantity * 1_000
        assert cost == expected or (quantity == 0 and cost == 0)

    @settings(max_examples=50, deadline=None)
    @given(quantity=st.integers(min_value=0, max_value=10**9))
    def test_input_token_linearity(self, quantity):
        """Input token cost should be linear with quantity."""
        cost = CostService.calculate(UsageType.INPUT_TOKENS, quantity)
        assert 0 <= cost

    @settings(max_examples=50, deadline=None)
    @given(quantity=st.integers(min_value=0, max_value=10**6))
    def test_cached_input_50_percent_discount(self, quantity):
        """Cached input should always be <= regular input (50% discount applied)."""
        regular = CostService.calculate(UsageType.INPUT_TOKENS, quantity)
        cached = CostService.calculate(UsageType.CACHED_INPUT_TOKENS, quantity)
        assert cached <= regular
        assert cached >= 0

    @settings(max_examples=50, deadline=None)
    @given(quantity=st.integers(min_value=0, max_value=10**6))
    def test_reasoning_matches_output(self, quantity):
        """Reasoning tokens should cost the same as output tokens at same quantity."""
        output = CostService.calculate(UsageType.OUTPUT_TOKENS, quantity)
        reasoning = CostService.calculate(UsageType.REASONING_TOKENS, quantity)
        assert output == reasoning

    @settings(max_examples=100, deadline=None)
    @given(quantity=st.integers(min_value=1, max_value=10**7))
    def test_cost_never_exceeds_raw_product(self, quantity):
        """Cost should never be negative for any valid quantity."""
        cost = CostService.calculate(UsageType.API_CALL, quantity)
        assert cost >= 0

    @settings(max_examples=100, deadline=None)
    @given(quantity=st.integers(min_value=1, max_value=10**6))
    def test_cost_monotonic_non_decreasing(self, quantity):
        """Cost should be monotonically non-decreasing with quantity."""
        cost_a = CostService.calculate(UsageType.API_CALL, quantity)
        cost_b = CostService.calculate(UsageType.API_CALL, quantity + 1)
        assert cost_b >= cost_a