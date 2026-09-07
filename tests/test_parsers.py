"""Regression tests for the INCLUDE_TERMS / EXCLUDE_TERMS filtering in parser.processors.parsers."""
import os
import tempfile
import unittest

from parser.processors.cleaners import clean_group_title, process_value
from parser.processors.parsers import filter_entry, parse_m3u_file, term_in_text, term_pattern


class TermMatchingTests(unittest.TestCase):
    """term_pattern / term_in_text match literally, case-insensitively and at word edges."""

    def test_match_is_case_insensitive(self):
        """A term matches regardless of the case used in the text."""
        self.assertTrue(term_in_text('en - series', ['EN']))
        self.assertTrue(term_in_text('KIDS MOVIES', ['kids']))

    def test_terms_are_matched_literally_not_as_regex(self):
        """Regex metacharacters in a term ([, +, |) are treated as plain text."""
        self.assertTrue(term_in_text('[EN] Films', ['[EN]']))
        self.assertTrue(term_in_text('Documentary+ Series', ['Documentary+']))
        self.assertTrue(term_in_text('US | News', ['US |']))

    def test_bracketed_term_does_not_match_as_character_class(self):
        """'[EN]' must not behave like the character class [EN] and match 'Get Gotti'."""
        self.assertFalse(term_in_text('Get Gotti', ['[EN]']))

    def test_alphanumeric_term_matches_only_whole_words(self):
        """'EN' matches when it stands alone but not when embedded in a longer word."""
        for text in ('EN - Series', '[EN]', 'Movies EN'):
            with self.subTest(text=text):
                self.assertTrue(term_in_text(text, ['EN']))
        for text in ('Documentary', 'General', 'ENTERTAINMENT'):
            with self.subTest(text=text):
                self.assertFalse(term_in_text(text, ['EN']))

    def test_underscore_is_a_word_boundary(self):
        """Underscores separate words, so 'EN' matches EN_MOVIES and EN_US but not ENTER_."""
        for text in ('EN_MOVIES', 'EN_US', 'MOVIES_EN', '_EN_'):
            with self.subTest(text=text):
                self.assertTrue(term_in_text(text, ['EN']))
        self.assertFalse(term_in_text('ENTER_MOVIES', ['EN']))

    def test_symbol_edges_match_literally(self):
        """A term ending in a symbol ('FR -') is matched exactly where it is written."""
        self.assertTrue(term_in_text('FR - Films', ['FR -']))
        self.assertFalse(term_in_text('FR Films', ['FR -']))

    def test_empty_inputs_never_match(self):
        """Empty text, an empty term list or blank terms never produce a match."""
        self.assertFalse(term_in_text('', ['EN']))
        self.assertFalse(term_in_text('EN', []))
        self.assertFalse(term_in_text('EN', None))
        self.assertFalse(term_in_text('EN', ['']))

    def test_term_pattern_is_compiled_case_insensitive(self):
        """term_pattern returns a compiled, case-insensitive pattern."""
        pattern = term_pattern('Kids')
        self.assertIsNotNone(pattern.search('KIDS zone'))
        self.assertIsNone(pattern.search('Kidsy'))


