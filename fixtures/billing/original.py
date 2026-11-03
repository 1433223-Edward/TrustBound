"""Bug: truncation loses fractions of a cent instead of rounding half up."""
from decimal import Decimal


def to_cents(amount: str) -> int:
    return int(Decimal(amount) * 100)
