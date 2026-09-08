"""Tests for per-provider source labels and M3U_URL-ordered playlist combining."""
import contextlib
import io
import os
import tempfile
import unittest
from unittest import mock

import requests

import parser.processors.cleaners as cleaners
from parser.processors.cleaners import clean_group_title, process_value
from parser.processors.handlers import (SOURCE_MARKER, download_m3u, prepare_m3us, proc_entries, redact_url,
                                        source_label, unique_label)
from parser.processors.parsers import parse_m3u_file


class FakeResponse:
    """Minimal stand-in for requests.Response."""

    def __init__(self, status_code=200, content=b'', headers=None):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}


def playlist(*names):
    """Build m3u bytes with one movie entry per name, URL derived from the name."""
    lines = ['#EXTM3U']
    for name in names:
        lines.append(f'#EXTINF:-1 tvg-id="" tvg-name="{name}" tvg-logo="" group-title="Movies",{name}')
        lines.append('http://stream/' + name.replace(' ', '_'))
    return ('\n'.join(lines) + '\n').encode('utf-8')


class SourceLabelTests(unittest.TestCase):
    """source_label derives a file-safe provider name."""

    def test_uses_first_hostname_component(self):
        """The first component of the hostname becomes the label."""
        self.assertEqual(source_label('http://chicotv.top/get.php?username=u&password=p', 0), 'chicotv')
        self.assertEqual(source_label('http://line.one-ott.xyz:80/get.php?x=1', 1), 'line')

    def test_explicit_label_wins(self):
        """An M3U_LABELS entry for the same index overrides the hostname."""
        self.assertEqual(source_label('http://chicotv.top/get.php', 0, ['chico', 'alpha']), 'chico')
        self.assertEqual(source_label('http://alphax8k.top/get.php', 1, ['chico', 'alpha']), 'alpha')

    def test_missing_or_blank_label_falls_back(self):
        """Blank or missing M3U_LABELS entries fall back to the hostname, then to sourceN."""
        self.assertEqual(source_label('http://alphax8k.top/get.php', 1, ['chico']), 'alphax8k')
        self.assertEqual(source_label('http://alphax8k.top/get.php', 1, ['chico', '']), 'alphax8k')
        self.assertEqual(source_label('not a url', 2), 'source3')

    def test_label_is_file_safe(self):
        """Characters outside letters, digits, dot, underscore and hyphen are dropped."""
        self.assertEqual(source_label('http://x.y', 0, ['my provider/1']), 'myprovider1')


class LabelAndLoggingTests(unittest.TestCase):
    """Generated labels never collide and log lines never carry provider credentials."""

    def test_unique_label_keeps_suffixing_until_free(self):
        """A generated label that is already taken gets the first free numeric suffix."""
        self.assertEqual(unique_label('source3', set()), 'source3')
        self.assertEqual(unique_label('source3', {'source3'}), 'source32')
        self.assertEqual(unique_label('source3', {'source3', 'source32'}), 'source33')

    def test_redact_url_drops_query_and_keeps_host_path(self):
        """The query string, which carries the username and password, never reaches the log."""
        self.assertEqual(redact_url('http://chicotv.top:80/get.php?username=u&password=p'), 'http://chicotv.top:80/get.php')
        self.assertEqual(redact_url('https://x.example/list.m3u'), 'https://x.example/list.m3u')
        self.assertEqual(redact_url('not a url'), '<invalid url>')

    def test_download_logs_omit_credentials_and_use_timeout(self):
        """Failure and error logs show the redacted URL only, and every request carries a timeout."""
        url = 'http://chicotv.top/get.php?username=secretuser&password=secretpass'
        calls = []

        def failing_get(u, **kwargs):
            calls.append(kwargs)
            raise requests.ConnectionError(f'cannot reach {u}')

        with tempfile.TemporaryDirectory() as tmp:
            out = io.StringIO()
            with mock.patch('parser.processors.handlers.requests.get', side_effect=failing_get), \
                    contextlib.redirect_stdout(out):
                self.assertFalse(download_m3u(url, os.path.join(tmp, 'x.m3u'), skip_header=True))
        self.assertNotIn('secretpass', out.getvalue())
        self.assertNotIn('secretuser', out.getvalue())
        self.assertIn('http://chicotv.top/get.php', out.getvalue())
        self.assertEqual(calls[0].get('timeout'), (15, 120))


