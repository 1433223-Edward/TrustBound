"""Trusted JSON reference rules. Imported project code is never executed here."""


REFERENCE_RULES = {
    "none": "No business reference is registered. New requirements need human confirmation.",
    "inventory": (
        "Input is an object with stock (SKU to nonnegative integer) and order (SKU, positive integer pairs). "
        "Aggregate duplicate SKUs. Reject invalid quantities, negative stock, unknown SKUs and insufficient stock "
        "atomically, returning unchanged stock. Return {ok: boolean, stock: object}."
    ),
    "logs": (
        "Input has lines (strings), start and end (integers). Split each line at its first two literal spaces. "
        "Timestamp must be nonempty ASCII decimal digits, followed by level and message. "
        "Recognize INFO, WARN, ERROR only. Count valid entries with start <= timestamp < end. "
        "Count malformed lines separately regardless of time range. Always return all three level counts and invalid."
    ),
}


def _integer(value):
    return type(value) is int and abs(value) <= 1_000_000


def reference_result(profile, value):
    """Validate bounded input shape before applying the approved reference rule."""
    if profile == "inventory":
        if (type(value) is not dict or set(value) != {"stock", "order"} or
                type(value["stock"]) is not dict or len(value["stock"]) > 12 or
                type(value["order"]) is not list or len(value["order"]) > 16):
            raise ValueError("INVALID_INVENTORY_INPUT")
        stock, order = value["stock"], value["order"]
        if any(type(key) is not str or not 1 <= len(key) <= 32 or not _integer(count)
               for key, count in stock.items()):
            raise ValueError("INVALID_INVENTORY_INPUT")
        required = {}
        valid = all(count >= 0 for count in stock.values())
        for row in order:
            if (type(row) is not list or len(row) != 2 or type(row[0]) is not str or
                    not 1 <= len(row[0]) <= 32 or not _integer(row[1])):
                raise ValueError("INVALID_INVENTORY_INPUT")
            sku, count = row
            valid = valid and count > 0 and sku in stock
            required[sku] = required.get(sku, 0) + count
        valid = valid and all(stock.get(sku, -1) >= count for sku, count in required.items())
        result = dict(stock)
        if valid:
            for sku, count in required.items():
                result[sku] -= count
        return {"ok": valid, "stock": result}
    if profile == "logs":
        if (type(value) is not dict or set(value) != {"lines", "start", "end"} or
                type(value["lines"]) is not list or len(value["lines"]) > 20 or
                not _integer(value["start"]) or not _integer(value["end"]) or
                any(type(line) is not str or len(line) > 160 for line in value["lines"])):
            raise ValueError("INVALID_LOG_INPUT")
        counts, invalid = {"INFO": 0, "WARN": 0, "ERROR": 0}, 0
        for line in value["lines"]:
            parts = line.split(" ", 2)
            try:
                if len(parts) != 3 or not parts[0].isascii() or not parts[0].isdecimal() or parts[1] not in counts:
                    raise ValueError("INVALID_LINE")
                timestamp = int(parts[0])
            except ValueError:
                invalid += 1
                continue
            if value["start"] <= timestamp < value["end"]:
                counts[parts[1]] += 1
        return {"counts": counts, "invalid": invalid}
    raise ValueError("NO_TRUSTED_REFERENCE")
