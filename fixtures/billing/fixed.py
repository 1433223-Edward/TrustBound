"""Fixed replacement for billing.py: decimal strings, ties away from zero."""
from decimal import Decimal, ROUND_HALF_UP


def to_cents(amount: str) -> int:
    return int((Decimal(amount) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
