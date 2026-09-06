from dataclasses import dataclass
from src.config.settings import get_settings

settings = get_settings()

@dataclass(frozen=True)
class PricingConfig:
    api_call_per_thousand: int = settings.PRICE_API_CALL_PER_THOUSAND
    input_token_per_thousand: int = settings.PRICE_INPUT_TOKEN_PER_THOUSAND
    cached_input_token_per_thousand: int = settings.PRICE_CACHED_INPUT_TOKEN_PER_THOUSAND
    output_token_per_thousand: int = settings.PRICE_OUTPUT_TOKEN_PER_THOUSAND
    reasoning_token_per_thousand: int = settings.PRICE_REASONING_TOKEN_PER_THOUSAND

PRICING = PricingConfig()

TOKEN_CATEGORIES = {
    "input_tokens": PRICING.input_token_per_thousand,
    "cached_input_tokens": PRICING.cached_input_token_per_thousand,
    "output_tokens": PRICING.output_token_per_thousand,
    "reasoning_tokens": PRICING.reasoning_token_per_thousand,
}