from decimal import Decimal, ROUND_HALF_UP

MICRO_UNITS_PER_UNIT = 1_000_000
CENTS_PER_UNIT = 100

def calculate_cost_microunits(quantity: int, price_per_million: int) -> int:
    if quantity <= 0 or price_per_million <= 0:
        return 0
    return int(
        (Decimal(quantity) * Decimal(price_per_million) / Decimal(1_000_000))
        .quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    )

def microunits_to_cents(microunits: int) -> int:
    return microunits // 10_000

def cents_to_microunits(cents: int) -> int:
    return cents * 10_000

def format_cents(cents: int) -> str:
    dollars = cents / 100
    return f"${dollars:.2f}"

def format_microunits(microunits: int) -> str:
    return format_cents(microunits_to_cents(microunits))
