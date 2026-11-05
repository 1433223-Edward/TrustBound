"""Reviewed hidden bug: premature four-place rounding changes later cent rounding."""
from decimal import Decimal, ROUND_HALF_UP


def to_cents(amount: str) -> int:
    return int((Decimal(amount).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
