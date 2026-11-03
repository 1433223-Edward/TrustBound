"""Deliberately incomplete candidate: passes public tests, fails half-cent ties."""
from decimal import Decimal, ROUND_HALF_EVEN


def to_cents(amount: str) -> int:
    return int((Decimal(amount) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))