class PrepareM3usTests(unittest.TestCase):
    """prepare_m3us downloads in M3U_URL order and marks each provider's section."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.m3u_dir = os.path.join(self.tmp.name, 'm3u')
        os.makedirs(self.m3u_dir)
        self.combined = os.path.join(self.tmp.name, 'm3u_file.m3u')

    def tearDown(self):
        self.tmp.cleanup()

    def run_prepare(self, responses, urls, labels=None):
        """Run prepare_m3us with requests.get answering from ``responses`` keyed by URL."""
        with mock.patch('parser.processors.handlers.requests.get', side_effect=lambda url, **kwargs: responses[url]):
            return prepare_m3us(urls, self.m3u_dir, self.combined, skip_header=True, M3U_LABELS=labels)

    def test_sections_follow_url_order_with_markers(self):
        """The combined file lists providers in M3U_URL order, each behind a source marker."""
        urls = ['http://alphax8k.top/get.php', 'http://chicotv.top/get.php']
        responses = {urls[0]: FakeResponse(content=playlist('Alpha Movie (2020)')),
                     urls[1]: FakeResponse(content=playlist('Chico Movie (2021)'))}
        sources = self.run_prepare(responses, urls)
        self.assertEqual([s['label'] for s in sources], ['alphax8k', 'chicotv'])
        self.assertTrue(all(s['downloaded'] for s in sources))
        with open(self.combined, encoding='utf-8') as f:
            content = f.read()
        self.assertLess(content.index(f'{SOURCE_MARKER}alphax8k'), content.index('Alpha Movie'))
        self.assertLess(content.index('Alpha Movie'), content.index(f'{SOURCE_MARKER}chicotv'))
        self.assertLess(content.index(f'{SOURCE_MARKER}chicotv'), content.index('Chico Movie'))
        self.assertEqual(sorted(os.listdir(self.m3u_dir)), ['00_alphax8k.m3u', '01_chicotv.m3u'])

    def test_failed_and_empty_sources_are_reported_not_combined(self):
        """A non-200 or empty download yields downloaded False or an empty section that is skipped."""
        urls = ['http://bad.example/get.php', 'http://empty.example/get.php', 'http://good.example/get.php']
        responses = {urls[0]: FakeResponse(status_code=884),
                     urls[1]: FakeResponse(content=b''),
                     urls[2]: FakeResponse(content=playlist('Good Movie (2022)'))}
        sources = self.run_prepare(responses, urls)
        self.assertEqual([(s['label'], s['downloaded']) for s in sources],
                         [('bad', False), ('empty', True), ('good', True)])
        with open(self.combined, encoding='utf-8') as f:
            content = f.read()
        self.assertNotIn(f'{SOURCE_MARKER}bad', content)
        self.assertNotIn(f'{SOURCE_MARKER}empty', content)
        self.assertIn(f'{SOURCE_MARKER}good', content)

    def test_truncated_download_cannot_swallow_next_source_marker(self):
        """A playlist cut off mid-line loses its partial last line, so later entries keep their own provider."""
        urls = ['http://alphax8k.top/get.php', 'http://chicotv.top/get.php']
        cut = playlist('Alpha Movie (2020)') + b'#EXTINF:-1 tvg-name="Half" group-title="Movies",Half (2'
        responses = {urls[0]: FakeResponse(content=cut), urls[1]: FakeResponse(content=playlist('Chico Movie (2021)'))}
        self.run_prepare(responses, urls)
        entries, errors = parse_m3u_file(self.combined, clean_group_title, process_value, {}, {}, [','], [], [], [], [])
        self.assertEqual(errors, [])
        self.assertEqual([(e['tvg-name'], e['source'], e['stream_url']) for e in entries],
                         [('Alpha Movie (2020)', 'alphax8k', 'http://stream/Alpha_Movie_(2020)'),
                          ('Chico Movie (2021)', 'chicotv', 'http://stream/Chico_Movie_(2021)')])

    def test_forged_marker_inside_a_playlist_is_ignored(self):
        """A provider cannot attribute its entries to another provider by emitting the marker itself."""
        urls = ['http://alphax8k.top/get.php', 'http://chicotv.top/get.php']
        forged = playlist('Alpha Movie (2020)') + f'{SOURCE_MARKER}chicotv\n'.encode() + \
            playlist('Fake Chico (2021)').replace(b'#EXTM3U\n', b'')
        responses = {urls[0]: FakeResponse(content=forged), urls[1]: FakeResponse(status_code=500)}
        sources = self.run_prepare(responses, urls)
        entries, errors = parse_m3u_file(self.combined, clean_group_title, process_value, {}, {}, [','], [], [], [], [])
        self.assertEqual(errors, [])
        self.assertEqual({e['source'] for e in entries}, {'alphax8k'})
        self.assertEqual([s['downloaded'] for s in sources], [True, False])

    def test_generated_labels_never_collide(self):
        """Explicit labels that clash with a generated fallback still produce distinct providers."""
        urls = ['http://a.example/1', 'http://b.example/2', 'http://c.example/3']
        responses = {u: FakeResponse(content=playlist('M (2020)')) for u in urls}
        sources = self.run_prepare(responses, urls, labels=['source3', 'source32', '!!!'])
        self.assertEqual(len({s['label'] for s in sources}), 3)

    def test_all_sources_failing_raises(self):
        """When nothing usable was downloaded the run aborts as before."""
        urls = ['http://bad.example/get.php']
        with self.assertRaises(ValueError):
            self.run_prepare({urls[0]: FakeResponse(status_code=500)}, urls)

    def test_duplicate_labels_are_made_unique(self):
        """Two URLs on the same host get distinct labels."""
        urls = ['http://chicotv.top/a', 'http://chicotv.top/b']
        responses = {u: FakeResponse(content=playlist('M (2020)')) for u in urls}
        sources = self.run_prepare(responses, urls)
        self.assertEqual([s['label'] for s in sources], ['chicotv', 'chicotv2'])


class SourceTaggingTests(unittest.TestCase):
    """Parsed entries carry the provider label and first-wins follows M3U_URL order."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._cleaner = cleaners.cleaner_value
        cleaners.cleaner_value = lambda f: ['tv']

    def tearDown(self):
        cleaners.cleaner_value = self._cleaner
        self.tmp.cleanup()

    def combined_file(self):
        """Write a combined playlist where alpha and chico both carry Tangled (2010)."""
        path = os.path.join(self.tmp.name, 'combined.m3u')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('#EXTM3U\n')
            f.write(f'{SOURCE_MARKER}alphax8k\n')
            f.write(playlist('Tangled (2010)', 'Alpha Only (2019)').decode('utf-8').replace('#EXTM3U\n', '')
                    .replace('http://stream/', 'http://alpha/'))
            f.write(f'{SOURCE_MARKER}chicotv\n')
            f.write(playlist('Tangled (2010)').decode('utf-8').replace('#EXTM3U\n', '').replace('http://stream/', 'http://chico/'))
        return path

    def parse(self, path):
        entries, errors = parse_m3u_file(path, clean_group_title, process_value, {}, {}, [','], [], [], [], [])
        self.assertEqual(errors, [])
        return entries

    def test_entries_get_source_label(self):
        """Each entry is tagged with the marker that precedes it."""
        entries = self.parse(self.combined_file())
        self.assertEqual([(e['tvg-name'], e['source']) for e in entries],
                         [('Tangled (2010)', 'alphax8k'), ('Alpha Only (2019)', 'alphax8k'), ('Tangled (2010)', 'chicotv')])

    def test_first_listed_provider_wins_duplicates(self):
        """The duplicate from the later provider is skipped and the first provider's URL is kept."""
        entries = self.parse(self.combined_file())
        movies = os.path.join(self.tmp.name, 'Movie_VOD')
        proc_entries(entries, [], os.path.join(self.tmp.name, 'TV_VOD'), movies, os.path.join(self.tmp.name, 'Unsorted_VOD'))
        with open(os.path.join(movies, 'Tangled (2010)', 'Tangled (2010).strm'), encoding='utf-8') as f:
            self.assertEqual(f.read(), 'http://alpha/Tangled_(2010)')
        self.assertTrue(entries[2].get('duplicate'))


if __name__ == '__main__':
    unittest.main()
