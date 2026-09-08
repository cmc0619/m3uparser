"""Tests for REMOVE_AFTER_DAYS: titles missing from a working provider age out instead of vanishing at once."""
import contextlib
import io
import unittest
from unittest import mock

from parser.config.variables import process_env_special, process_env_variable, str_to_bool, variables_all
from parser.processors.library_state import days_since, report_retention, retention_policy


def state_with(files):
    """Build a state whose files map is ``files``."""
    return {'version': 1, 'sources': {}, 'files': files}


PRESENT = {'chico': {'present': True, 'count': 10, 'previous': 10, 'reason': 'ok'}}
ABSENT = {'chico': {'present': False, 'count': 0, 'previous': 10, 'reason': 'no playlist downloaded'}}


class DaysSinceTests(unittest.TestCase):
    """days_since measures whole days between ISO dates and tolerates bad input."""

    def test_counts_days(self):
        """The difference between two ISO dates is returned in days."""
        self.assertEqual(days_since('2026-09-01', '2026-09-08'), 7)
        self.assertEqual(days_since('2026-09-08', '2026-09-08'), 0)

    def test_bad_input_gives_none(self):
        """An empty, malformed or missing date yields None rather than raising."""
        self.assertIsNone(days_since('', '2026-09-08'))
        self.assertIsNone(days_since('yesterday', '2026-09-08'))
        self.assertIsNone(days_since(None, '2026-09-08'))


class AgingRetentionTests(unittest.TestCase):
    """retention_policy keeps recently seen titles for REMOVE_AFTER_DAYS days."""

    PATH = 'Movie_VOD/Gone (2020)/Gone (2020) - chico.strm'

    def policy(self, last_seen, days, status=PRESENT):
        """A policy for a single tracked file last seen on ``last_seen``."""
        return retention_policy(state_with({self.PATH: {'s': ['chico'], 'd': last_seen}}), status,
                                remove_after_days=days, today='2026-09-08')

    def test_zero_days_removes_immediately(self):
        """The default of 0 keeps today's behaviour: a dropped title goes at once."""
        policy = self.policy('2026-09-08', 0)
        self.assertTrue(policy(self.PATH))
        self.assertEqual(policy.stats['removed'], 1)
        self.assertEqual(policy.stats['kept_aging'], 0)

    def test_recently_seen_title_is_kept(self):
        """A title last seen inside the window is kept and counted as aging."""
        policy = self.policy('2026-09-06', 3)
        self.assertFalse(policy(self.PATH))
        self.assertEqual(policy.stats, {'removed': 0, 'kept_absent_source': 0, 'kept_aging': 1})

    def test_title_past_the_window_is_removed(self):
        """Once the title has been missing for the full window it is removed."""
        self.assertTrue(self.policy('2026-09-05', 3)(self.PATH))
        self.assertTrue(self.policy('2026-08-01', 3)(self.PATH))

    def test_unavailable_provider_still_wins_over_aging(self):
        """An absent provider keeps its titles no matter how old they are."""
        policy = self.policy('2026-01-01', 3, status=ABSENT)
        self.assertFalse(policy(self.PATH))
        self.assertEqual(policy.stats['kept_absent_source'], 1)
        self.assertEqual(policy.stats['kept_aging'], 0)

    def test_untracked_file_ignores_aging(self):
        """A file the state never recorded follows the old behaviour and is removed."""
        policy = retention_policy(state_with({}), PRESENT, remove_after_days=30, today='2026-09-08')
        self.assertTrue(policy('Movie_VOD/Unknown (2001)/Unknown (2001).strm'))

    def test_unusable_last_seen_date_removes(self):
        """A record with no usable last-seen date cannot be aged, so it is removed."""
        policy = self.policy('', 3)
        self.assertTrue(policy(self.PATH))

    def test_today_defaults_to_current_date(self):
        """Without an explicit today the policy uses the real date."""
        with mock.patch('parser.processors.library_state.today_str', return_value='2026-09-08'):
            policy = retention_policy(state_with({self.PATH: {'s': ['chico'], 'd': '2026-09-07'}}), PRESENT,
                                      remove_after_days=5)
        self.assertFalse(policy(self.PATH))

    def test_report_mentions_aging_count(self):
        """report_retention prints the number of titles kept inside the window."""
        policy = self.policy('2026-09-07', 3)
        policy(self.PATH)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            report_retention(policy)
        self.assertIn('kept 1 files still inside REMOVE_AFTER_DAYS', out.getvalue())


class RemoveAfterDaysEnvTests(unittest.TestCase):
    """REMOVE_AFTER_DAYS is read as an integer with 0 as the default."""

    def read(self, value):
        """Return the parsed remove_after_days for an environment value (None means unset)."""
        env = {} if value is None else {'REMOVE_AFTER_DAYS': value}
        with mock.patch.dict('os.environ', env, clear=False):
            if value is None:
                import os
                os.environ.pop('REMOVE_AFTER_DAYS', None)
            return variables_all(process_env_variable, str_to_bool, process_env_special, 'remove_after_days')['remove_after_days']

    def test_default_and_blank_are_zero(self):
        """Unset or blank means immediate removal."""
        self.assertEqual(self.read(None), 0)
        self.assertEqual(self.read(''), 0)

    def test_number_is_parsed(self):
        """A numeric value is used as the number of days."""
        self.assertEqual(self.read('3'), 3)

    def test_non_numeric_falls_back_to_zero(self):
        """A value such as '3 days' or '1.5' is ignored with a warning instead of stopping the parser."""
        self.assertEqual(self.read('3 days'), 0)
        self.assertEqual(self.read('1.5'), 0)


if __name__ == '__main__':
    unittest.main()
