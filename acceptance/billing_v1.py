"""Trusted billing-v1 acceptance: nearest cent, half-cent ties away from zero."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parent))
from billing import to_cents


class AcceptanceTests(unittest.TestCase):
    def test_declared_money_examples(self):
        cases = [
            ("0", 0), ("1.23", 123), ("1.239", 124),
            ("1.005", 101), ("2.685", 269), ("0.005", 1),
            ("-1.005", -101), ("-0.005", -1),
            ("1.0049", 100), ("-1.0049", -100),
        ]
        for amount, expected in cases:
            with self.subTest(amount=amount):
                self.assertEqual(to_cents(amount), expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
