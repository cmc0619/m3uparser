"""Tests for versions mode (DUPLICATE_VERSIONS) in parser.processors.handlers."""
import os
import tempfile
import unittest

from parser.processors.handlers import handle_entry, proc_entries, version_path
from parser.utils import write_to_file


def movie(title, date, url, source=None):
    """Build a movie entry dict in the shape clean_group_title produces, optionally with a source."""
    entry = {'movie': True, 'movie_title': title, 'movie_date': date, 'stream_url': url,
             'tvg-name': f'{title} ({date})', 'duration': '-1'}
    if source is not None:
        entry['source'] = source
    return entry


def episode(show, season, season_episode, url, source=None):
    """Build a series entry dict in the shape clean_group_title produces, optionally with a source."""
    entry = {'series': True, 'tv_show': True, 'show_title': show, 'season': season,
             'season_episode': season_episode, 'stream_url': url, 'duration': '-1'}
    if source is not None:
        entry['source'] = source
    return entry


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


class VersionPathTests(unittest.TestCase):
    """version_path inserts a `` - <label>`` suffix before the .strm extension."""

    def test_appends_label_before_extension(self):
        """A non-empty label is inserted right before the file extension."""
        self.assertEqual(version_path('/a/Tangled (2010).strm', 'chicotv'),
                         '/a/Tangled (2010) - chicotv.strm')

    def test_empty_label_leaves_path_unchanged(self):
        """An empty label returns the original path untouched."""
        self.assertEqual(version_path('/a/Tangled (2010).strm', ''), '/a/Tangled (2010).strm')


class HandleEntryVersionsModeTests(TempDirsMixin, unittest.TestCase):
    """handle_entry with canonical_paths honours the first entry's folder/base name."""

    def test_second_source_reuses_first_entrys_canonical_path(self):
        """A same-title entry from a different source is written under the first entry's base name."""
        errors, seen, canonical = [], set(), {}
        first = movie('Tangled', '2010', 'http://x/chico', source='chicotv')
        second = movie('TANGLED', '2010', 'http://x/alpha', source='alphax8k')
        first_path = handle_entry(first, self.tv_dir, self.movies_dir, self.unsorted_dir, write_to_file,
                                  errors, seen, canonical)
        second_path = handle_entry(second, self.tv_dir, self.movies_dir, self.unsorted_dir, write_to_file,
                                   errors, seen, canonical)
        self.assertEqual(first_path, os.path.join(self.movies_dir, 'Tangled (2010)', 'Tangled (2010) - chicotv.strm'))
        self.assertEqual(second_path, os.path.join(self.movies_dir, 'Tangled (2010)',
                                                    'Tangled (2010) - alphax8k.strm'))
        self.assertFalse(first.get('duplicate'))
        self.assertFalse(second.get('duplicate'))
        self.assertEqual(errors, [])


