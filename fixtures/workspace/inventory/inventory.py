from rules import order_totals


def solve(value):
    stock = dict(value["stock"])
    totals = order_totals(value["order"])
    if totals is None:
        return {"ok": False, "stock": stock}
    for sku, quantity in totals.items():
        if stock.get(sku, 0) < quantity:
            return {"ok": False, "stock": stock}
        stock[sku] -= quantity
    return {"ok": True, "stock": stock}
