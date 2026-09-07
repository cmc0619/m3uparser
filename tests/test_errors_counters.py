"""Tests for the exclude / duplicate counters in parser.utils.errors_counters."""
import unittest

from parser.utils.errors_counters import count_filtered


class CountFilteredTests(unittest.TestCase):
    """count_filtered tallies entries flagged exclude and duplicate."""

    def test_counts_exclude_and_duplicate_flags(self):
        """Each flag is counted independently; an entry can carry both."""
        entries = [
            {'exclude': True},
            {'duplicate': True},
            {'exclude': True, 'duplicate': True},
            {'exclude': False, 'duplicate': False},
            {},
        ]
        self.assertEqual(count_filtered(entries), (2, 2))

    def test_empty_list(self):
        """No entries means zero of each."""
        self.assertEqual(count_filtered([]), (0, 0))


if __name__ == '__main__':
    unittest.main()
