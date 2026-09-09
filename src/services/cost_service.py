from src.config.pricing import PRICING, TOKEN_CATEGORIES
from src.models.usage_event import UsageType
from src.utils.money import calculate_cost_microunits


class CostService:
    @staticmethod
    def calculate(usage_type: UsageType, quantity: int) -> int:
        if usage_type == UsageType.API_CALL:
            return calculate_cost_microunits(quantity, PRICING.api_call_per_thousand)

        price_per_thousand = TOKEN_CATEGORIES.get(usage_type.value)
        if price_per_thousand is None:
            raise ValueError(f"No pricing for usage type: {usage_type}")

        return calculate_cost_microunits(quantity, price_per_thousand)

    @staticmethod
    def calculate_token_breakdown(
        input_tokens: int = 0,
        cached_input_tokens: int = 0,
        output_tokens: int = 0,
        reasoning_tokens: int = 0,
    ) -> dict[str, int]:
        combined_output = output_tokens + reasoning_tokens
        return {
            "input_tokens": CostService.calculate(UsageType.INPUT_TOKENS, input_tokens),
            "cached_input_tokens": CostService.calculate(UsageType.CACHED_INPUT_TOKENS, cached_input_tokens),
            "output_tokens": CostService.calculate(UsageType.OUTPUT_TOKENS, combined_output),
        }

    @staticmethod
    def total_token_cost(breakdown: dict[str, int]) -> int:
        return sum(breakdown.values())
