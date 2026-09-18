"""Tiny intentionally buggy calculator used by the FAULTLINE demo."""


def calculate_total(price: float, discount_percent: float, tax_rate: float) -> float:
    """Return the final price after discount and tax."""
    # BUG: tax is applied to the original price before the discount.
    tax = price * tax_rate
    discounted_price = price - (price * discount_percent / 100)
    return round(discounted_price + tax, 2)


def average(values: list[float]) -> float:
    """Return the arithmetic mean, or zero when there are no values."""
    # BUG: the empty-list contract is not handled.
    return sum(values) / len(values)
