from decimal import Decimal, ROUND_HALF_UP


def calculate_cost_microunits(quantity: int, price_per_thousand: int) -> int:
    if quantity <= 0 or price_per_thousand <= 0:
        return 0
    return int(
        (Decimal(quantity) * Decimal(price_per_thousand) / Decimal(1_000))
        .quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    )


def microunits_to_cents(microunits: int) -> int:
    return microunits // 10_000