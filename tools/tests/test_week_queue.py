"""Regresiones de cargas reales: orden, duplicados, huecos y transacciones."""
import csv
import hashlib
import io
import json
import os
import argparse
import subprocess
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import audit_week_source
import process_week_queue as queue
import update_week
import verify_week_publish
import weekly_source

HEADERS = ['Semana', 'Tiendas', 'Categoría Inventario', 'Ingrediente', 'Indicadores', 'Uso Ideal* (#)']
DIRECTORY = {'38101': 'Tienda Uno'}
RECORDS = {'38101': {'name': 'Tienda Uno', 'status': 'Abierta', 'priority': 0}}


def write_csv(root, name, week, usage='2.50', extra=None):
    path = root / 'updates/incoming' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(HEADERS)
    writer.writerow([week, '38101', 'Bebidas', 'Agua', '', usage])
    if extra:
        writer.writerow(extra)
    path.write_text(output.getvalue(), encoding='utf-8-sig')
    return path


def fixture(root):
    (root / 'data/stores_01').mkdir(parents=True)
    (root / 'audit').mkdir()
    (root / 'sources').mkdir()
    (root / 'updates/incoming').mkdir(parents=True)
    manifest = {'weeks': list(range(1, 35)), 'categories': ['Bebidas'],
        'ingredients': [{'name': 'Agua', 'sap': 'Agua', 'code': '1', 'woe': '2', 'unit': 'PZA',
                         'pickpack': 'PZA', 'factor': 1, 'sapStatus': 'ok', 'formatStatus': 'ok'}],
        'stores': [{'code': '38101', 'name': 'Tienda Uno', 'label': '38101 · Tienda Uno',
                    'file': 'data/stores_01/38101.json', 'status': 'Abierta'}],
        'counts': {'rows': 1, 'positiveRows': 1, 'rowsByWeek': {str(n): int(n == 34) for n in range(1, 35)},
                   'positiveByWeek': {str(n): int(n == 34) for n in range(1, 35)}}}
    (root / 'data/manifest.js').write_text('window.MAXMIN_MANIFEST=' + json.dumps(manifest) + ';\n')
    (root / 'data/stores_01/38101.json').write_text('{"34":[0,0,100]}')


