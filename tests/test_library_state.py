"""Tests for parser.processors.library_state and the retention-aware sync helpers
in parser.processors.handlers (prune_tree, sync_directories)."""
import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest import mock

from parser.processors.handlers import prune_tree, sync_directories
from parser.processors.library_state import (
    empty_state,
    judge_sources,
    load_state,
    normalize_state,
    prune_state,
    record_run,
    relative_written,
    report_retention,
    report_sources,
    retention_policy,
    save_state,
)


def write(path, content=''):
    """Create ``path`` (and its parent directories) with ``content``."""
    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


class LoadStateTests(unittest.TestCase):
    """load_state always returns a usable state, even from a bad file."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.state_file = os.path.join(self.tmpdir.name, 'state.json')

    def test_missing_file_returns_empty_state(self):
        """A state file that was never written yields the empty-state shape."""
        self.assertEqual(load_state(self.state_file), empty_state())

    def test_invalid_json_returns_empty_state(self):
        """Garbage bytes that fail to parse as JSON yield the empty state."""
        write(self.state_file, '{not json at all')
        self.assertEqual(load_state(self.state_file), empty_state())

    def test_non_object_json_returns_empty_state(self):
        """Valid JSON that isn't an object (e.g. a list) yields the empty state."""
        write(self.state_file, '[1, 2, 3]')
        self.assertEqual(load_state(self.state_file), empty_state())

    def test_round_trip_through_save_and_load(self):
        """A state written by save_state comes back unchanged from load_state."""
        state = {'version': 1, 'sources': {'chico': {'entries': 42, 'd': '2026-01-01'}},
                  'files': {'Movie_VOD/x.strm': {'s': ['chico'], 'd': '2026-01-01'}}}
        save_state(self.state_file, state)
        self.assertEqual(load_state(self.state_file), {**state, 'shows': {}})

    def test_save_state_creates_parent_directory(self):
        """save_state makes any missing directories in the target path."""
        nested = os.path.join(self.tmpdir.name, 'nested', 'dir', 'state.json')
        save_state(nested, empty_state())
        self.assertTrue(os.path.isfile(nested))

    def test_save_state_leaves_no_tmp_file_behind(self):
        """The atomic write's .tmp file is renamed away, not left on disk."""
        save_state(self.state_file, empty_state())
        self.assertEqual(os.listdir(self.tmpdir.name), ['state.json'])


class JudgeSourcesTests(unittest.TestCase):
    """judge_sources decides, per provider, whether this run's playlist is trustworthy."""

    def test_not_downloaded_is_absent(self):
        """A source whose playlist never downloaded is absent with that reason."""
        status = judge_sources({}, [{'label': 'chico', 'downloaded': False}], [])
        self.assertEqual(status['chico']['present'], False)
        self.assertEqual(status['chico']['reason'], 'no playlist downloaded')

    def test_downloaded_but_no_entries_is_absent(self):
        """A downloaded but empty playlist is absent with 'playlist was empty'."""
        status = judge_sources({}, [{'label': 'chico', 'downloaded': True}], [])
        self.assertEqual(status['chico']['present'], False)
        self.assertEqual(status['chico']['reason'], 'playlist was empty')

    def test_ratio_below_threshold_is_absent(self):
        """Fewer than min_source_ratio of the previous entry count marks the source absent."""
        state = {'sources': {'chico': {'entries': 100}}}
        entries = [{'source': 'chico'}] * 30
        status = judge_sources(state, [{'label': 'chico', 'downloaded': True}], entries, min_source_ratio=0.5)
        self.assertFalse(status['chico']['present'])
        self.assertIn('30', status['chico']['reason'])
        self.assertIn('100', status['chico']['reason'])

    def test_ratio_meets_threshold_is_present(self):
        """At or above min_source_ratio of the previous count marks the source present."""
        state = {'sources': {'chico': {'entries': 100}}}
        entries = [{'source': 'chico'}] * 60
        status = judge_sources(state, [{'label': 'chico', 'downloaded': True}], entries, min_source_ratio=0.5)
        self.assertTrue(status['chico']['present'])
        self.assertEqual(status['chico']['reason'], 'ok')

    def test_first_run_with_no_previous_record_is_present(self):
        """With nothing recorded from a previous run, any non-empty download is trusted."""
        entries = [{'source': 'chico'}]
        status = judge_sources({}, [{'label': 'chico', 'downloaded': True}], entries)
        self.assertTrue(status['chico']['present'])

    def test_status_carries_count_and_previous(self):
        """The returned status dict exposes this run's count and the prior count."""
        state = {'sources': {'chico': {'entries': 100}}}
        entries = [{'source': 'chico'}] * 60
        status = judge_sources(state, [{'label': 'chico', 'downloaded': True}], entries)
        self.assertEqual(status['chico']['count'], 60)
        self.assertEqual(status['chico']['previous'], 100)


