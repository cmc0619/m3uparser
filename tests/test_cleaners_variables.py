"""Regression tests for issue 20 (SCRUB_HEADER with a literal comma) and env variable parsing."""
import os
import unittest
from unittest import mock

from parser.config.variables import vars as resolve_vars, process_env_special, process_env_variable, str_to_bool, variables_all
from parser.processors.cleaners import process_value


class ProcessValueHeaderTests(unittest.TestCase):
    """process_value removes a SCRUB_HEADER term and everything before it, literally."""

    def test_plus_in_group_name_is_scrubbed_with_comma_header(self):
        """'Documentary+,' is removed even though '+' is a regex metacharacter (issue 20)."""
        self.assertEqual(process_value('Documentary+,Get Gotti', remove_header=[',']), 'Get Gotti')

    def test_plain_group_name_is_scrubbed_with_comma_header(self):
        """The plain 'Documentary,' header is removed the same way."""
        self.assertEqual(process_value('Documentary,Get Gotti', remove_header=[',']), 'Get Gotti')

    def test_header_match_is_case_insensitive_and_non_greedy(self):
        """Only the first occurrence of the header term is used and case is ignored."""
        self.assertEqual(process_value('hd : The Fall Guy 2024', remove_header=['HD :']), 'The Fall Guy 2024')
        self.assertEqual(process_value('A,B,C', remove_header=[',']), 'B,C')

    def test_missing_header_leaves_value_untouched(self):
        """A header term that is not present leaves the value as-is (stripped)."""
        self.assertEqual(process_value('  Movie VOD ', remove_header=['HD :']), 'Movie VOD')


class ProcessEnvVariableTests(unittest.TestCase):
    """process_env_variable splits comma lists and honours escaped commas."""

    def test_escaped_comma_yields_literal_comma(self):
        """SCRUB_HEADER="\\," resolves to a single literal comma term."""
        self.assertEqual(process_env_variable('"\\,"'), [','])

    def test_blank_items_are_dropped(self):
        """Consecutive commas and surrounding whitespace do not create empty terms."""
        self.assertEqual(process_env_variable('"a,,, b"'), ['a', 'b'])

    def test_quotes_are_stripped_and_regex_characters_preserved(self):
        """Symmetric outer quotes are removed and terms keep characters like '+' and '['."""
        self.assertEqual(process_env_variable("'Documentary+, [EN], US |'"), ['Documentary+', '[EN]', 'US |'])
        self.assertEqual(process_env_variable(''), [])

    def test_non_string_returns_none(self):
        """Non-string input is not processed."""
        self.assertIsNone(process_env_variable(None))


class RemoveDuplicatesVariableTests(unittest.TestCase):
    """REMOVE_DUPLICATES defaults to True and can be switched off via the environment."""

    def read(self):
        """Fetch the variables relevant to the new features from variables_all."""
        return variables_all(process_env_variable, str_to_bool, process_env_special,
                             'remove_duplicates', 'filter_live_tv', 'INCLUDE_TERM')

    def test_defaults_when_unset(self):
        """Unset REMOVE_DUPLICATES defaults to True; the other new options default to off/empty."""
        with mock.patch.dict(os.environ):
            for key in ('REMOVE_DUPLICATES', 'FILTER_LIVE_TV', 'INCLUDE_TERMS'):
                os.environ.pop(key, None)
            values = self.read()
        self.assertIs(values['remove_duplicates'], True)
        self.assertIs(values['filter_live_tv'], False)
        self.assertEqual(values['INCLUDE_TERM'], [])

    def test_blank_value_defaults_to_true(self):
        """A blank REMOVE_DUPLICATES (as written by a template env file) still means True."""
        with mock.patch.dict(os.environ, {'REMOVE_DUPLICATES': ''}):
            values = self.read()
        self.assertIs(values['remove_duplicates'], True)

    def test_false_value_disables(self):
        """REMOVE_DUPLICATES=false turns de-duplication off."""
        with mock.patch.dict(os.environ, {'REMOVE_DUPLICATES': 'false'}):
            values = self.read()
        self.assertIs(values['remove_duplicates'], False)

    def test_filter_live_tv_and_include_terms_are_read(self):
        """FILTER_LIVE_TV and INCLUDE_TERMS are exposed through variables_all."""
        with mock.patch.dict(os.environ, {'FILTER_LIVE_TV': 'true', 'INCLUDE_TERMS': '"EN, [EN]"'}):
            values = self.read()
        self.assertIs(values['filter_live_tv'], True)
        self.assertEqual(values['INCLUDE_TERM'], ['EN', '[EN]'])


class VarsHelperTests(unittest.TestCase):
    """vars() resolves variable names given positionally and as keyword values alike."""

    def test_keyword_string_values_are_resolved_alongside_positional_names(self):
        """A keyword whose value names a variable receives that variable even when positional names are present."""
        seen = {}

        def target(movies_dir, remove_sync, root=None):
            seen.update(movies_dir=movies_dir, remove_sync=remove_sync, root=root)

        with mock.patch.dict('os.environ', {'CLEAN_SYNC': 'true'}):
            resolve_vars(target, variables_all, 'movies_dir', 'remove_sync', root='local_vods_dir')
        expected = variables_all(process_env_variable, str_to_bool, process_env_special, 'movies_dir', 'local_vods_dir')
        self.assertEqual(seen['movies_dir'], expected['movies_dir'])
        self.assertEqual(seen['root'], expected['local_vods_dir'])
        self.assertTrue(seen['remove_sync'])

    def test_unknown_strings_pass_through_unchanged(self):
        """A string that is not a variable name is handed to the function as written."""
        seen = {}

        def target(label, root=None):
            seen.update(label=label, root=root)

        resolve_vars(target, variables_all, 'not-a-variable', root='/some/path')
        self.assertEqual(seen, {'label': 'not-a-variable', 'root': '/some/path'})


if __name__ == '__main__':
    unittest.main()