class ProcEntriesVersionsModeTests(TempDirsMixin, unittest.TestCase):
    """proc_entries with duplicate_versions=True writes one .strm per provider."""

    def run_entries(self, entries):
        """Run proc_entries in versions mode and return (written mapping, errors)."""
        errors = []
        written = proc_entries(entries, errors, self.tv_dir, self.movies_dir, self.unsorted_dir,
                               remove_duplicates=True, duplicate_versions=True)
        return written, errors

    def test_different_sources_both_written_in_same_folder(self):
        """Two providers of the same movie ('Tangled (2010)' vs 'TANGLED  (2010)') both get a file, same folder."""
        entries = [movie('Tangled', '2010', 'http://x/chico', source='chicotv'),
                   movie('TANGLED ', '2010', 'http://x/alpha', source='alphax8k')]
        written, errors = self.run_entries(entries)
        self.assertEqual(errors, [])
        files = self.strm_files()
        self.assertEqual(len(files), 2)
        expected_dir = os.path.join('Movie_VOD', 'Tangled (2010)')
        self.assertEqual(files[os.path.join(expected_dir, 'Tangled (2010) - chicotv.strm')], 'http://x/chico')
        self.assertEqual(files[os.path.join(expected_dir, 'Tangled (2010) - alphax8k.strm')], 'http://x/alpha')
        self.assertFalse(entries[0].get('duplicate'))
        self.assertFalse(entries[1].get('duplicate'))
        self.assertEqual(set(written.values()), {'chicotv', 'alphax8k'})

    def test_same_source_repeat_is_flagged_and_skipped(self):
        """A second entry from the SAME source for the same title is a duplicate, not a new version."""
        entries = [movie('Tangled', '2010', 'http://x/first', source='chicotv'),
                   movie('TANGLED', '2010', 'http://x/second', source='chicotv')]
        written, errors = self.run_entries(entries)
        self.assertEqual(errors, [])
        files = self.strm_files()
        self.assertEqual(len(files), 1)
        self.assertEqual(list(files.values()), ['http://x/first'])
        self.assertFalse(entries[0].get('duplicate'))
        self.assertTrue(entries[1].get('duplicate'))
        self.assertEqual(len(written), 1)

    def test_series_episode_versions_get_source_suffix(self):
        """Episodes from two sources land in the same Season folder, each with its own suffix."""
        entries = [episode('Show', '01', 'S01E02', 'http://x/chico', source='chicotv'),
                   episode('show', '01', 'S01E02', 'http://x/alpha', source='alphax8k')]
        written, errors = self.run_entries(entries)
        self.assertEqual(errors, [])
        files = self.strm_files()
        self.assertEqual(len(files), 2)
        season_dir = os.path.join('TV_VOD', 'Show', 'Season 01')
        self.assertEqual(files[os.path.join(season_dir, 'Show S01E02 - chicotv.strm')], 'http://x/chico')
        self.assertEqual(files[os.path.join(season_dir, 'Show S01E02 - alphax8k.strm')], 'http://x/alpha')

    def test_entry_without_source_written_without_suffix(self):
        """An entry carrying no source key gets no `` - <label>`` suffix in versions mode."""
        entries = [movie('Get Gotti', '2023', 'http://x/1')]
        written, errors = self.run_entries(entries)
        self.assertEqual(errors, [])
        self.assertEqual(self.strm_files(), {os.path.join('Movie_VOD', 'Get Gotti (2023)', 'Get Gotti (2023).strm'):
                                             'http://x/1'})
        self.assertEqual(list(written.values()), [''])

    def test_excluded_entry_produces_no_file(self):
        """Entries flagged exclude=True still produce no file in versions mode."""
        excluded = movie('Adult film', '2019', 'http://x/5', source='chicotv')
        excluded['exclude'] = True
        written, errors = self.run_entries([excluded])
        self.assertEqual(errors, [])
        self.assertEqual(self.strm_files(), {})
        self.assertEqual(written, {})
        self.assertFalse(excluded.get('duplicate'))

    def test_written_mapping_covers_every_file_with_its_source(self):
        """proc_entries returns {written path: source label} for every file it wrote."""
        entries = [movie('Tangled', '2010', 'http://x/chico', source='chicotv'),
                   movie('TANGLED', '2010', 'http://x/alpha', source='alphax8k')]
        written, errors = self.run_entries(entries)
        self.assertEqual(errors, [])
        self.assertEqual(len(written), 2)
        base = os.path.join(self.movies_dir, 'Tangled (2010)')
        self.assertEqual(written[os.path.join(base, 'Tangled (2010) - chicotv.strm')], 'chicotv')
        self.assertEqual(written[os.path.join(base, 'Tangled (2010) - alphax8k.strm')], 'alphax8k')
        for path in written:
            self.assertTrue(os.path.isfile(path))


class ProcEntriesNormalModeTests(TempDirsMixin, unittest.TestCase):
    """proc_entries with duplicate_versions=False (the default) keeps the old single-file behaviour."""

    def run_entries(self, entries):
        """Run proc_entries in normal (non-versions) mode and return (written mapping, errors)."""
        errors = []
        written = proc_entries(entries, errors, self.tv_dir, self.movies_dir, self.unsorted_dir,
                               remove_duplicates=True, duplicate_versions=False)
        return written, errors

    def test_second_providers_copy_is_skipped_as_duplicate(self):
        """With versions mode off, only the first provider's stream is written; no suffix is added."""
        entries = [movie('Tangled', '2010', 'http://x/chico', source='chicotv'),
                   movie('TANGLED', '2010', 'http://x/alpha', source='alphax8k')]
        written, errors = self.run_entries(entries)
        self.assertEqual(errors, [])
        expected_path = os.path.join('Movie_VOD', 'Tangled (2010)', 'Tangled (2010).strm')
        self.assertEqual(self.strm_files(), {expected_path: 'http://x/chico'})
        self.assertFalse(entries[0].get('duplicate'))
        self.assertTrue(entries[1].get('duplicate'))
        self.assertEqual(list(written.values()), ['chicotv'])

    def test_written_mapping_has_no_suffix_in_normal_mode(self):
        """The returned mapping's paths carry no `` - source`` suffix outside versions mode."""
        entries = [movie('Get Gotti', '2023', 'http://x/1', source='chicotv')]
        written, errors = self.run_entries(entries)
        self.assertEqual(errors, [])
        expected = os.path.join(self.movies_dir, 'Get Gotti (2023)', 'Get Gotti (2023).strm')
        self.assertEqual(written, {expected: 'chicotv'})


if __name__ == '__main__':
    unittest.main()
