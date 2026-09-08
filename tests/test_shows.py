"""Tests for show-title splitting and cross-provider year merging in parser.processors.shows."""
import unittest

from parser.processors.shows import merge_show_years, split_show_title
from parser.processors.handlers import strm_path_for_entry


def series(show, season='01', season_episode='S01E01', url='u'):
    """Build a series entry dict in the shape clean_group_title produces."""
    return {'series': True, 'tv_show': True, 'show_title': show, 'season': season,
            'season_episode': season_episode, 'stream_url': url, 'duration': '-1'}


def talk_show(show, season='01', season_episode='S01E01', url='u'):
    """Build a television (talk show) entry dict, which merge_show_years must treat like series."""
    return {'television': True, 'tv_show': True, 'show_title': show, 'season': season,
            'season_episode': season_episode, 'stream_url': url, 'duration': '-1'}


def movie(title, date, url='u'):
    """Build a movie entry dict; movies carry no show_title and must be left untouched."""
    return {'movie': True, 'movie_title': title, 'movie_date': date, 'stream_url': url, 'duration': '-1'}


class SplitShowTitleTests(unittest.TestCase):
    """split_show_title peels trailing (YYYY) and (CC) tags off in any order."""

    def test_year_then_country(self):
        """A trailing year followed by a country tag is stripped to base + year."""
        self.assertEqual(split_show_title('Acapulco (2021) (US)'), ('Acapulco', '2021', 'US'))

    def test_country_then_year(self):
        """The tags are recognised regardless of which comes first."""
        self.assertEqual(split_show_title('Acapulco (US) (2021)'), ('Acapulco', '2021', 'US'))

    def test_no_tags(self):
        """A bare title has no year and is returned unchanged."""
        self.assertEqual(split_show_title('Acapulco'), ('Acapulco', '', ''))

    def test_title_with_digits_and_year(self):
        """A number in the base title does not confuse the trailing year match."""
        self.assertEqual(split_show_title('The 100 (2014) (US)'), ('The 100', '2014', 'US'))

    def test_internal_year_like_text_is_untouched(self):
        """A year-shaped number inside the title (not a trailing tag) is left alone."""
        self.assertEqual(split_show_title('Class of 1999 Reunion'), ('Class of 1999 Reunion', '', ''))

    def test_only_19xx_20xx_years_count(self):
        """A trailing parenthesised number outside 19xx/20xx is not treated as a year."""
        self.assertEqual(split_show_title('Show (1899)'), ('Show (1899)', '', ''))
        self.assertEqual(split_show_title('Show (2099)'), ('Show', '2099', ''))

    def test_non_two_letter_uppercase_parenthetical_is_not_a_country(self):
        """Only two-uppercase-letter tags are stripped as country codes; other parentheticals stay."""
        self.assertEqual(split_show_title('Acapulco (Uncut)'), ('Acapulco (Uncut)', '', ''))

    def test_whitespace_is_trimmed(self):
        """Leading/trailing whitespace around the title and stripped tags is trimmed away."""
        self.assertEqual(split_show_title('  Acapulco (2021) (US)  '), ('Acapulco', '2021', 'US'))


