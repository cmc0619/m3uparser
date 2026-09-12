"""Tests for targeted Jellyfin refresh helpers and sync added-path collection."""
import os
import sys
import tempfile
import unittest
from unittest import mock

# jellyfin_apiclient_python is optional in local unit-test environments
sys.modules.setdefault('jellyfin_apiclient_python', mock.MagicMock())

from parser.config.variables import parse_refresh_lib, variables_all, process_env_variable, str_to_bool, process_env_special
from parser.jellyfin_api.utility.library_refresh import map_vods_path, media_updated_payload
from parser.jellyfin_api.utility.apikey_jellyfin import run_libraryapi_task
from parser.processors.handlers import sync_directories


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


class ParseRefreshLibTests(unittest.TestCase):
    def test_false_values(self):
        for value in (None, '', 'false', 'False', 'no', '0', False):
            self.assertEqual(parse_refresh_lib(value), 'false')

    def test_true_values(self):
        for value in ('true', 'TRUE', 'yes', '1', True):
            self.assertEqual(parse_refresh_lib(value), 'true')

    def test_targeted(self):
        self.assertEqual(parse_refresh_lib('targeted'), 'targeted')
        self.assertEqual(parse_refresh_lib('TARGETED'), 'targeted')

    def test_unknown_falls_back_to_false(self):
        self.assertEqual(parse_refresh_lib('maybe'), 'false')


class MapVodsPathTests(unittest.TestCase):
    def test_maps_relative_tree(self):
        local = os.path.join('/usr/src/app', 'VODS', 'TV_VOD', 'Show', 'ep.strm')
        root = os.path.join('/usr/src/app', 'VODS')
        self.assertEqual(
            map_vods_path(local, root, '/data/vod'),
            '/data/vod/TV_VOD/Show/ep.strm',
        )

    def test_rejects_outside_root(self):
        with self.assertRaises(ValueError):
            map_vods_path('/tmp/other.strm', '/usr/src/app/VODS', '/data/vod')


class MediaUpdatedPayloadTests(unittest.TestCase):
    def test_payload_shape(self):
        local = os.path.join('/app', 'VODS', 'Movie_VOD', 'Film (2024)', 'Film (2024).strm')
        root = os.path.join('/app', 'VODS')
        payload = media_updated_payload([local], root, '/data/vod')
        self.assertEqual(payload['Updates'][0]['UpdateType'], 'Created')
        self.assertTrue(payload['Updates'][0]['Path'].startswith('/data/vod/'))


class SyncAddedPathsTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.src = os.path.join(self.tmpdir.name, 'src')
        self.dest = os.path.join(self.tmpdir.name, 'dest')
        os.makedirs(self.src)
        os.makedirs(self.dest)

    def test_collects_new_files_only(self):
        write(os.path.join(self.src, 'new.strm'), 'url-a')
        write(os.path.join(self.dest, 'existing.strm'), 'url-old')
        write(os.path.join(self.src, 'existing.strm'), 'url-new')
        added = []
        sync_directories(self.src, self.dest, remove_sync=False, added_paths=added)
        self.assertEqual(added, [os.path.join(self.dest, 'new.strm')])


class VariablesRefreshModeTests(unittest.TestCase):
    def test_env_targeted_and_vods_path(self):
        with mock.patch.dict(os.environ, {
            'REFRESH_LIB': 'targeted',
            'JELLYFIN_VODS_PATH': '/data/vod',
        }, clear=False):
            values = variables_all(process_env_variable, str_to_bool, process_env_special,
                                   'lib_refresh', 'jellyfin_vods_path')
            self.assertEqual(values['lib_refresh'], 'targeted')
            self.assertEqual(values['jellyfin_vods_path'], '/data/vod')


class RunLibraryApiTaskTests(unittest.TestCase):
    def test_targeted_without_env_does_not_call_jellyfin(self):
        with mock.patch('parser.jellyfin_api.utility.apikey_jellyfin.JellyfinClient') as client_cls:
            run_libraryapi_task('key', 'http://jf', 'targeted', jellyfin_vods_path='',
                                local_vods_dir='/app/VODS', added_paths=['/app/VODS/a.strm'])
            client_cls.assert_not_called()

    def test_targeted_with_no_adds_does_not_call_jellyfin(self):
        with mock.patch('parser.jellyfin_api.utility.apikey_jellyfin.JellyfinClient') as client_cls:
            run_libraryapi_task('key', 'http://jf', 'targeted', jellyfin_vods_path='/data/vod',
                                local_vods_dir='/app/VODS', added_paths=[])
            client_cls.assert_not_called()

    def test_targeted_posts_media_updated(self):
        client = mock.MagicMock()
        client.jellyfin.get_default_headers.return_value = {}
        client.jellyfin.send_request.return_value.status_code = 204
        with mock.patch('parser.jellyfin_api.utility.apikey_jellyfin.JellyfinClient', return_value=client):
            local = os.path.join('/app', 'VODS', 'TV_VOD', 'Show', 'ep.strm')
            run_libraryapi_task('key', 'http://jf', 'targeted', jellyfin_vods_path='/data/vod',
                                local_vods_dir=os.path.join('/app', 'VODS'), added_paths=[local])
        args, kwargs = client.jellyfin.send_request.call_args
        self.assertEqual(args[1], '/Library/Media/Updated')
        self.assertEqual(kwargs['method'], 'post')
        self.assertIn('/data/vod/', kwargs['data'])

    def test_true_posts_full_refresh(self):
        client = mock.MagicMock()
        client.jellyfin.get_default_headers.return_value = {}
        client.jellyfin.send_request.return_value.status_code = 204
        with mock.patch('parser.jellyfin_api.utility.apikey_jellyfin.JellyfinClient', return_value=client):
            run_libraryapi_task('key', 'http://jf', 'true')
        self.assertEqual(client.jellyfin.send_request.call_args[0][1], '/Library/Refresh')


if __name__ == '__main__':
    unittest.main()