def data_snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in (root / 'data').rglob('*') if p.is_file()}


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'project'
        fixture(self.root)
        crosses = (DIRECTORY, {}, {})
        self.patches = [patch.object(update_week, 'load_directory_records', return_value=RECORDS),
            patch.object(update_week, 'load_crosses', return_value=crosses),
            patch.object(audit_week_source, 'load_crosses', return_value=crosses),
            patch.object(verify_week_publish, 'load_directory_records', return_value=RECORDS),
            patch.object(queue, 'run_checks')]
        for value in self.patches:
            value.start()

    def tearDown(self):
        for value in reversed(self.patches):
            value.stop()
        self.temp.cleanup()

    def csv(self, week, **kwargs):
        return write_csv(self.root, f'Max & Min_{week}.csv', week, **kwargs)

    def test_all_pending_weeks_are_sorted_by_content(self):
        self.csv(38); self.csv(35); self.csv(37); self.csv(36)
        self.assertEqual([item['week'] for item in queue.plan_queue(self.root)['sources']], [35, 36, 37, 38])

    def test_exact_duplicates_use_correct_name_once(self):
        right = self.csv(38)
        (right.parent / 'Max & Min_37.csv').write_bytes(right.read_bytes())
        plan = queue.plan_queue(self.root)
        self.assertEqual(len(plan['sources']), 1)
        self.assertTrue(plan['sources'][0]['path'].endswith('_38.csv'))
        self.assertEqual(plan['misnamed'][0]['week'], 38)
        report = queue.process_queue(self.root)
        self.assertEqual(report['processedWeeks'], [38])
        self.assertEqual(report['pendingWeeks'], [35, 36, 37])
        self.assertEqual(len(report['retiredSources']), 2)
        rows = json.loads((self.root / 'data/stores_01/38101.json').read_text())
        self.assertEqual(rows['38'], [0, 0, 250])
        self.assertNotIn('37', rows)

    def test_conflicting_versions_of_a_week_block_entire_batch(self):
        self.csv(35)
        write_csv(self.root, 'correccion_35.csv', 35, '9')
        before = data_snapshot(self.root)
        with self.assertRaisesRegex(ValueError, 'fuentes distintas'):
            queue.process_queue(self.root)
        self.assertEqual(before, data_snapshot(self.root))
        self.assertEqual(len(list((self.root / 'updates/incoming').glob('*.csv'))), 2)

    def test_mixed_week_csv_is_rejected(self):
        self.csv(35, extra=[36, '38101', 'Bebidas', 'Otra', '', '1'])
        with self.assertRaisesRegex(ValueError, 'mezcla semanas'):
            queue.plan_queue(self.root)

    def test_fractional_and_out_of_range_weeks_are_not_truncated(self):
        for week in ['38.5', 'NaN', 'Infinity', '0', '54', 'texto']:
            with self.subTest(week=week), self.assertRaises(ValueError):
                weekly_source.parse_week(week)
        self.assertEqual(weekly_source.parse_week('38.0'), 38)

    def test_non_finite_negative_and_overflow_usage_block_before_publish(self):
        for usage in ['NaN', 'Infinity', '-1', '42949673']:
            with self.subTest(usage=usage):
                path = self.csv(35, usage=usage)
                before = data_snapshot(self.root)
                with self.assertRaises(SystemExit):
                    queue.process_queue(self.root)
                self.assertEqual(before, data_snapshot(self.root))
                self.assertTrue(path.exists())

    def test_blank_usage_is_zero(self):
        self.assertEqual(weekly_source.parse_usage(' '), 0)

    def test_week35_and36_are_verified_after_the_full_batch(self):
        self.csv(36, usage='3'); self.csv(35)
        report = queue.process_queue(self.root)
        self.assertEqual(report['processedWeeks'], [35, 36])
        self.assertEqual(report['pendingWeeks'], [])
        self.assertEqual([r['mismatches'] for r in report['publications']], [0, 0])
        self.assertEqual(update_week.read_manifest(self.root)['counts']['positiveRows'], 3)

    def test_late_week_fills_gap_without_altering_other_weeks(self):
        self.csv(38); queue.process_queue(self.root)
        before = json.loads((self.root / 'data/stores_01/38101.json').read_text())
        self.csv(37, usage='7'); report = queue.process_queue(self.root)
        after = json.loads((self.root / 'data/stores_01/38101.json').read_text())
        self.assertEqual(after['38'], before['38'])
        self.assertEqual(after['34'], before['34'])
        self.assertEqual(after['37'], [0, 0, 700])
        self.assertEqual(report['pendingWeeks'], [35, 36])

    def test_replacing_week_does_not_accumulate_old_rows(self):
        self.csv(35); queue.process_queue(self.root)
        self.csv(35, usage='9'); queue.process_queue(self.root)
        manifest = update_week.read_manifest(self.root)
        self.assertEqual(manifest['counts']['positiveByWeek']['35'], 1)
        self.assertEqual(json.loads((self.root / 'data/stores_01/38101.json').read_text())['35'], [0, 0, 900])

    def test_repeated_identical_upload_is_idempotent(self):
        self.csv(35); queue.process_queue(self.root)
        before = data_snapshot(self.root)
        self.csv(35); queue.process_queue(self.root)
        self.assertEqual(before, data_snapshot(self.root))

    def test_failed_final_check_preserves_original_and_source(self):
        path = self.csv(35)
        before = data_snapshot(self.root)
        with patch.object(queue, 'run_checks', side_effect=RuntimeError('failed check')):
            with self.assertRaisesRegex(RuntimeError, 'failed check'):
                queue.process_queue(self.root)
        self.assertEqual(before, data_snapshot(self.root))
        self.assertTrue(path.exists())

    def test_changed_upload_is_not_removed(self):
        path = self.csv(35)
        before = data_snapshot(self.root)
        with self.assertRaisesRegex(ValueError, 'cambió'):
            queue.process_queue(self.root, before_promote=lambda: path.write_text('nueva carga'))
        self.assertEqual(before, data_snapshot(self.root))
        self.assertEqual(path.read_text(), 'nueva carga')

    def test_new_remote_upload_prevents_promotion(self):
        self.csv(35)
        before = data_snapshot(self.root)
        def newer():
            raise queue.NewUploads('main avanzó')
        with self.assertRaises(queue.NewUploads):
            queue.process_queue(self.root, before_promote=newer)
        self.assertEqual(before, data_snapshot(self.root))
        self.assertTrue((self.root / 'updates/incoming/Max & Min_35.csv').exists())

    def test_io_failure_during_promotion_rolls_back(self):
        path = self.csv(35)
        before = data_snapshot(self.root)
        replace = os.replace
        def fail_once(src, dst):
            if Path(src).name == 'audit' and 'maxmin-validated-' in str(src):
                raise OSError('simulated disk failure')
            return replace(src, dst)
        with patch.object(queue.os, 'replace', side_effect=fail_once), self.assertRaises(OSError):
            queue.process_queue(self.root)
        self.assertEqual(before, data_snapshot(self.root))
        self.assertTrue(path.exists())

    def test_manual_week_must_match_content(self):
        self.csv(38)
        with self.assertRaisesRegex(ValueError, 'no coincide'):
            queue.plan_queue(self.root, 'updates/incoming/Max & Min_38.csv', '37')

    def test_no_pending_source_is_a_successful_noop(self):
        self.assertEqual(queue.process_queue(self.root)['status'], 'noop')

    def test_push_is_forbidden_outside_isolated_actions_main(self):
        with patch.dict(os.environ, {'GITHUB_ACTIONS': 'false'}), self.assertRaises(ValueError):
            queue.publish(type('Args', (), {'root': self.root})())

    def test_actions_push_commits_verified_data_and_retires_only_sources(self):
        self.csv(35)
        origin = Path(self.temp.name) / 'origin.git'
        def command(*args, cwd=self.root):
            return subprocess.check_output(['git', *args], cwd=cwd, stderr=subprocess.DEVNULL, text=True).strip()
        command('init', '--bare', str(origin))
        command('init', '-b', 'main')
        command('config', 'user.name', 'Test Maintainer')
        command('config', 'user.email', 'test@example.invalid')
        command('add', '.')
        command('commit', '-m', 'baseline')
        command('remote', 'add', 'origin', str(origin))
        command('push', '-u', 'origin', 'main')
        args = argparse.Namespace(root=self.root, input='', week='')
        with patch.dict(os.environ, {'GITHUB_ACTIONS': 'true', 'GITHUB_REF': 'refs/heads/main', 'GITHUB_WORKSPACE': str(self.root)}):
            report = queue.publish(args)
        self.assertEqual(report['processedWeeks'], [35])
        self.assertEqual(command('rev-parse', 'HEAD'), command('rev-parse', 'refs/heads/main', cwd=origin))
        data = command('show', 'main:data/manifest.js', cwd=origin)
        self.assertIn(35, json.loads(data.split('=', 1)[1][:-1])['weeks'])
        self.assertNotIn('updates/incoming/Max & Min_35.csv', command('ls-tree', '-r', '--name-only', 'main', cwd=origin))

    def test_path_outside_incoming_is_rejected(self):
        path = self.csv(35)
        outside = self.root / 'fuera.csv'; outside.write_bytes(path.read_bytes())
        with self.assertRaisesRegex(ValueError, 'directo'):
            queue.plan_queue(self.root, 'fuera.csv')

    def test_zip_may_have_wrong_name_but_real_content_is_authoritative(self):
        path = self.csv(38); raw = path.read_bytes(); path.unlink()
        with zipfile.ZipFile(path.parent / 'Max & Min_37.ZIP', 'w') as archive:
            archive.writestr('Max & Min_37.csv', raw)
        self.assertEqual(queue.plan_queue(self.root)['sources'][0]['week'], 38)

    def test_zip_with_two_csvs_is_ambiguous(self):
        path = self.root / 'updates/incoming/Max & Min_35.zip'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('a.csv', 'x'); archive.writestr('b.csv', 'x')
        with self.assertRaisesRegex(ValueError, 'exactamente un CSV'):
            weekly_source.read_source(path)

    def test_zip_traversal_is_rejected(self):
        path = self.root / 'updates/incoming/Max & Min_35.zip'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('../35.csv', 'x')
        with self.assertRaisesRegex(ValueError, 'insegura'):
            weekly_source.read_source(path)

    def test_zip_expanded_size_is_bounded(self):
        path = self.root / 'updates/incoming/Max & Min_35.zip'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('35.csv', 'x' * 200)
        with patch.object(weekly_source, 'MAX_EXPANDED_BYTES', 100), self.assertRaisesRegex(ValueError, 'grande'):
            weekly_source.read_source(path)

    def test_limits_apply_per_file_not_to_combined_queue(self):
        a = self.csv(35); b = self.csv(36)
        cap = max(a.stat().st_size, b.stat().st_size)
        self.assertGreater(a.stat().st_size + b.stat().st_size, cap)
        with patch.object(weekly_source, 'MAX_UPLOAD_BYTES', cap):
            self.assertEqual(len(queue.plan_queue(self.root)['sources']), 2)
        with patch.object(weekly_source, 'MAX_UPLOAD_BYTES', cap - 1), self.assertRaises(ValueError):
            queue.plan_queue(self.root)


if __name__ == '__main__':
    unittest.main()
