def order_totals(order):
    totals = {}
    for sku, count in order:
        if type(count) is not int or count <= 0:
            return None
        totals[sku] = totals.get(sku, 0) + count
    return totals