class RecordRunTests(unittest.TestCase):
    """record_run stores this run's written files and each provider's trusted entry count."""

    def test_records_written_files_with_their_label(self):
        """Each written path is stored with the provider label that supplied it."""
        state = empty_state()
        record_run(state, {'Movie_VOD/x.strm': 'chico'}, {}, today='2026-01-01')
        self.assertEqual(state['files']['Movie_VOD/x.strm'], {'s': ['chico'], 'd': '2026-01-01'})

    def test_records_written_files_with_empty_label_as_empty_list(self):
        """A blank source label is stored as an empty 's' list, not ['']."""
        state = empty_state()
        record_run(state, {'Movie_VOD/x.strm': ''}, {}, today='2026-01-01')
        self.assertEqual(state['files']['Movie_VOD/x.strm'], {'s': [], 'd': '2026-01-01'})

    def test_list_of_labels_is_stored_without_blanks(self):
        """A file supplied by several providers keeps all of their labels."""
        state = {'sources': {}, 'files': {}}
        record_run(state, {'Movie_VOD/x.strm': ['alpha', '', 'chico']}, {}, today='2026-01-01')
        self.assertEqual(state['files']['Movie_VOD/x.strm'], {'s': ['alpha', 'chico'], 'd': '2026-01-01'})

    def test_present_source_records_its_entry_count(self):
        """A source marked present in status is recorded with this run's count."""
        state = empty_state()
        status = {'chico': {'present': True, 'count': 60, 'previous': 100, 'reason': 'ok'}}
        record_run(state, {}, status, today='2026-01-02')
        self.assertEqual(state['sources']['chico'], {'entries': 60, 'd': '2026-01-02'})

    def test_absent_source_keeps_its_previous_entry_count(self):
        """A previously-known source that is absent this run keeps its old entries value."""
        state = {'version': 1, 'sources': {'chico': {'entries': 100, 'd': '2025-12-01'}}, 'files': {}}
        status = {'chico': {'present': False, 'count': 30, 'previous': 100, 'reason': 'only 30 entries, previous run had 100'}}
        record_run(state, {}, status, today='2026-01-02')
        self.assertEqual(state['sources']['chico'], {'entries': 100, 'd': '2025-12-01'})

    def test_absent_source_never_seen_before_is_recorded_as_zero(self):
        """A brand-new source that is absent on its first run is recorded with zero entries."""
        state = empty_state()
        status = {'chico': {'present': False, 'count': 0, 'previous': 0, 'reason': 'no playlist downloaded'}}
        record_run(state, {}, status, today='2026-01-02')
        self.assertEqual(state['sources']['chico'], {'entries': 0, 'd': ''})