class MergeShowYearsTests(unittest.TestCase):
    """merge_show_years groups series/television entries and back-fills a single known year."""

    def test_one_known_year_is_applied_to_the_whole_group(self):
        """A bare title and a tagged title for the same show both gain the known year."""
        bare = series('Acapulco')
        tagged = series('Acapulco (2021) (US)')
        merge_show_years([bare, tagged])
        self.assertEqual(bare['show_title'], 'Acapulco (2021)')
        self.assertEqual(tagged['show_title'], 'Acapulco (2021)')

    def test_no_year_anywhere_leaves_bare_base_name(self):
        """With no year known in the group, entries just lose their country tag."""
        tagged = series('Untold (GB)')
        bare = series('Untold')
        merge_show_years([tagged, bare])
        self.assertEqual(tagged['show_title'], 'Untold')
        self.assertEqual(bare['show_title'], 'Untold')

    def test_two_different_years_are_kept_apart(self):
        """Each year keeps its own entries; an unyeared entry is left bare, not guessed."""
        old = series('Battlestar Galactica (1978)')
        new = series('Battlestar Galactica (2004) (US)')
        unknown = series('Battlestar Galactica')
        merge_show_years([old, new, unknown])
        self.assertEqual(old['show_title'], 'Battlestar Galactica (1978)')
        self.assertEqual(new['show_title'], 'Battlestar Galactica (2004)')
        self.assertEqual(unknown['show_title'], 'Battlestar Galactica')

    def test_grouping_matches_dedupe_key_and_uses_first_spelling(self):
        """Titles that differ only by punctuation/case/spacing merge, keeping the first spelling seen."""
        first = series('AVATAR: The Last Airbender')
        second = series('Avatar the Last Airbender (2005)')
        merge_show_years([first, second])
        self.assertEqual(first['show_title'], 'AVATAR: The Last Airbender (2005)')
        self.assertEqual(second['show_title'], 'AVATAR: The Last Airbender (2005)')

    def test_movies_are_untouched(self):
        """Movie entries have no show_title and their movie_title must survive unchanged."""
        film = movie('Get Gotti', '2023')
        merge_show_years([film])
        self.assertNotIn('show_title', film)
        self.assertEqual(film['movie_title'], 'Get Gotti')

    def test_live_tv_and_titleless_entries_are_skipped_without_error(self):
        """Live TV entries and entries missing show_title are ignored, not errored on."""
        live = {'livetv': True, 'tvg-name': 'CNN', 'stream_url': 'u', 'duration': '-1'}
        no_title_series = {'series': True, 'tv_show': True, 'season': '01',
                            'season_episode': 'S01E01', 'stream_url': 'u'}
        merge_show_years([live, no_title_series])
        self.assertNotIn('show_title', live)
        self.assertNotIn('show_title', no_title_series)

    def test_disabled_leaves_entries_unchanged(self):
        """enabled=False returns the entries as-is, even where a merge would otherwise happen."""
        bare = series('Acapulco')
        tagged = series('Acapulco (2021) (US)')
        merge_show_years([bare, tagged], enabled=False)
        self.assertEqual(bare['show_title'], 'Acapulco')
        self.assertEqual(tagged['show_title'], 'Acapulco (2021) (US)')

    def test_television_entries_participate_like_series(self):
        """Talk-show entries flagged 'television' merge alongside 'series' entries."""
        bare = talk_show('Untold')
        tagged = series('Untold (2021) (US)')
        merge_show_years([bare, tagged])
        self.assertEqual(bare['show_title'], 'Untold (2021)')
        self.assertEqual(tagged['show_title'], 'Untold (2021)')

    def test_returns_same_list_object_and_mutates_in_place(self):
        """The input list is returned (not a copy) and its entry dicts are mutated in place."""
        entries = [series('Acapulco'), series('Acapulco (2021) (US)')]
        first_entry = entries[0]
        result = merge_show_years(entries)
        self.assertIs(result, entries)
        self.assertIs(result[0], first_entry)
        self.assertEqual(result[0]['show_title'], 'Acapulco (2021)')

    def test_end_to_end_strm_paths_share_one_folder(self):
        """After merging, both providers' Acapulco episodes resolve into the same season folder."""
        bare = series('Acapulco', season='01', season_episode='S01E01', url='http://a')
        tagged = series('Acapulco (2021) (US)', season='01', season_episode='S01E01', url='http://b')
        merge_show_years([bare, tagged])
        path_bare = strm_path_for_entry(bare, 'TV_VOD', 'Movie_VOD', 'Unsorted_VOD')
        path_tagged = strm_path_for_entry(tagged, 'TV_VOD', 'Movie_VOD', 'Unsorted_VOD')
        expected_dir = 'TV_VOD/Acapulco (2021)/Season 01/'
        self.assertTrue(path_bare.replace('\\', '/').startswith(expected_dir))
        self.assertTrue(path_tagged.replace('\\', '/').startswith(expected_dir))


class CountryConflictTests(unittest.TestCase):
    """Shows that differ only by country tag are different shows and are never merged."""

    def entries(self, *titles):
        """Series entries for the given show titles."""
        return [{'series': True, 'tv_show': True, 'show_title': t, 'season': '01', 'season_episode': 'S01E01'}
                for t in titles]

    def test_different_country_tags_stay_apart(self):
        """The Office (US) and The Office (UK) keep their tags instead of collapsing into one folder."""
        entries = self.entries('The Office (US)', 'The Office (UK)')
        merge_show_years(entries)
        self.assertEqual([e['show_title'] for e in entries], ['The Office (US)', 'The Office (UK)'])

    def test_year_is_not_shared_across_countries(self):
        """A year known only for one country is not applied to the other, and an untagged copy is left alone."""
        entries = self.entries('The Office (US) (2005)', 'The Office (UK)', 'The Office')
        merge_show_years(entries)
        self.assertEqual([e['show_title'] for e in entries], ['The Office (US) (2005)', 'The Office (UK)', 'The Office'])

    def test_single_country_tag_is_still_dropped(self):
        """With only one country tag in the group the tag is removed as before."""
        entries = self.entries('Acapulco (2021) (US)', 'Acapulco')
        merge_show_years(entries)
        self.assertEqual([e['show_title'] for e in entries], ['Acapulco (2021)', 'Acapulco (2021)'])

    def test_conflicting_countries_write_separate_folders(self):
        """The two Office shows resolve to different show folders on disk."""
        entries = self.entries('The Office (US)', 'The Office (UK)')
        merge_show_years(entries)
        paths = {strm_path_for_entry(e, 'TV_VOD', 'Movie_VOD', 'Unsorted_VOD') for e in entries}
        self.assertEqual(len(paths), 2)


if __name__ == '__main__':
    unittest.main()
