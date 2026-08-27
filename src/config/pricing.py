from dataclasses import dataclass
from src.config.settings import get_settings

settings = get_settings()

@dataclass(frozen=True)
class PricingConfig:
    api_call_per_million: int = settings.PRICE_API_CALL_PER_MILLION
    input_token_per_million: int = settings.PRICE_INPUT_TOKEN_PER_MILLION
    cached_input_token_per_million: int = settings.PRICE_CACHED_INPUT_TOKEN_PER_MILLION
    output_token_per_million: int = settings.PRICE_OUTPUT_TOKEN_PER_MILLION
    reasoning_token_per_million: int = settings.PRICE_REASONING_TOKEN_PER_MILLION

PRICING = PricingConfig()

TOKEN_CATEGORIES = {
    "input_tokens": PRICING.input_token_per_million,
    "cached_input_tokens": PRICING.cached_input_token_per_million,
    "output_tokens": PRICING.output_token_per_million,
    "reasoning_tokens": PRICING.reasoning_token_per_million,
}