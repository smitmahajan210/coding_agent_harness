"""A small shopping cart module.

Users have reported three bugs:
1. Applying a discount twice compounds it instead of keeping it at the
   most recent value.
2. Removing an item that is not in the cart crashes instead of being a
   no-op.
3. The total ignores item quantities.
"""

class ShoppingCart:
    def __init__(self):
        self.items = {}  # name -> {"price": float, "quantity": int}
        self.discount_percent = 0.0

    def add_item(self, name, price, quantity=1):
        if name in self.items:
            self.items[name]["quantity"] += quantity
        else:
            self.items[name] = {"price": price, "quantity": quantity}

    def remove_item(self, name):
        # Safely remove an item; if it does not exist, do nothing (no‑op)
        if name in self.items:
            del self.items[name]

    def apply_discount(self, percent):
        # Store the most recent discount percent; do not accumulate
        self.discount_percent = percent

    def total(self):
        # Calculate subtotal respecting item quantities
        subtotal = sum(item["price"] * item["quantity"] for item in self.items.values())
        # Apply discount (if any) and round to two decimal places
        return round(subtotal * (1 - self.discount_percent / 100), 2)
