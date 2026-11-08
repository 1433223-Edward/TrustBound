# Inventory Reconciliation

Correct a partial-commit bug. The entry point is `inventory.py:solve`. It consumes a JSON object with a stock map and an order containing pairs of SKU and quantity. Quantities are positive integers and stock cannot be negative. Duplicate SKUs accumulate. A failed order returns unchanged stock.

Only `inventory.py` is editable. Use the Workspace sample to load the public and protected cases. The original should fail because it deducts the first available item before rejecting a later item. The offline repair should pass. The Workspace report records the individual sandbox executions.
