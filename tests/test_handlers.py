"""Regression tests for .strm de-duplication in parser.processors.handlers."""
import os
import tempfile
import unittest

from parser.processors.handlers import handle_entry, proc_entries, strm_path_for_entry
from parser.utils import write_to_file


def movie(title, date, url):
    """Build a movie entry dict in the shape clean_group_title produces."""
    return {'movie': True, 'movie_title': title, 'movie_date': date, 'stream_url': url,
            'tvg-name': f'{title} ({date})', 'duration': '-1'}


def episode(show, season, season_episode, url):
    """Build a series entry dict in the shape clean_group_title produces."""
    return {'series': True, 'tv_show': True, 'show_title': show, 'season': season,
            'season_episode': season_episode, 'stream_url': url, 'duration': '-1'}


class TempDirsMixin:
    """Provide fresh tv / movies / unsorted output directories for every test."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.tv_dir = os.path.join(self.tmpdir.name, 'TV_VOD')
        self.movies_dir = os.path.join(self.tmpdir.name, 'Movie_VOD')
        self.unsorted_dir = os.path.join(self.tmpdir.name, 'Unsorted_VOD')

    def strm_files(self):
        """Return {relative path: content} for every .strm written under the temp dir."""
        found = {}
        for root, _dirs, files in os.walk(self.tmpdir.name):
            for name in files:
                if name.endswith('.strm'):
                    path = os.path.join(root, name)
                    with open(path, encoding='utf-8') as handle:
                        found[os.path.relpath(path, self.tmpdir.name)] = handle.read()
        return found


class StrmPathForEntryTests(TempDirsMixin, unittest.TestCase):
    """strm_path_for_entry resolves the output path or returns None for skipped entries."""

    def test_movie_path(self):
        """Movies go to <movies>/<Title (Year)>/<Title (Year)>.strm."""
        path = strm_path_for_entry(movie('Get Gotti', '2023', 'u'), self.tv_dir, self.movies_dir, self.unsorted_dir)
        self.assertEqual(path, os.path.join(self.movies_dir, 'Get Gotti (2023)', 'Get Gotti (2023).strm'))

    def test_series_path(self):
        """Episodes go to <tv>/<Show>/Season <n>/<Show SxxEyy>.strm."""
        path = strm_path_for_entry(episode('Show', '01', 'S01E02', 'u'), self.tv_dir, self.movies_dir,
                                   self.unsorted_dir)
        self.assertEqual(path, os.path.join(self.tv_dir, 'Show', 'Season 01', 'Show S01E02.strm'))

    def test_unsorted_path(self):
        """Unsorted entries go to <unsorted>/<group-title>/<group-title>.strm."""
        entry = {'unsorted': True, 'group-title': 'Misc'}
        path = strm_path_for_entry(entry, self.tv_dir, self.movies_dir, self.unsorted_dir)
        self.assertEqual(path, os.path.join(self.unsorted_dir, 'Misc', 'Misc.strm'))

    def test_excluded_entry_returns_none(self):
        """Entries flagged exclude=True never get a path."""
        entry = movie('Adult film', '2019', 'u')
        entry['exclude'] = True
        self.assertIsNone(strm_path_for_entry(entry, self.tv_dir, self.movies_dir, self.unsorted_dir))

    def test_live_tv_entry_returns_none(self):
        """Live TV entries never get a .strm path."""
        entry = {'livetv': True, 'tvg-name': 'CNN', 'stream_url': 'u', 'duration': '-1'}
        self.assertIsNone(strm_path_for_entry(entry, self.tv_dir, self.movies_dir, self.unsorted_dir))


class HandleEntryTests(TempDirsMixin, unittest.TestCase):
    """handle_entry writes a single .strm and applies seen_paths de-duplication."""

    def test_writes_strm_and_returns_path(self):
        """A movie entry is written with its stream URL and the path is returned."""
        errors = []
        path = handle_entry(movie('Get Gotti', '2023', 'http://x/1'), self.tv_dir, self.movies_dir,
                            self.unsorted_dir, write_to_file, errors)
        self.assertTrue(os.path.isfile(path))
        self.assertEqual(self.strm_files(), {os.path.join('Movie_VOD', 'Get Gotti (2023)', 'Get Gotti (2023).strm'):
                                             'http://x/1'})
        self.assertEqual(errors, [])

    def test_seen_paths_marks_case_insensitive_duplicates(self):
        """The second entry resolving to the same path (ignoring case) is flagged duplicate."""
        errors, seen = [], set()
        first = movie('Get Gotti', '2023', 'http://x/1')
        second = movie('GET GOTTI', '2023', 'http://x/2')
        self.assertIsNotNone(handle_entry(first, self.tv_dir, self.movies_dir, self.unsorted_dir, write_to_file,
                                          errors, seen))
        self.assertIsNone(handle_entry(second, self.tv_dir, self.movies_dir, self.unsorted_dir, write_to_file,
                                       errors, seen))
        self.assertTrue(second.get('duplicate'))
        self.assertFalse(first.get('duplicate'))
        self.assertEqual(len(seen), 1)
        self.assertEqual(errors, [])

    def test_failed_first_write_does_not_mark_later_entry_duplicate(self):
        """A path is only remembered once its .strm was written, so a failed first write is retried."""
        errors, seen = [], set()
        calls = []

        def flaky_write(filepath, content):
            """Fail the first write, succeed afterwards."""
            calls.append(filepath)
            if len(calls) == 1:
                raise OSError('disk full')
            write_to_file(filepath, content)

        first = movie('Get Gotti', '2023', 'http://x/1')
        second = movie('Get Gotti', '2023', 'http://x/2')
        self.assertIsNone(handle_entry(first, self.tv_dir, self.movies_dir, self.unsorted_dir, flaky_write,
                                       errors, seen))
        self.assertEqual(len(errors), 1)
        self.assertEqual(seen, set())
        path = handle_entry(second, self.tv_dir, self.movies_dir, self.unsorted_dir, flaky_write, errors, seen)
        self.assertIsNotNone(path)
        self.assertFalse(second.get('duplicate'))
        self.assertEqual(self.strm_files(), {os.path.join('Movie_VOD', 'Get Gotti (2023)', 'Get Gotti (2023).strm'):
                                             'http://x/2'})

    def test_excluded_entry_writes_nothing(self):
        """Excluded entries produce no file and no error."""
        errors = []
        entry = movie('Adult film', '2019', 'http://x/5')
        entry['exclude'] = True
        self.assertIsNone(handle_entry(entry, self.tv_dir, self.movies_dir, self.unsorted_dir, write_to_file, errors))
        self.assertEqual(self.strm_files(), {})
        self.assertEqual(errors, [])


class ProcEntriesDeduplicationTests(TempDirsMixin, unittest.TestCase):
    """proc_entries honours remove_duplicates across a whole entry list."""

    def run_entries(self, entries, remove_duplicates):
        """Run proc_entries into the temp dirs and return the collected errors."""
        errors = []
        proc_entries(entries, errors, self.tv_dir, self.movies_dir, self.unsorted_dir,
                     remove_duplicates=remove_duplicates)
        return errors

    def test_first_entry_wins_when_removing_duplicates(self):
        """Two entries with the same title keep the first URL; the second is flagged."""
        entries = [movie('Get Gotti', '2023', 'http://x/first'),
                   movie('Get Gotti', '2023', 'http://x/second')]
        errors = self.run_entries(entries, remove_duplicates=True)
        self.assertEqual(errors, [])
        self.assertEqual(self.strm_files(), {os.path.join('Movie_VOD', 'Get Gotti (2023)', 'Get Gotti (2023).strm'):
                                             'http://x/first'})
        self.assertFalse(entries[0].get('duplicate'))
        self.assertTrue(entries[1].get('duplicate'))

    def test_case_variants_are_duplicates(self):
        """'Get Gotti' and 'GET GOTTI' resolve to one .strm containing the first URL."""
        entries = [movie('Get Gotti', '2023', 'http://x/first'),
                   movie('GET GOTTI', '2023', 'http://x/second')]
        self.run_entries(entries, remove_duplicates=True)
        files = self.strm_files()
        self.assertEqual(len(files), 1)
        self.assertEqual(list(files.values()), ['http://x/first'])
        self.assertTrue(entries[1].get('duplicate'))
        self.assertFalse(entries[0].get('duplicate'))

    def test_series_episodes_are_deduplicated_too(self):
        """The same episode delivered twice is only written once."""
        entries = [episode('Show', '01', 'S01E02', 'http://x/a'),
                   episode('show', '01', 'S01E02', 'http://x/b'),
                   episode('Show', '01', 'S01E03', 'http://x/c')]
        self.run_entries(entries, remove_duplicates=True)
        files = self.strm_files()
        self.assertEqual(len(files), 2)
        self.assertEqual(files[os.path.join('TV_VOD', 'Show', 'Season 01', 'Show S01E02.strm')], 'http://x/a')
        self.assertEqual([e.get('duplicate') for e in entries], [None, True, None])

    def test_last_entry_wins_when_not_removing_duplicates(self):
        """With de-duplication off the later entry overwrites the file and nothing is flagged."""
        entries = [movie('Get Gotti', '2023', 'http://x/first'),
                   movie('Get Gotti', '2023', 'http://x/second')]
        errors = self.run_entries(entries, remove_duplicates=False)
        self.assertEqual(errors, [])
        self.assertEqual(self.strm_files(), {os.path.join('Movie_VOD', 'Get Gotti (2023)', 'Get Gotti (2023).strm'):
                                             'http://x/second'})
        self.assertFalse(entries[0].get('duplicate'))
        self.assertFalse(entries[1].get('duplicate'))

    def test_excluded_entries_produce_no_file(self):
        """Entries flagged exclude=True are skipped entirely by proc_entries."""
        kept = movie('Some Film', '2020', 'http://x/kept')
        dropped = movie('Adult film', '2019', 'http://x/dropped')
        dropped['exclude'] = True
        live = {'livetv': True, 'tvg-name': 'CNN', 'stream_url': 'http://x/live', 'duration': '-1'}
        errors = self.run_entries([dropped, kept, live], remove_duplicates=True)
        self.assertEqual(errors, [])
        self.assertEqual(self.strm_files(), {os.path.join('Movie_VOD', 'Some Film (2020)', 'Some Film (2020).strm'):
                                             'http://x/kept'})
        self.assertFalse(dropped.get('duplicate'))


if __name__ == '__main__':
    unittest.main()
