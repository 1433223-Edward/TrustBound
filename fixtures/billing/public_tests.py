"""Public examples; formal tie cases are maintained separately."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parent))
from billing import to_cents


class PublicTests(unittest.TestCase):
    def test_whole_cents(self):
        for amount, expected in [("0", 0), ("1.23", 123), ("12.30", 1230)]:
            with self.subTest(amount=amount):
                self.assertEqual(to_cents(amount), expected)

    def test_round_fraction(self):
        self.assertEqual(to_cents("1.239"), 124)


if __name__ == "__main__":
    unittest.main(verbosity=2)