class FilterEntryTests(unittest.TestCase):
    """filter_entry combines INCLUDE_TERMS and EXCLUDE_TERMS over the relevant entry fields."""

    def test_no_terms_filters_nothing(self):
        """With neither include nor exclude terms configured, every entry is kept."""
        entry = {'group-title': 'XXX', 'tvg-name': 'Anything'}
        self.assertFalse(filter_entry(entry))
        self.assertFalse(filter_entry(entry, [], []))
        self.assertFalse(filter_entry(entry, None, None))

    def test_exclude_checks_group_title_tvg_name_and_extgrp(self):
        """An exclude term found in any of group-title, tvg-name or extgrp drops the entry."""
        self.assertTrue(filter_entry({'group-title': 'XXX Adult'}, EXCLUDE_TERM=['XXX']))
        self.assertTrue(filter_entry({'tvg-name': 'XXX Adult'}, EXCLUDE_TERM=['XXX']))
        self.assertTrue(filter_entry({'extgrp': '#EXTGRP:XXX'}, EXCLUDE_TERM=['XXX']))
        self.assertFalse(filter_entry({'group-title': 'Kids', 'tvg-name': 'Cartoon', 'extgrp': '#EXTGRP:Kids'},
                                      EXCLUDE_TERM=['XXX']))

    def test_include_keeps_only_matching_entries(self):
        """With INCLUDE_TERMS set, entries without a matching field are dropped."""
        self.assertFalse(filter_entry({'group-title': 'EN - Movies'}, INCLUDE_TERM=['EN']))
        self.assertFalse(filter_entry({'tvg-name': 'EN Show'}, INCLUDE_TERM=['EN']))
        self.assertFalse(filter_entry({'extgrp': '#EXTGRP:[EN] Kids'}, INCLUDE_TERM=['EN']))
        self.assertTrue(filter_entry({'group-title': 'FR - Films'}, INCLUDE_TERM=['EN']))
        self.assertTrue(filter_entry({'group-title': 'General'}, INCLUDE_TERM=['EN']))

    def test_exclude_wins_over_include(self):
        """An entry matching both an include and an exclude term is excluded."""
        entry = {'group-title': 'EN - XXX'}
        self.assertTrue(filter_entry(entry, INCLUDE_TERM=['EN'], EXCLUDE_TERM=['XXX']))
        self.assertFalse(filter_entry({'group-title': 'EN - Kids'}, INCLUDE_TERM=['EN'], EXCLUDE_TERM=['XXX']))

    def test_entry_without_any_fields_is_excluded_when_include_set(self):
        """An entry with no group-title/tvg-name/extgrp cannot satisfy INCLUDE_TERMS."""
        self.assertTrue(filter_entry({}, INCLUDE_TERM=['EN']))
        self.assertFalse(filter_entry({}, EXCLUDE_TERM=['EN']))


SAMPLE_M3U = """#EXTM3U
#EXTINF:-1 tvg-id="" tvg-name="Get Gotti (2023)" group-title="Documentary+",Get Gotti (2023)
http://example.test/vod/1.mkv
#EXTINF:-1 tvg-id="" tvg-name="Some Film (2020)" group-title="HD : FR - Films",Some Film (2020)
http://example.test/vod/2.mkv
#EXTINF:-1 tvg-id="cnn" tvg-name="CNN" group-title="US | News",CNN
http://example.test/live/3
#EXTINF:-1 tvg-id="" tvg-name="Show S01E02" group-title="EN - Series",Show S01E02
#EXTGRP:Kids
http://example.test/series/4.mkv
#EXTINF:-1 tvg-id="" tvg-name="Adult film (2019)" group-title="XXX",Adult film (2019)
http://example.test/vod/5.mkv
"""


