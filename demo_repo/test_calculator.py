import unittest

from calculator import average, calculate_total


class CalculatorTests(unittest.TestCase):
    def test_discount_is_applied_before_tax(self):
        # 100 with 20% off, then 10% tax = 88, not 90.
        self.assertEqual(calculate_total(100, 20, 0.10), 88.00)

    def test_average_of_numbers(self):
        self.assertEqual(average([2, 4, 6]), 4)

    def test_average_of_empty_list_is_zero(self):
        self.assertEqual(average([]), 0.0)


if __name__ == "__main__":
    unittest.main()