class RetentionPolicyTests(unittest.TestCase):
    """retention_policy builds the should_remove predicate used to prune the library."""

    def test_untracked_path_is_removed(self):
        """A file the state has never heard of follows the old CLEAN_SYNC behaviour."""
        should_remove = retention_policy({'files': {}}, {})
        self.assertTrue(should_remove('Movie_VOD/unknown.strm'))
        self.assertEqual(should_remove.stats, {'removed': 1, 'kept_absent_source': 0})

    def test_path_whose_source_is_absent_is_kept(self):
        """A file supplied by a provider currently marked absent is not removed."""
        state = {'files': {'Movie_VOD/x.strm': {'s': ['chico'], 'd': '2026-01-01'}}}
        status = {'chico': {'present': False, 'count': 0, 'previous': 5, 'reason': 'playlist was empty'}}
        should_remove = retention_policy(state, status)
        self.assertFalse(should_remove('Movie_VOD/x.strm'))
        self.assertEqual(should_remove.stats, {'removed': 0, 'kept_absent_source': 1})

    def test_path_whose_source_is_present_is_removed(self):
        """A file whose only supplying provider is present and trusted is removed."""
        state = {'files': {'Movie_VOD/x.strm': {'s': ['chico'], 'd': '2026-01-01'}}}
        status = {'chico': {'present': True, 'count': 5, 'previous': 5, 'reason': 'ok'}}
        should_remove = retention_policy(state, status)
        self.assertTrue(should_remove('Movie_VOD/x.strm'))
        self.assertEqual(should_remove.stats, {'removed': 1, 'kept_absent_source': 0})

    def test_source_missing_from_status_entirely_is_removed(self):
        """A provider dropped from the config altogether is treated as removed, not absent."""
        state = {'files': {'Movie_VOD/x.strm': {'s': ['oldprovider'], 'd': '2026-01-01'}}}
        should_remove = retention_policy(state, {})
        self.assertTrue(should_remove('Movie_VOD/x.strm'))
        self.assertEqual(should_remove.stats, {'removed': 1, 'kept_absent_source': 0})


class PruneStateTests(unittest.TestCase):
    """prune_state forgets library files that no longer exist on disk."""

    def test_drops_missing_files_and_keeps_existing_ones(self):
        """Only the file entries backed by an actual file under local_root survive."""
        with tempfile.TemporaryDirectory() as root:
            write(os.path.join(root, 'Movie_VOD', 'kept.strm'), 'x')
            state = {'files': {
                os.path.join('Movie_VOD', 'kept.strm'): {'s': ['chico'], 'd': '2026-01-01'},
                os.path.join('Movie_VOD', 'gone.strm'): {'s': ['chico'], 'd': '2025-12-01'},
            }}
            prune_state(state, root)
            self.assertEqual(list(state['files']), [os.path.join('Movie_VOD', 'kept.strm')])


class ReportTests(unittest.TestCase):
    """report_sources and report_retention only print; they never raise or return data."""

    def test_report_sources_prints_provider_labels_and_counts(self):
        """Both present and absent providers show their label and relevant numbers."""
        status = {
            'chico': {'present': True, 'count': 60, 'previous': 100, 'reason': 'ok'},
            'alpha': {'present': False, 'count': 0, 'previous': 5, 'reason': 'playlist was empty'},
        }
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            report_sources(status)
        output = buf.getvalue()
        self.assertIn('chico', output)
        self.assertIn('60', output)
        self.assertIn('100', output)
        self.assertIn('alpha', output)
        self.assertIn('playlist was empty', output)

    def test_report_retention_prints_stats(self):
        """The removed / kept counts from should_remove.stats are printed."""
        should_remove = retention_policy({'files': {}}, {})
        should_remove('Movie_VOD/a.strm')
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            report_retention(should_remove)
        output = buf.getvalue()
        self.assertIn('1', output)

    def test_report_retention_without_stats_prints_nothing_and_does_not_raise(self):
        """A plain callable with no .stats attribute is a silent no-op."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            report_retention(lambda rel_path: True)
        self.assertEqual(buf.getvalue(), '')


class RelativeWrittenTests(unittest.TestCase):
    """relative_written turns absolute written-file paths into root-relative ones."""

    def test_maps_absolute_paths_to_relative(self):
        """Each absolute path becomes its path relative to root_dir, label preserved."""
        with tempfile.TemporaryDirectory() as root:
            written = {os.path.join(root, 'Movie_VOD', 'x.strm'): 'chico'}
            self.assertEqual(relative_written(written, root),
                             {os.path.join('Movie_VOD', 'x.strm'): 'chico'})


class PruneTreeTests(unittest.TestCase):
    """prune_tree removes approved files and cleans up directories left empty."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.root = os.path.join(self.tmpdir.name, 'tree')
        write(os.path.join(self.root, 'keep.txt'), 'keep')
        write(os.path.join(self.root, 'remove.txt'), 'remove')
        write(os.path.join(self.root, 'empties', 'remove2.txt'), 'remove')
        write(os.path.join(self.root, 'mixed', 'keep2.txt'), 'keep')
        write(os.path.join(self.root, 'mixed', 'remove3.txt'), 'remove')

    def should_remove(self, rel_path):
        """Approve removal of any path whose basename starts with 'remove'."""
        return os.path.basename(rel_path).startswith('remove')

    def test_prunes_files_and_empty_directories_but_keeps_the_rest(self):
        """Approved files go, kept files stay, and only the now-empty directory disappears."""
        prune_tree(self.root, self.root, self.should_remove)
        self.assertTrue(os.path.isfile(os.path.join(self.root, 'keep.txt')))
        self.assertFalse(os.path.isfile(os.path.join(self.root, 'remove.txt')))
        self.assertFalse(os.path.exists(os.path.join(self.root, 'empties')))
        self.assertTrue(os.path.isdir(os.path.join(self.root, 'mixed')))
        self.assertTrue(os.path.isfile(os.path.join(self.root, 'mixed', 'keep2.txt')))
        self.assertFalse(os.path.isfile(os.path.join(self.root, 'mixed', 'remove3.txt')))