class ParseM3uFileTests(unittest.TestCase):
    """parse_m3u_file flags filtered entries with exclude=True on a temporary m3u file."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.TemporaryDirectory()
        cls.m3u_path = os.path.join(cls.tmpdir.name, 'sample.m3u')
        with open(cls.m3u_path, 'w', encoding='utf-8') as handle:
            handle.write(SAMPLE_M3U)

    @classmethod
    def tearDownClass(cls):
        cls.tmpdir.cleanup()

    def parse(self, EXCLUDE_TERM=None, INCLUDE_TERM=None, filter_live_tv=False):
        """Run parse_m3u_file with the default scrub settings and return entries keyed by tvg-name."""
        entries, errors = parse_m3u_file(
            self.m3u_path, clean_group_title, process_value,
            REPLACE_TERMS={}, REPLACE_DEFAULTS={},
            SCRUB_HEADER=[','], SCRUB_DEFAULTS=['HD :', 'SD :'],
            REMOVE_TERMS=[], REMOVE_DEFAULTS=[],
            EXCLUDE_TERM=EXCLUDE_TERM, INCLUDE_TERM=INCLUDE_TERM,
            filter_live_tv=filter_live_tv,
        )
        self.assertEqual(errors, [])
        return {entry['tvg-name']: entry for entry in entries}

    def test_all_entries_parsed_and_classified(self):
        """Every #EXTINF block is returned once and classified into movie / series / live TV."""
        by_name = self.parse()
        self.assertEqual(len(by_name), 5)
        self.assertTrue(by_name['Get Gotti (2023)'].get('movie'))
        self.assertEqual(by_name['Get Gotti (2023)']['movie_title'], 'Get Gotti')
        self.assertEqual(by_name['Get Gotti (2023)']['movie_date'], '2023')
        self.assertEqual(by_name['Some Film (2020)']['movie_title'], 'Some Film')
        self.assertTrue(by_name['CNN'].get('livetv'))
        self.assertTrue(by_name['Show S01E02'].get('series'))
        self.assertEqual(by_name['Show S01E02']['show_title'], 'Show')
        self.assertEqual(by_name['Show S01E02']['stream_url'], 'http://example.test/series/4.mkv')
        for entry in by_name.values():
            self.assertFalse(entry.get('exclude'), entry)

    def test_filtered_vod_entries_are_flagged_excluded(self):
        """VOD entries matching EXCLUDE_TERMS get exclude=True while the rest are untouched."""
        by_name = self.parse(EXCLUDE_TERM=['XXX'])
        self.assertTrue(by_name['Adult film (2019)'].get('exclude'))
        self.assertFalse(by_name['Get Gotti (2023)'].get('exclude'))
        self.assertFalse(by_name['Show S01E02'].get('exclude'))

    def test_include_terms_flag_non_matching_vod_entries(self):
        """With INCLUDE_TERMS, VOD entries that match no include term are flagged."""
        by_name = self.parse(INCLUDE_TERM=['EN'])
        self.assertFalse(by_name['Show S01E02'].get('exclude'))
        self.assertTrue(by_name['Get Gotti (2023)'].get('exclude'))
        self.assertTrue(by_name['Some Film (2020)'].get('exclude'))
        self.assertTrue(by_name['Adult film (2019)'].get('exclude'))

    def test_live_tv_not_flagged_unless_filter_live_tv(self):
        """Live TV entries ignore the filters by default and honour them with filter_live_tv=True."""
        by_name = self.parse(EXCLUDE_TERM=['US |'])
        self.assertTrue(by_name['CNN'].get('livetv'))
        self.assertFalse(by_name['CNN'].get('exclude'))

        by_name = self.parse(EXCLUDE_TERM=['US |'], filter_live_tv=True)
        self.assertTrue(by_name['CNN'].get('livetv'))
        self.assertTrue(by_name['CNN'].get('exclude'))

    def test_live_tv_not_flagged_by_include_terms_unless_filter_live_tv(self):
        """INCLUDE_TERMS also leave live TV alone unless filter_live_tv is enabled."""
        by_name = self.parse(INCLUDE_TERM=['EN'])
        self.assertFalse(by_name['CNN'].get('exclude'))
        by_name = self.parse(INCLUDE_TERM=['EN'], filter_live_tv=True)
        self.assertTrue(by_name['CNN'].get('exclude'))

    def test_extgrp_line_is_captured_and_filterable(self):
        """The #EXTGRP line is stored on the entry and can be matched by the filters."""
        by_name = self.parse()
        self.assertEqual(by_name['Show S01E02']['extgrp'], '#EXTGRP:Kids')
        self.assertNotIn('extgrp', by_name['Get Gotti (2023)'])

        by_name = self.parse(EXCLUDE_TERM=['Kids'])
        self.assertTrue(by_name['Show S01E02'].get('exclude'))

        by_name = self.parse(INCLUDE_TERM=['Kids'])
        self.assertFalse(by_name['Show S01E02'].get('exclude'))
        self.assertTrue(by_name['Get Gotti (2023)'].get('exclude'))

    def test_filters_apply_to_raw_group_title_before_scrub_header(self):
        """A term equal to the scrubbed-away group name still excludes the entry."""
        by_name = self.parse(EXCLUDE_TERM=['Documentary+'])
        entry = by_name['Get Gotti (2023)']
        self.assertTrue(entry.get('exclude'))
        # The group name really was scrubbed from the final value.
        self.assertNotIn('Documentary+', entry['group-title'])
        self.assertEqual(entry['movie_title'], 'Get Gotti')

        by_name = self.parse(EXCLUDE_TERM=['FR -'])
        self.assertTrue(by_name['Some Film (2020)'].get('exclude'))
        self.assertFalse(by_name['Get Gotti (2023)'].get('exclude'))


if __name__ == '__main__':
    unittest.main()
