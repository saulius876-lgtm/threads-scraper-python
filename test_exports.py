"""Offline export regressions: python -m unittest -v test_exports.py. No paid runs."""
from contextlib import redirect_stdout, redirect_stderr
import csv
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

# Load without requiring the SDK: every client in this suite is a local fake.
stub = ModuleType('apify_client')
stub.ApifyClient = None
with patch.dict(sys.modules, {'apify_client': stub}):
    spec = importlib.util.spec_from_file_location('threads_example', Path(__file__).with_name('threads_search.py'))
    app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app)


class FakeClient:
    def __init__(self, rows=(), status='SUCCEEDED', download_error=False):
        self.rows = rows
        self.status = status
        self.download_error = download_error
        self.input = None
    def actor(self, name):
        assert name == app.ACTOR
        return self
    def call(self, **kwargs):
        self.input = kwargs['run_input']
        return SimpleNamespace(status=self.status, default_dataset_id='offline')
    def dataset(self, dataset_id):
        assert dataset_id == 'offline'
        return self
    def iterate_items(self):
        yield from self.rows
        if self.download_error:
            raise ConnectionError('simulated interrupted download')


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.out = self.root / 'report.CSV'
        self.side = self.root / 'report-profiles.csv'
        self.out.write_text('stale posts\n')
        self.side.write_text('stale profiles\n')
    def run_cli(self, rows=(), args=('topic',), **kwargs):
        client = FakeClient(rows, **kwargs)
        with patch.object(app, 'ApifyClient', return_value=client), patch.object(app.os.environ, 'get', return_value='offline-token'), patch.object(sys, 'argv', ['threads_search.py', *args, '--out', str(self.out)]), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            code = app.main()
        return code, client
    def read(self, path):
        with path.open(newline='') as stream:
            reader = csv.DictReader(stream)
            return reader.fieldnames, list(reader)
    def test_empty_keywords_replace_stale_csv_with_post_header(self):
        self.assertEqual(self.run_cli()[0], 0)
        self.assertEqual(self.read(self.out), (app.POST_COLUMNS, []))
    def test_empty_profiles_replace_stale_csv_with_profile_header(self):
        code, client = self.run_cli(args=('--profiles', 'account'))
        self.assertEqual(code, 0)
        self.assertEqual(client.input['maxPostsPerProfile'], 0)
        self.assertEqual(self.read(self.out), (app.PROFILE_COLUMNS, []))
    def test_empty_mixed_replaces_both_stale_files(self):
        self.assertEqual(self.run_cli(args=('topic', '--profiles', 'account'))[0], 0)
        self.assertEqual(self.read(self.out), (app.POST_COLUMNS, []))
        self.assertEqual(self.read(self.side), (app.PROFILE_COLUMNS, []))
    def test_posts_sorted_and_csv_special_characters_round_trip(self):
        rows=[{'type':'post','likes':2,'text':'comma, quote " and\nnewline'}, {'type':'post','likes':9,'text':'first'}]
        self.assertEqual(self.run_cli(rows)[0], 0)
        data=self.read(self.out)[1]
        self.assertEqual([r['likes'] for r in data], ['9','2'])
        self.assertEqual(data[1]['text'], rows[0]['text'])
    def test_profiles_join_links_without_mutating_rows(self):
        row={'type':'profile','username':'account','bioLinks':['https://example.com/a','https://example.com/b']}
        self.assertEqual(self.run_cli([row], args=('--profiles','account'))[0], 0)
        self.assertEqual(self.read(self.out)[1][0]['bioLinks'], ' '.join(row['bioLinks']))
        self.assertIsInstance(row['bioLinks'], list)
    def test_mixed_empty_posts_keeps_profiles_in_sibling(self):
        row={'type':'profile','username':'account'}
        self.assertEqual(self.run_cli([row], args=('topic','--profiles','account'))[0], 0)
        self.assertEqual(self.read(self.out), (app.POST_COLUMNS, []))
        self.assertEqual(self.read(self.side)[1][0]['username'], 'account')
    def test_mixed_posts_and_profiles_preserve_both_modes(self):
        rows=[{'type':'post','text':'post'}, {'type':'profile','username':'account'}]
        self.assertEqual(self.run_cli(rows, args=('topic','--profiles','account'))[0], 0)
        self.assertEqual(self.read(self.out)[1][0]['text'], 'post')
        self.assertEqual(self.read(self.side)[1][0]['username'], 'account')
    def test_mixed_empty_profiles_clears_stale_sibling(self):
        self.assertEqual(self.run_cli([{'type':'post','text':'post'}], args=('topic','--profiles','account'))[0], 0)
        self.assertEqual(self.read(self.side), (app.PROFILE_COLUMNS, []))
    def test_error_only_clears_stale_csv_and_returns_two(self):
        self.assertEqual(self.run_cli([{'type':'error','input':'topic','error':'not found'}])[0], 2)
        self.assertEqual(self.read(self.out), (app.POST_COLUMNS, []))
    def test_valid_rows_with_unknown_row_are_exported_but_return_two(self):
        self.assertEqual(self.run_cli([{'type':'post','text':'valid'}, {'type':'unexpected'}])[0], 2)
        self.assertEqual(self.read(self.out)[1][0]['text'], 'valid')
    def test_failed_actor_does_not_replace_previous_exports(self):
        with self.assertRaises(SystemExit):self.run_cli(status='FAILED')
        self.assertEqual(self.out.read_text(), 'stale posts\n')
        self.assertEqual(self.side.read_text(), 'stale profiles\n')
    def test_partial_download_does_not_replace_previous_export(self):
        with self.assertRaises(ConnectionError):self.run_cli([{'type':'post'}], download_error=True)
        self.assertEqual(self.out.read_text(), 'stale posts\n')
    def test_replace_failure_preserves_old_file_and_cleans_temp(self):
        with patch.object(app.os, 'replace', side_effect=OSError('simulated disk failure')):
            with self.assertRaises(OSError):self.run_cli()
        self.assertEqual(self.out.read_text(), 'stale posts\n')
        self.assertEqual(sorted(x.name for x in self.root.iterdir()), ['report-profiles.csv','report.CSV'])
    def test_directory_and_filename_with_csv_inside_are_preserved(self):
        folder=self.root/'archive.csv';folder.mkdir()
        self.out=folder/'name.csv.backup'
        self.assertEqual(self.run_cli(args=('topic','--profiles','account'))[0], 0)
        self.assertTrue((folder/'name.csv-profiles.csv').exists())


if __name__ == '__main__':
    unittest.main()