class SyncDirectoriesRetentionTests(unittest.TestCase):
    """sync_directories consults should_remove for anything missing from src when given one."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.src = os.path.join(self.tmpdir.name, 'src')
        self.dest = os.path.join(self.tmpdir.name, 'dest')
        os.makedirs(self.src)
        os.makedirs(self.dest)

    def keep_marked(self, rel_path):
        """A retention predicate that only removes paths whose basename contains 'remove'."""
        return 'remove' in os.path.basename(rel_path)

    def test_missing_dest_file_removed_when_should_remove_says_so(self):
        """A dest-only file approved for removal is deleted."""
        write(os.path.join(self.dest, 'remove_me.strm'), 'x')
        sync_directories(self.src, self.dest, remove_sync=True, should_remove=self.keep_marked, root=self.dest)
        self.assertFalse(os.path.exists(os.path.join(self.dest, 'remove_me.strm')))

    def test_missing_dest_file_kept_when_should_remove_declines(self):
        """A dest-only file the retention policy declines to remove, and its directory, survive."""
        write(os.path.join(self.dest, 'keep_dir', 'keep_me.strm'), 'x')
        sync_directories(self.src, self.dest, remove_sync=True, should_remove=self.keep_marked, root=self.dest)
        self.assertTrue(os.path.isfile(os.path.join(self.dest, 'keep_dir', 'keep_me.strm')))

    def test_whole_missing_directory_is_pruned_file_by_file(self):
        """A dest directory absent from src is walked, not deleted wholesale."""
        write(os.path.join(self.dest, 'stale_dir', 'keep_me.strm'), 'x')
        write(os.path.join(self.dest, 'stale_dir', 'remove_me.strm'), 'x')
        sync_directories(self.src, self.dest, remove_sync=True, should_remove=self.keep_marked, root=self.dest)
        self.assertTrue(os.path.isdir(os.path.join(self.dest, 'stale_dir')))
        self.assertTrue(os.path.isfile(os.path.join(self.dest, 'stale_dir', 'keep_me.strm')))
        self.assertFalse(os.path.isfile(os.path.join(self.dest, 'stale_dir', 'remove_me.strm')))

    def test_whole_missing_directory_disappears_once_every_file_is_approved(self):
        """When every file inside a stale directory is approved for removal, the directory too is gone."""
        write(os.path.join(self.dest, 'stale_dir', 'remove_a.strm'), 'x')
        write(os.path.join(self.dest, 'stale_dir', 'remove_b.strm'), 'x')
        sync_directories(self.src, self.dest, remove_sync=True, should_remove=self.keep_marked, root=self.dest)
        self.assertFalse(os.path.exists(os.path.join(self.dest, 'stale_dir')))

    def test_files_in_src_are_still_copied_and_updated(self):
        """New and changed files from src are copied into dest as usual."""
        write(os.path.join(self.src, 'new.strm'), 'new-content')
        write(os.path.join(self.dest, 'existing.strm'), 'old-content')
        write(os.path.join(self.src, 'existing.strm'), 'new-content')
        sync_directories(self.src, self.dest, remove_sync=True, should_remove=self.keep_marked, root=self.dest)
        with open(os.path.join(self.dest, 'new.strm'), encoding='utf-8') as f:
            self.assertEqual(f.read(), 'new-content')
        with open(os.path.join(self.dest, 'existing.strm'), encoding='utf-8') as f:
            self.assertEqual(f.read(), 'new-content')

    def test_without_should_remove_missing_dest_entries_are_removed_outright(self):
        """The old CLEAN_SYNC behaviour is unchanged when no should_remove is given."""
        write(os.path.join(self.dest, 'stale.strm'), 'x')
        write(os.path.join(self.dest, 'stale_dir', 'a.strm'), 'x')
        sync_directories(self.src, self.dest, remove_sync=True)
        self.assertFalse(os.path.exists(os.path.join(self.dest, 'stale.strm')))
        self.assertFalse(os.path.exists(os.path.join(self.dest, 'stale_dir')))


if __name__ == '__main__':
    unittest.main()


class MinSourceRatioEnvTests(unittest.TestCase):
    """MIN_SOURCE_RATIO is read tolerantly so a typo cannot stop the parser from running."""

    def read(self):
        """Return the parsed min_source_ratio under the current environment."""
        from parser.config.variables import process_env_special, process_env_variable, str_to_bool, variables_all
        return variables_all(process_env_variable, str_to_bool, process_env_special, 'min_source_ratio')['min_source_ratio']

    def test_default_blank_and_number(self):
        """Unset or blank gives 0.5; a number is used as given."""
        with mock.patch.dict('os.environ', {'MIN_SOURCE_RATIO': ''}):
            self.assertEqual(self.read(), 0.5)
        with mock.patch.dict('os.environ', {'MIN_SOURCE_RATIO': '0.8'}):
            self.assertEqual(self.read(), 0.8)

    def test_non_numeric_falls_back_to_default(self):
        """A value such as 50% is ignored with a warning instead of raising."""
        with mock.patch.dict('os.environ', {'MIN_SOURCE_RATIO': '50%'}):
            self.assertEqual(self.read(), 0.5)


class NormalizeStateTests(unittest.TestCase):
    """A damaged state file is repaired on load instead of crashing the sync."""

    def test_non_dict_sections_are_replaced(self):
        """sources, files and shows that are not objects become empty."""
        state = normalize_state({'sources': [], 'files': 'x', 'shows': 3})
        self.assertEqual((state['sources'], state['files'], state['shows']), ({}, {}, {}))

    def test_malformed_records_are_dropped_and_good_ones_kept(self):
        """Provider and file records of the wrong shape are discarded; valid ones survive."""
        state = normalize_state({
            'sources': {'chico': {'entries': 5}, 'bad': 7},
            'files': {'a.strm': {'s': ['chico'], 'd': '2026-01-01'}, 'b.strm': {'s': 'chico'}, 'c.strm': None},
            'shows': {'acapulco': '2021', 'bad': 2021},
        })
        self.assertEqual(state['sources'], {'chico': {'entries': 5}})
        self.assertEqual(list(state['files']), ['a.strm'])
        self.assertEqual(state['shows'], {'acapulco': '2021'})

    def test_load_state_normalizes_file_content(self):
        """load_state applies the same repair to what it reads from disk."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'state.json')
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({'sources': 'nope', 'files': {'x.strm': 1}}, f)
            state = load_state(path)
        self.assertEqual(state['sources'], {})
        self.assertEqual(state['files'], {})
        self.assertEqual(state['version'], 1)
